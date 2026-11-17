import argparse
import sys
from pathlib import Path

from core.errors import ConflictError
from core.keys import DEFAULT_OWNER, DEFAULT_SPACE
from core.repo import Repository
from core.store import commit_changeset, parse_expect_head


def _repo_path(raw: str | None) -> Path:
    return Path(raw or ".").resolve()


def cmd_init(args: argparse.Namespace) -> int:
    repo = Repository.init(_repo_path(args.path))
    repo.close()
    print(f"инициализирован репозиторий: {args.path or '.'}")
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    repo = Repository.open(_repo_path(args.path))
    try:
        src = Path(args.file)
        data = src.read_bytes()
        blob_hash = repo.blobs.put(data)
        repo.work.set_path(DEFAULT_SPACE, args.doc_path, blob_hash)
        print(f"записан {args.doc_path} ({len(data)} байт)")
    finally:
        repo.close()
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    repo = Repository.open(_repo_path(args.path))
    try:
        expected = parse_expect_head(args.expect_head)
        cs_id = commit_changeset(
            repo,
            DEFAULT_SPACE,
            message=args.message,
            author=args.author or DEFAULT_OWNER,
            expected_head=expected,
        )
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
        head = repo.pointers.head(DEFAULT_SPACE)
        work = repo.work.read(DEFAULT_SPACE)
        if head is None:
            for path in sorted(work):
                print(f"+ {path}")
            return 0
        cs = repo.changesets.get(head.decode())
        tree = repo.blobs.read_tree(cs["tree_hash"])
        if not work:
            print("нет локальных изменений")
            return 0
        merged = dict(tree)
        merged.update(work)
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
        cs = repo.changesets.get(ref)
        tree = repo.blobs.read_tree(cs["tree_hash"])
        out_root = _repo_path(args.path)
        for path, blob_hash in tree.items():
            dest = out_root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(repo.blobs.read(blob_hash))
        repo.work.write(DEFAULT_SPACE, dict(tree))
        print(f"checkout {ref[:8]} ({len(tree)} файлов)")
    finally:
        repo.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dv")
    parser.add_argument("--path", default=".", help="путь к репозиторию")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="создать репозиторий")

    write_p = sub.add_parser("write", help="добавить файл в черновик")
    write_p.add_argument("doc_path", help="путь документа в хранилище")
    write_p.add_argument("file", help="локальный файл с содержимым")

    commit_p = sub.add_parser("commit", help="закоммитить черновик")
    commit_p.add_argument("-m", "--message", required=True)
    commit_p.add_argument("--author", default=DEFAULT_OWNER)
    commit_p.add_argument("--expect-head", dest="expect_head", default=None)

    sub.add_parser("log", help="история changesets")

    sub.add_parser("diff", help="diff head vs черновик")

    checkout_p = sub.add_parser("checkout", help="восстановить дерево по ref")
    checkout_p.add_argument("ref", nargs="?", default=None)
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
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
