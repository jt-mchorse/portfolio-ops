"""The history ratchet counts a block with a duplicate top-level key (#107).

A clean ``merge=union`` rebase glued two appended entries into one fenced
block: the first entry's ``followups: [] / ---`` tail was hoisted out once and
the second entry ran straight on from it. That block still loads.
``yaml.safe_load`` keeps the last copy of each repeated key, so it reads as the
second entry alone and the first is gone, with no parse error for the ratchet to
count. Measured on the 13 origin/main files on 2026-10-21: 29 such blocks in
every repo, 28 of them glued pairs or runs hiding 49 entries behind the 28 that
still read, most from the 2026-10-07 night run.

The last arm builds the glued block the way it was really made: a real
``git rebase`` with ``MEMORY/*.md merge=union`` in ``.git/info/attributes``.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_memory_yaml.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_memory_yaml", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


count_unparseable = _load_module().count_unparseable

ENTRY_A = 'session: 2026-10-21T07:00Z\nissue: 380\nphase: shipped\nmeasured: "a"\n'
ENTRY_B = 'session: 2026-10-21T07:20Z\nissue: 378\nphase: shipped\nmeasured: "b"\n'
TRAILER = "decisions_made: []\nfollowups: []\n"

# The shape #107 found on three mains: A's trailer and fence gone, B glued on.
GLUED = "---\n" + ENTRY_A + ENTRY_B + TRAILER + "---\n"


def test_a_glued_pair_is_counted() -> None:
    bad, total, reasons = count_unparseable(GLUED)
    assert (bad, total) == (1, 1)
    assert "session" in reasons[0] and "duplicate" in reasons[0]


def test_a_repeated_decisions_made_is_counted() -> None:
    """portfolio-ops' own 2026-05-27 entry: `[D-006, D-007]` then `[]`, so the
    two recorded decisions read as none."""
    block = (
        "---\n"
        + ENTRY_A
        + "decisions_made: [D-006, D-007]\ndecisions_made: []\nfollowups: []\n---\n"
    )
    bad, _, reasons = count_unparseable(block)
    assert bad == 1
    assert reasons == ["duplicate top-level key(s): decisions_made"]


def test_a_glued_file_regresses_the_cli(tmp_path: Path) -> None:
    f = tmp_path / "full_history_ai.md"
    f.write_text(GLUED, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(f), "--repo", "no-such-repo"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "duplicate top-level key(s): session" in proc.stderr


def test_two_fenced_entries_are_not_counted() -> None:
    """Control: the same two entries, written whole."""
    text = "---\n" + ENTRY_A + TRAILER + "---\n\n---\n" + ENTRY_B + TRAILER + "---\n"
    assert count_unparseable(text)[:2] == (0, 2)


def test_a_key_repeated_under_different_parents_is_not_counted() -> None:
    """Control: only the top level is checked. `files_changed` in two nested
    mappings, and a nested `session:`, are not duplicates of anything."""
    block = (
        "---\n" + ENTRY_A + "delta:\n  files_changed: 2\n  session: x\n"
        "measured_by:\n  files_changed: 3\n" + TRAILER + "---\n"
    )
    assert count_unparseable(block)[:2] == (0, 1)


def test_an_unloadable_glued_block_is_counted_once() -> None:
    """Control: a block that already fails to load is one failure, not two."""
    block = "---\n" + ENTRY_A + ENTRY_B + "followups: [#107]\n---\n"
    bad, total, reasons = count_unparseable(block)
    assert (bad, total) == (1, 1)
    assert "duplicate" not in reasons[0]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )


def test_a_real_union_rebase_produces_a_block_the_ratchet_counts(
    tmp_path: Path,
) -> None:
    """End to end: the 2026-10-21 shape, from git, not by hand."""
    repo = tmp_path
    hist = repo / "MEMORY" / "full_history_ai.md"
    hist.parent.mkdir()
    _git(repo, "init", "-q", "-b", "main", ".")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    base = "---\nsession: base\nphase: shipped\n" + TRAILER + "---\n"
    hist.write_text(base, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "side")
    hist.write_text(base + "\n---\n" + ENTRY_B + TRAILER + "---\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "B")
    _git(repo, "checkout", "-q", "main")
    hist.write_text(base + "\n---\n" + ENTRY_A + TRAILER + "---\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "A")
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "attributes").write_text(
        "MEMORY/*.md merge=union\n", encoding="utf-8"
    )
    _git(repo, "checkout", "-q", "side")
    rebase = _git(repo, "rebase", "main")
    assert rebase.returncode == 0, rebase.stdout + rebase.stderr

    text = hist.read_text(encoding="utf-8")
    assert text.count("session:") == 3
    bad, total, _ = count_unparseable(text)
    assert (bad, total) == (1, 2), text
