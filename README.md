# DocVault

![CI](https://github.com/MrGrose/docvault/actions/workflows/ci.yml/badge.svg?branch=main) ![Python](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white) ![LMDB](https://img.shields.io/badge/storage-LMDB-0d47a1) ![uv](https://img.shields.io/badge/uv-DE5FE9?logo=python&logoColor=white) ![Docker](https://img.shields.io/badge/Docker%20Compose-2496ED?logo=docker&logoColor=white)

![DocVault architecture overview](docs/assets/demo.png)

Версионированное хранилище документов с доказуемой целостностью: OCC/CAS на ревизии `head`, changesets, CDC для blob, HTTP API и CLI. Автономный агент правит черновик в Docker-песочнице через capability broker; человек утверждает публикацию с проверкой цитат из исходных байтов (HITL).

## Возможности

- LMDB-хранилище с оптимистичным контролем на `head` (без потери обновлений при конкуренции).
- Changesets и publish с CAS; CLI `dv` и REST API.
- Buzhash CDC и дедупликация крупных blob.
- FastAPI: changesets, documents, runs, audit; `Idempotency-Key` на мутациях.
- Capability broker (UDS) и Docker sandbox (`network none`) для кода агента.
- Evidence и claims; слабый support -> human review; UI на `/ui`.

## Архитектурные принципы

- **Один доменный слой** - `Repository` + LMDB для CLI, API и broker; агент не читает LMDB напрямую.
- **CAS на head** - publish только при совпадении ожидаемой ревизии.
- **Изоляция агента** - запись только через capability token и broker.
- **HITL** - publish после вердикта с проверкой, что цитата - подстрока bytes по `source_ref` (полной антигаллюцинации LLM нет).
- **Audit** - значимые события, включая HITL, в журнале LMDB.

## Tech Stack

Python 3.13, [uv](https://docs.astral.sh/uv/), FastAPI, LMDB, structlog, Docker / Docker Compose, pytest, ruff, mypy.

## Quick Start

Нужны Python 3.13 (uv поставит нужную версию сам), Docker для песочницы и fault-теста.

```bash
git clone git@github.com:MrGrose/docvault.git
cd docvault
uv sync
make lint && make test
make demo-1
export DOCVAULT_CAPABILITY_SECRET=dev-demo-secret && make demo-agent
make demo-hitol
```

Для HITL-демо:

```bash
export DOCVAULT_REPO=./data/hitol-repo
uv run python -m cli.dv --path "$DOCVAULT_REPO" init
uv run uvicorn main:app --app-dir src --port 8080
# UI: http://127.0.0.1:8080/ui/
make demo-hitol
```

## Demos

| Команда | Что показывает |
|---------|----------------|
| `make demo-1` | LMDB, CAS, CLI, concurrent writers |
| `make demo-agent` | Broker UDS, sandbox, agent pipeline |
| `make demo-hitol` | Evidence, HITL UI, runs, audit |

Опционально: `make test-fault` (Docker, отдельный CI job).

## Проверено на практике

| Проверка | Результат |
|----------|-----------|
| `uv run pytest` | 65 тестов проходят, 1 скипается (fault-тест требует Docker) |
| `uv run pytest --cov=src` | покрытие 86% по `src`, включая песочницу и CLI |
| `uv run ruff check .` и `uv run mypy src` | без замечаний, mypy в strict-режиме |
| Локальность CDC | вставка одного байта в файл 96 КБ меняет 1 чанк из 27 |
| CI | ruff, формат, mypy, pytest с покрытием; fault-тест отдельным job в Docker |

Числа получены на локальной машине (8 ядер), воспроизводятся командами из раздела Development.

## Бенчмарк CDC

`make bench` сравнивает buzhash и фиксированные чанки по 4 КБ на трех сценариях правки. Метрика это отношение всех байтов десяти версий к байтам, которые реально остались после дедупликации: чем больше, тем лучше хранилище.

| Сценарий | buzhash CDC | fixed 4 КБ |
|----------|------------:|-----------:|
| правка 2% на месте | 6.58x | 7.81x |
| вставка 3000 Б | 6.29x | 1.80x |
| удаление 3000 Б | 6.02x | 1.40x |

База 300 КБ, 10 версий, seed 42, время на все 10 версий: CDC около 0.3 с, fixed около 0.001 с. Fixed выигрывает на правке без сдвига границ (там ему достаточно переписать один блок), а на вставке и удалении теряет почти все чанки после места правки. Время CDC это цена python-реализации, а не алгоритма; чанки считаются один раз при записи blob.

## Запуск в Docker Compose

```bash
docker compose up --build -d
curl -s http://127.0.0.1:8000/health   # {"status":"ok"}
```

- Данные лежат в `./data` (в контейнере `/app/data`, репозиторий `/app/data/repo`), каталог переживает перезапуск.
- UI: `http://127.0.0.1:8000/ui/`, OpenAPI: `http://127.0.0.1:8000/docs`.
- Остановить: `docker compose down`.
- Песочница и `make demo-agent` из этого контейнера не запускаются: агенту нужен доступ к `docker.sock` и broker по UDS. Эти демо запускаются на хосте, как описано выше.

## API

Группы: **changesets** (create, write doc, publish), **docs**, **runs** (создание, вердикты), **audit**. На всех мутациях обязателен заголовок `Idempotency-Key`: повтор с тем же ключом возвращает сохраненный ответ, тот же ключ с другим телом дает `409 idempotency_mismatch`.

```bash
BASE=http://127.0.0.1:8080

# 1. Черновик: id в ответе равен имени пространства
curl -s -X POST $BASE/changesets \
  -H 'Content-Type: application/json' -d '{"space":"default"}'

# 2. Запись документа в черновик
curl -s -X PUT $BASE/changesets/default/doc/docs/offer.md \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: write-1' \
  -d '{"content":"# Оффер\n\nТариф 100 рублей.\n"}'

# 3. Публикация (CAS на head)
curl -s -X POST $BASE/changesets/default/publish \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: publish-1' \
  -d '{"message":"оффер","author":"user:host"}'

# 4. Конфликт: сначала есть незакоммиченная правка, затем publish со старым head
curl -s -X PUT $BASE/changesets/default/doc/docs/offer.md \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: write-2' \
  -d '{"content":"# Оффер v2\n"}'
curl -s -X POST $BASE/changesets/default/publish \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: publish-2' \
  -d '{"message":"оффер","expected_head":"deadbeef"}'   # 409 rebase_required

# 5. Чтение опубликованного дерева и файла
curl -s "$BASE/docs/tree?space=default"
curl -s "$BASE/docs/doc/docs/offer.md"

# 6. Агентский прогон: claim с цитатой и правкой
curl -s -X POST $BASE/runs \
  -H 'Content-Type: application/json' \
  -d '{"claims":[{"text":"тариф 100 рублей","quote":"Тариф 100 рублей","source_ref":"<sha256 blob>"}],"write":{"path":"docs/offer.md","content":"# Оффер\n\nТариф 100 рублей.\n"}}'

# 7. Вердикт человека: accept публикует, reject отклоняет
curl -s -X POST $BASE/runs/<run_id>/verdicts \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: verdict-1' \
  -d '{"verdict":"accept"}'

# 8. Журнал: обычный publish туда не пишется, записи появляются после HITL-вердикта
curl -s "$BASE/audit?limit=20"
```

Коды ответов: `200` успех, `202` прогон требует человека (`needs_human`), `409` конфликт CAS, `rebase_required` или `idempotency_mismatch`, `422` цитата не подтверждена (`ungrounded`) или отсутствует `Idempotency-Key`.

## Ограничения

- Одна нода и один процесс: LMDB-файл, `MAP_SIZE` 50 МБ задается при открытии и на лету не растет.
- LMDB пускает одного писателя за раз; конкурентность держится на CAS в логике, а не на параллельной записи.
- Rebase это повтор с новым `head`, трехстороннего merge нет: конфликтующие пути не сливаются автоматически.
- Capability-токен это HMAC-подпись секретом из `DOCVAULT_CAPABILITY_SECRET` с TTL; списка отзыва и привязки токена к конкретному run нет.
- Песочница требует Docker и доступа к `docker.sock` на хосте; broker слушает только UDS, из другой машины к нему не подключиться.
- Антигаллюцинация ограничена: проверяется, что цитата является подстрокой байтов источника, смысл утверждения не проверяется.
- Идемпотентные ключи хранятся без TTL и не чистятся, журнал аудита только дописывается и читается через API; обычный publish в аудит не попадает, там только HITL-публикации.
- Публикация пустого черновика отвечает `409 conflict` с ошибкой `нет изменений для коммита`; отдельного кода для этого случая нет.
- Полнотекстового поиска по документам нет.

## Development

```bash
make lint          # ruff + mypy src
make test          # pytest (unit + integration + BDD)
make bench         # бенчмарк CDC: три сценария правки
uv run pytest tests/bdd/ -q
uv run pytest --cov=src --cov-report=term-missing tests/
```

Перед merge: тесты и линтер зеленые локально и в CI.

### `scripts/`

Вспомогательные сценарии для демо и локальных замеров (не часть runtime `src/`). Демо-шеллы вызываются из `make demo-*`; остальное запускается вручную.

| Файл | Назначение |
|------|------------|
| `demo_1.sh` | LMDB, CAS, параллельные writers через CLI |
| `demo_agent.sh` | broker UDS, sandbox, agent pipeline |
| `demo_hitol.sh` | HITL: поднимает сценарий и вызывает клиент |
| `hitol_demo_client.py` | HTTP-клиент для HITL-демо (runs, verdict, publish) |
| `bench_cdc.py` | бенч buzhash и fixed-chunk на трех сценариях правки |

Запуск бенча: `make bench`.

## Architecture

На хосте: API, CLI, broker и LMDB. Агент в контейнере без сети обращается к broker по UDS; broker пишет в тот же `Repository`, что и API.

Подробно: компоненты, поток от агента до publish, хранение, безопасность и ограничения реализации - **[docs/architecture.md](docs/architecture.md)**.