# DocVault

![CI](https://github.com/MrGrose/docvault/actions/workflows/ci.yml/badge.svg?branch=main) ![Python](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white) ![LMDB](https://img.shields.io/badge/storage-LMDB-0d47a1) ![uv](https://img.shields.io/badge/uv-DE5FE9?logo=python&logoColor=white) ![Docker](https://img.shields.io/badge/Docker%20Compose-2496ED?logo=docker&logoColor=white)

![DocVault architecture overview](docs/assets/demo.png)

Версионированное хранилище документов с изолированными черновиками, неизменяемыми changesets и публикацией через CAS. Агент правит черновик в песочнице без сети, человек утверждает публикацию с проверкой цитат. Каждая публикация оставляет запись в audit и provenance.

## Возможности

- Черновик на автора: свой id, владелец, `base_head`, пути и конфликты. Общей рабочей копии нет.
- Публикация только при `expected_head == draft.base_head`, CAS на `head`, конфликт дает 409.
- Rebase создает новый черновик, старый не меняется, конфликтные пути помечаются.
- Changesets неизменяемы, дерево публикации это база черновика плюс его пути.
- Buzhash CDC и дедупликация крупных blob.
- Claims с тремя результатами: evidence, binding к измененному фрагменту, support как подсказка.
- Provenance с хэшем цитаты и ссылкой на источник, audit на каждый publish в одной транзакции.
- Capability broker по UDS, токен привязан к space и draft_id.
- Docker sandbox: без сети, лимиты памяти, CPU, pids, read-only rootfs, non-root.
- UI на `/ui`: diff, цитаты, статусы и предупреждение о ручной проверке смысла.

## Принципы

- **Один доменный слой.** `Repository` и LMDB для CLI, API и broker; агент не читает базу.
- **Draft isolation.** Два автора могут менять один путь в разных черновиках, конфликт виден на publish.
- **CAS и атомарность.** Changeset, `head`, provenance, audit и idempotency outcome пишутся вместе.
- **Grounding без обещаний.** `grounded` значит "цитата найдена и утверждение привязано к изменению", а не "утверждение истинно".
- **Минимум поверхности.** API только на localhost, песочница без сети, доступ к данным только через broker.

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

Для HITL-демо с UI:

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
| `make demo-1` | Черновики, CAS, CLI, конкурентные писатели |
| `make demo-agent` | Broker UDS, sandbox, агентский черновик и публикация |
| `make demo-hitol` | Claims, evidence, вердикт, audit |

Опционально: `make test-fault` (Docker, отдельный CI job).

## Проверено на практике

| Проверка | Результат |
|----------|-----------|
| `uv run pytest` | 150 тестов проходят, 1 скипается (fault-тест требует Docker) |
| `uv run pytest --cov=src` | покрытие 91% по `src` |
| `uv run ruff check .` и `uv run mypy src` | без замечаний, mypy в strict-режиме |
| Локальность CDC | вставка одного байта в файл 96 КБ меняет 1 чанк из 27 |
| Конкурентность | симуляция 100 черновиков с rebase: 100 changesets, ни один файл не потерян |
| CI | ruff, формат, mypy, pytest с порогом покрытия; fault-тест отдельным job в Docker |

Числа получены на локальной машине (8 ядер), воспроизводятся командами из раздела Development.

## Бенчмарк CDC

`make bench` сравнивает buzhash и фиксированные чанки по 4 КБ на трех сценариях правки. Метрика это отношение всех байтов десяти версий к байтам, которые реально остались после дедупликации: чем больше, тем лучше хранилище.

| Сценарий | buzhash CDC | fixed 4 КБ |
|----------|------------:|-----------:|
| правка 2% на месте | 6.58x | 7.81x |
| вставка 3000 Б | 6.29x | 1.80x |
| удаление 3000 Б | 6.02x | 1.40x |

База 300 КБ, 10 версий, seed 42, время на все 10 версий: CDC около 0.3 с, fixed около 0.001 с. Fixed выигрывает на правке без сдвига границ, а на вставке и удалении теряет почти все чанки после места правки. Время CDC это цена python-реализации, а не алгоритма.

## Запуск в Docker Compose

```bash
docker compose up --build -d
curl -s http://127.0.0.1:8000/health   # {"status":"ok"}
```

- Порт опубликован только на `127.0.0.1:8000`. Наружу API не выставляется, удаленный доступ через SSH tunnel.
- Данные лежат в `./data`, каталог переживает перезапуск.
- UI: `http://127.0.0.1:8000/ui/`, OpenAPI: `http://127.0.0.1:8000/docs`.
- Песочница и `make demo-agent` из контейнера не запускаются: нужен доступ к `docker.sock` и broker по UDS. Эти демо идут на хосте.

## API

Группы: **changesets** (создание черновика, запись, publish, rebase), **docs**, **runs** (claims, вердикты), **audit**. На мутациях обязателен `Idempotency-Key`: повтор возвращает сохраненный ответ, тот же ключ с другим телом дает `409 idempotency_mismatch`.

```bash
BASE=http://127.0.0.1:8080

# 1. Черновик: в ответе id и base_head
curl -s -X POST $BASE/changesets \
  -H 'Content-Type: application/json' -d '{"space":"default"}'
# {"id":"<draft_id>","space":"default","owner":"user:host","base_head":null}

# 2. Запись документа
curl -s -X PUT "$BASE/changesets/<draft_id>/doc/docs/offer.md" \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: write-1' \
  -d '{"content":"# Оффер\n\nТариф 100 рублей.\n"}'

# 3. Публикация: expected_head равен base_head, для первого коммита это genesis
curl -s -X POST "$BASE/changesets/<draft_id>/publish" \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: publish-1' \
  -d '{"message":"оффер","author":"user:host","expected_head":"genesis"}'

# 4. Конфликт: второй черновик на той же базе получает 409 rebase_required
curl -s -X POST "$BASE/changesets/<draft_id>/rebase" \
  -H 'Idempotency-Key: rebase-1'
# {"draft":{...,"conflicts":["docs/offer.md"]}}

# 5. Чтение опубликованного дерева и файла
curl -s "$BASE/docs/tree?space=default"
curl -s "$BASE/docs/doc/docs/offer.md"

# 6. Агентский прогон: claim привязан к пути черновика
curl -s -X POST $BASE/runs \
  -H 'Content-Type: application/json' \
  -d '{"draft_id":"<draft_id>","claims":[{"path":"docs/offer.md","text":"тариф 100 рублей","quote":"Тариф 100 рублей","source_ref":"<sha256 blob>"}]}'

# 7. Вердикт: expected_head это база, которую видел ревьюер
curl -s -X POST "$BASE/runs/<run_id>/verdicts" \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: verdict-1' \
  -d '{"verdict":"accept","expected_head":"genesis"}'

# 8. Журнал: каждый publish, включая CLI и API
curl -s "$BASE/audit?limit=20"
```

Коды ответов: `201` черновик создан, `200` запись, публикация или вердикт, `409` конфликт CAS, `rebase_required`, `idempotency_mismatch` или закрытый черновик, `422` ошибка валидации, неподтвержденная цитата, отсутствующий `Idempotency-Key` или `expected_head`, `403` чужой черновик.

## Ограничения

- Одна нода и один процесс: LMDB, размер карты задается `DOCVAULT_MAP_SIZE` при открытии, на лету не растет.
- LMDB пускает одного писателя; конкурентность держится на CAS и rebase, а не на параллельной записи.
- Rebase не делает трехсторонний merge: конфликтные пути помечаются и правятся вручную.
- Capability-токен это HMAC с TTL, привязанный к space и draft_id; списка отзыва нет.
- Песочница требует Docker и `docker.sock` на хосте, broker слушает только UDS.
- Проверяется буквальная цитата и привязка к изменению; смысл утверждения проверяет человек.
- Идемпотентные ключи хранятся без TTL, журнал аудита только дописывается.
- API без аутентификации, только localhost. Для удаленного доступа SSH tunnel, не VPN и не публичный интерфейс.
- Полнотекстового поиска нет.

## Development

```bash
make lint          # ruff + mypy src
make test          # pytest (unit + integration + BDD)
make bench         # бенчмарк CDC: три сценария правки
uv run pytest tests/bdd/ -q
uv run pytest --cov=src --cov-report=term-missing tests/
```

Перед merge: тесты, линтер и покрытие не ниже 90 зеленые локально и в CI.

### `scripts/`

Вспомогательные сценарии для демо и замеров, не часть runtime `src/`.

| Файл | Назначение |
|------|------------|
| `demo_1.sh` | Черновики, CAS, CLI |
| `demo_agent.sh` | Broker UDS, sandbox, агентский черновик |
| `demo_hitol.sh` | Claims, вердикт, audit |
| `hitol_demo_client.py` | HTTP-клиент для HITL-демо |
| `bench_cdc.py` | Бенч buzhash и fixed-chunk |

## Architecture

На хосте: API, CLI, broker и LMDB. Агент в контейнере без сети обращается к broker по UDS. Подробно: **[docs/architecture.md](docs/architecture.md)**.
