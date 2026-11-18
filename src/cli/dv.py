import argparse
import os
import sys
from pathlib import Path
from typing import Any

from core.errors import ConflictError
from core.idempotency.store import IdempotencyStore
from core.keys import DEFAULT_OWNER, DEFAULT_SPACE
from core.repo import Repository

STATE_NAME = ".docvault-draft"


def _repo_path(raw: str | None) -> Path:
    return Path(raw or ".").resolve()


def _state_path(repo: Repository) -> Path:
    return repo.root / STATE_NAME


def _actor() -> str:
    return os.environ.get("DOCVAULT_ACTOR", DEFAULT_OWNER)


def _read_state(repo: Repository) -> str | None:
    path = _state_path(repo)
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def _write_state(repo: Repository, draft_id: str) -> None:
    _state_path(repo).write_text(draft_id + "\n", encoding="utf-8")


def _clear_state(repo: Repository) -> None:
    path = _state_path(repo)
    if path.exists():
        path.unlink()


def _load_draft(
    repo: Repository,
    draft_id: str | None,
    create: bool = False,
) -> dict[str, Any] | None:
    state_id = draft_id or _read_state(repo)
    if state_id is None:
        if not create:
            return None
        head = repo.pointers.head(DEFAULT_SPACE)
        draft = repo.drafts.create(DEFAULT_SPACE, _actor(), head)
        _write_state(repo, str(draft["id"]))
        return draft

    try:
        draft = repo.drafts.get(state_id)
    except KeyError:
        print(f"draft не найден: {state_id}", file=sys.stderr)
        return None
    if draft_id:
        _write_state(repo, state_id)
    return draft


def cmd_init(args: argparse.Namespace) -> int:
    repo = Repository.init(_repo_path(args.path))
    repo.close()
    print(f"инициализирован репозиторий: {args.path or '.'}")
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    repo = Repository.open(_repo_path(args.path))
    try:
        draft = _load_draft(repo, args.draft, create=True)
        if draft is None:
            return 1
        if draft.get("status") != "open":
            print(f"draft не открыт: {draft.get('status')}", file=sys.stderr)
            return 1
        src = Path(args.file)
        data = src.read_bytes()
        repo.write_draft(str(draft["id"]), args.doc_path, data.decode("utf-8"), _actor())
        print(f"записан {args.doc_path} ({len(data)} байт), draft {str(draft['id'])[:8]}")
    finally:
        repo.close()
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    repo = Repository.open(_repo_path(args.path))
    try:
        draft = _load_draft(repo, args.draft)
        if draft is None:
            print("нет активного draft", file=sys.stderr)
            return 1
        if draft.get("status") != "open":
            print(f"draft не открыт: {draft.get('status')}", file=sys.stderr)
            return 1
        base_head = draft.get("base_head")
        if args.expect_head is None:
            expected = base_head.encode() if base_head else None
        elif args.expect_head == "genesis":
            expected = None
        else:
            expected = args.expect_head.encode()
        cs_id = repo.publish_draft(
            str(draft["id"]),
            expected_head=expected,
            message=args.message,
            author=args.author,
            source="cli",
        )
        _clear_state(repo)
        print(cs_id)
    except ConflictError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        repo.close()
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    repo = Repository.open(_repo_path(args.path))
    try:
        for cs in repo.changesets.log(DEFAULT_SPACE):
            print(f"{cs['id'][:8]}  {cs.get('author', '?')}  {cs.get('message', '')}")
    finally:
        repo.close()
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    repo = Repository.open(_repo_path(args.path))
    try:
        draft = _load_draft(repo, args.draft)
        paths: dict[str, str] = {}
        if draft is not None and draft.get("status") == "open":
            paths = dict(draft.get("paths") or {})
        head = repo.pointers.head(DEFAULT_SPACE)
        if head is None:
            for path in sorted(paths):
                print(f"+ {path}")
            return 0
        cs = repo.changesets.get(head.decode())
        tree = repo.blobs.read_tree(cs["tree_hash"])
        if not paths:
            print("нет локальных изменений")
            return 0
        merged = dict(tree)
        merged.update(paths)
        new_tree = repo.blobs.put_tree(merged)
        for entry in repo.blobs.diff_trees(cs["tree_hash"], new_tree):
            before = entry.get("before")
            after = entry.get("after")
            if before and after:
                print(f"~ {entry['path']}")
            elif after:
                print(f"+ {entry['path']}")
            else:
                print(f"- {entry['path']}")
    finally:
        repo.close()
    return 0


def cmd_checkout(args: argparse.Namespace) -> int:
    repo = Repository.open(_repo_path(args.path))
    try:
        head_raw = repo.pointers.head(DEFAULT_SPACE)
        ref = args.ref or (head_raw.decode() if head_raw else None)
        if ref is None:
            print("нет head для checkout", file=sys.stderr)
            return 1
        tree = repo.tree_at(ref)
        out_root = _repo_path(args.path)
        for path, blob_hash in tree.items():
            dest = out_root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(repo.blobs.read(blob_hash))
        _clear_state(repo)
        print(f"checkout {ref[:8]} ({len(tree)} файлов)")
    finally:
        repo.close()
    return 0


def cmd_idem_purge(args: argparse.Namespace) -> int:
    repo = Repository.open(_repo_path(args.path))
    try:
        removed = IdempotencyStore(repo.kv).purge_expired()
    finally:
        repo.close()
    print(f"удалено ключей: {removed}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dv")
    parser.add_argument("--path", default=".", help="путь к репозиторию")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="создать репозиторий")

    write_p = sub.add_parser("write", help="добавить файл в черновик")
    write_p.add_argument("doc_path", help="путь документа в хранилище")
    write_p.add_argument("file", help="локальный файл с содержимым")
    write_p.add_argument("--draft", default=None)

    commit_p = sub.add_parser("commit", help="опубликовать черновик")
    commit_p.add_argument("-m", "--message", required=True)
    commit_p.add_argument("--author", default=DEFAULT_OWNER)
    commit_p.add_argument("--expect-head", dest="expect_head", default=None)
    commit_p.add_argument("--draft", default=None)

    sub.add_parser("log", help="история changesets")

    diff_p = sub.add_parser("diff", help="diff head vs черновик")
    diff_p.add_argument("--draft", default=None)

    checkout_p = sub.add_parser("checkout", help="восстановить дерево по ref")
    checkout_p.add_argument("ref", nargs="?", default=None)

    sub.add_parser("idem-purge", help="удалить истекшие ключи идемпотентности")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "init": cmd_init,
        "write": cmd_write,
        "commit": cmd_commit,
        "log": cmd_log,
        "diff": cmd_diff,
        "checkout": cmd_checkout,
        "idem-purge": cmd_idem_purge,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
