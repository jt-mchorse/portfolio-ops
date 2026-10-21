"""`check_merge_attr.py`: a local merge attribute on MEMORY history is reported (#107).

`MEMORY/*.md merge=union` in each clone's `.git/info/attributes` turned the
conflict `resolve_memory_conflict.py` handles into a clean, glued merge. It is
invisible to everything committed, and it overrides a committed
`.gitattributes`, so these arms build real checkouts and ask the script about
them.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_merge_attr.py"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _clone(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main", ".")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    _git(path, "config", "commit.gpgsign", "false")
    (path / "MEMORY").mkdir()
    (path / "MEMORY" / "full_history_ai.md").write_text("---\nsession: a\n---\n")
    (path / "MEMORY" / "full_history_human.md").write_text("## a\n")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "init")
    return path


def _union(clone: Path) -> None:
    info = clone / ".git" / "info"
    info.mkdir(exist_ok=True)
    (info / "attributes").write_text("MEMORY/*.md merge=union\n")


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_an_info_attributes_union_line_is_reported(tmp_path: Path) -> None:
    _clone(tmp_path / "repos" / "clean-repo")
    _union(_clone(tmp_path / "repos" / "rag-production-kit"))
    proc = _run(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "rag-production-kit" in proc.stdout
    assert "MEMORY/full_history_ai.md: merge=union" in proc.stdout
    lines = {ln.split()[0]: ln for ln in proc.stdout.splitlines()}
    assert lines["clean-repo"].endswith(" ok")


def test_a_worktree_inherits_its_clones_union_line(tmp_path: Path) -> None:
    """Every fix agent worked in a `git worktree`, which shares the clone's
    `info/` dir. A worktree under `repos/` is reported by its own name."""
    clone = _clone(tmp_path / "canonical")
    _union(clone)
    _git(clone, "worktree", "add", "-q", str(tmp_path / "repos" / "leh-266"), "-b", "w")
    proc = _run(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "leh-266" in proc.stdout and "merge=union" in proc.stdout


def test_a_committed_gitattributes_driver_is_reported(tmp_path: Path) -> None:
    """Any non-default driver replaces the conflict the resolver expects."""
    clone = _clone(tmp_path / "portfolio-ops")
    (clone / ".gitattributes").write_text(
        "MEMORY/full_history_human.md merge=memory-append\n"
    )
    proc = _run(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "MEMORY/full_history_human.md: merge=memory-append" in proc.stdout


def test_clean_checkouts_pass(tmp_path: Path) -> None:
    """Control: no attribute anywhere is `unspecified`, exit 0."""
    _clone(tmp_path / "portfolio-ops")
    _clone(tmp_path / "repos" / "llm-eval-harness")
    proc = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.count(" ok") == 2


def test_an_attribute_on_another_path_is_not_reported(tmp_path: Path) -> None:
    """Control: only the two history files the resolver merges are asked about."""
    clone = _clone(tmp_path / "repos" / "llm-eval-harness")
    (clone / ".git" / "info" / "attributes").write_text("*.lock merge=union\n")
    assert _run(tmp_path).returncode == 0


def test_no_checkouts_is_exit_2_not_a_silent_pass(tmp_path: Path) -> None:
    (tmp_path / "repos" / "not-a-checkout").mkdir(parents=True)
    proc = _run(tmp_path)
    assert proc.returncode == 2
    assert "no git checkouts" in proc.stderr
