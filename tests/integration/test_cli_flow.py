from pathlib import Path

import pytest

from cli.dv import main


def _write_source(path: Path, content: str) -> Path:
    src = path / "source.txt"
    src.write_text(content, encoding="utf-8")
    return src


def test_cli_full_flow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    assert main(["--path", str(repo), "init"]) == 0
    assert "инициализирован репозиторий" in capsys.readouterr().out

    first = _write_source(tmp_path, "hello")
    assert main(["--path", str(repo), "write", "docs/a.md", str(first)]) == 0
    out = capsys.readouterr().out
    assert "записан docs/a.md (5 байт)" in out

    assert main(["--path", str(repo), "diff"]) == 0
    assert "+ docs/a.md" in capsys.readouterr().out

    assert main(["--path", str(repo), "commit", "-m", "first", "--expect-head", "genesis"]) == 0
    cs_id = capsys.readouterr().out.strip()
    assert len(cs_id) == 32

    assert main(["--path", str(repo), "log"]) == 0
    log_out = capsys.readouterr().out
    assert cs_id[:8] in log_out
    assert "first" in log_out

    assert main(["--path", str(repo), "diff"]) == 0
    assert "нет локальных изменений" in capsys.readouterr().out

    second = _write_source(tmp_path, "second version")
    assert main(["--path", str(repo), "write", "docs/a.md", str(second)]) == 0
    capsys.readouterr()
    assert main(["--path", str(repo), "diff"]) == 0
    assert "~ docs/a.md" in capsys.readouterr().out

    restored = tmp_path / "restore"
    restored.mkdir()
    assert main(["--path", str(restored), "init"]) == 0
    capsys.readouterr()
    assert main(["--path", str(repo), "checkout", cs_id]) == 0
    assert "checkout" in capsys.readouterr().out
    assert (repo / "docs" / "a.md").read_text(encoding="utf-8") == "hello"


def test_cli_commit_conflict_returns_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    assert main(["--path", str(repo), "init"]) == 0
    src = _write_source(tmp_path, "content")
    assert main(["--path", str(repo), "write", "docs/a.md", str(src)]) == 0
    capsys.readouterr()

    assert main(["--path", str(repo), "commit", "-m", "first"]) == 0
    capsys.readouterr()

    src.write_text("changed", encoding="utf-8")
    assert main(["--path", str(repo), "write", "docs/a.md", str(src)]) == 0
    capsys.readouterr()

    code = main(["--path", str(repo), "commit", "-m", "stale", "--expect-head", "deadbeef"])
    assert code == 2
    assert "base_head" in capsys.readouterr().err


def test_cli_commit_without_active_draft_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    assert main(["--path", str(repo), "init"]) == 0
    capsys.readouterr()
    assert main(["--path", str(repo), "commit", "-m", "nothing"]) == 1
    assert "нет активного draft" in capsys.readouterr().err


def test_cli_write_to_published_draft_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    assert main(["--path", str(repo), "init"]) == 0
    src = _write_source(tmp_path, "x")
    assert main(["--path", str(repo), "write", "docs/a.md", str(src)]) == 0
    draft_id = (repo / ".docvault-draft").read_text(encoding="utf-8").strip()
    capsys.readouterr()
    assert main(["--path", str(repo), "commit", "-m", "first"]) == 0
    capsys.readouterr()
    (repo / ".docvault-draft").write_text(draft_id + "\n", encoding="utf-8")
    assert main(["--path", str(repo), "write", "docs/b.md", str(src)]) == 1
    assert "draft не открыт" in capsys.readouterr().err


def test_cli_checkout_without_head_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    assert main(["--path", str(repo), "init"]) == 0
    capsys.readouterr()
    assert main(["--path", str(repo), "checkout"]) == 1
    assert "нет head для checkout" in capsys.readouterr().err


def test_cli_diff_new_file_without_head(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    assert main(["--path", str(repo), "init"]) == 0
    src = _write_source(tmp_path, "x")
    assert main(["--path", str(repo), "write", "docs/new.md", str(src)]) == 0
    capsys.readouterr()
    assert main(["--path", str(repo), "diff"]) == 0
    assert "+ docs/new.md" in capsys.readouterr().out
