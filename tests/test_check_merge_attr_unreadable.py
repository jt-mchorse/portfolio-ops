"""`check_merge_attr.py`: a checkout git cannot answer for does not stop the run (#118).

The per-checkout loop returned 2 on the first ``git check-attr`` failure, so
every checkout after it went unasked, and a ``merge=union`` line in one of them
went unreported. That is the same early return #118 found in
``check_memory_yaml.py``, and both run in the same Phase A step.

``aaa-broken`` is a directory with a ``.git`` file pointing nowhere. It passes
``checkouts()``'s ``(p / ".git").exists()`` test, git refuses it, and it sorts
ahead of the real clones.
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
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "init")
    return path


def _broken(path: Path) -> None:
    path.mkdir(parents=True)
    (path / ".git").write_text(f"gitdir: {path / 'no-such-gitdir'}\n")


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_git_error_ahead_of_a_union_line_is_exit_1(tmp_path: Path) -> None:
    _broken(tmp_path / "repos" / "aaa-broken")
    union = _clone(tmp_path / "repos" / "rag-production-kit")
    (union / ".git" / "info").mkdir(exist_ok=True)
    (union / ".git" / "info" / "attributes").write_text("MEMORY/*.md merge=union\n")
    proc = _run(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "rag-production-kit" in proc.stdout and "merge=union" in proc.stdout
    assert "aaa-broken" in proc.stderr, proc.stderr


def test_a_git_error_with_no_finding_is_exit_2_and_every_checkout_is_still_asked(
    tmp_path: Path,
) -> None:
    _broken(tmp_path / "repos" / "aaa-broken")
    _clone(tmp_path / "repos" / "clean-repo")
    proc = _run(tmp_path)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "clean-repo" in proc.stdout and "ok" in proc.stdout, proc.stdout
    assert "aaa-broken" in proc.stderr, proc.stderr
