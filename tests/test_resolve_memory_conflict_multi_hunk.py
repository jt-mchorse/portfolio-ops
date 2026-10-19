"""`resolve_memory_conflict.py` when git splits one appended entry into several hunks (#95).

Git's default merge does not hand the resolver one hunk per appended block. It
aligns any line the two appended blocks share -- `phase: shipped`, `delta:`,
`  files_changed: 2`, `  tests_added: 3`, a shared `**Reversibility:**` line in
the prose file -- and leaves those lines BETWEEN two hunks. The resolver used to
treat every hunk as a whole block, so it split block A after its header, glued
A's tail onto B's header and left B's tail orphaned in a fence of its own. It
printed `resolved:` and exited 0, and both earlier guards passed: no duplicated
trailer key (#65), no leftover marker (#90). lco#309 committed exactly this, and
the history ratchet was over its baseline in six other repos the same week.

Every conflict here is produced by `git init` + two branches + `git rebase`,
so the hunk layout is whatever git really emits. The assertions are on the
resolved file as a whole: it must equal base + A + B, byte for byte.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "resolve_memory_conflict.py"

AI_BASE = "# Full history\n\n---\nsession: base\nfocus: base\ndecisions_made: []\nfollowups: []\n---\n"
MD_BASE = "# History\n\n## base\n\nbase prose.\n"


def _load_module():
    spec = importlib.util.spec_from_file_location("resolve_memory_conflict", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return _load_module()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def _ai_block(session: str, issue: int, suite: str, *, extra: str = "") -> str:
    return (
        f"\n---\nsession: {session}\n{extra}issue: {issue}\nfocus: FOCUS_{issue}\n"
        "phase: shipped\ndelta:\n  files_changed: 2\n  tests_added: 3\n"
        f'  suite: "{suite}"\ndecisions_made: []\nmeasured: "measured {issue}"\n'
        "followups: []\n---\n"
    )


def _md_section(title: str, body: str) -> str:
    return (
        f"\n## {title}\n\n{body}\n\nThe suite is green.\nRuff is clean.\n"
        f"The revert probe is red.\n\n{title} closing line.\n"
    )


def _rebase_conflict(
    tmp_path: Path,
    ai: tuple[str, str],
    md: tuple[str, str] = ("", ""),
    *,
    ai_base: str = AI_BASE,
    md_base: str = MD_BASE,
    main_edits_base: str | None = None,
) -> Path:
    """main appends ai[0]/md[0]; the branch appends ai[1]/md[1]; rebase the branch."""
    repo = tmp_path
    mem = repo / "MEMORY"
    mem.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main", ".")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "merge.conflictStyle", "merge")
    (mem / "full_history_ai.md").write_text(ai_base)
    (mem / "full_history_human.md").write_text(md_base)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "side")
    (mem / "full_history_ai.md").write_text(ai_base + ai[1])
    (mem / "full_history_human.md").write_text(md_base + md[1])
    _git(repo, "commit", "-qam", "B")
    _git(repo, "checkout", "-q", "main")
    main_ai = main_edits_base if main_edits_base is not None else ai_base
    (mem / "full_history_ai.md").write_text(main_ai + ai[0])
    (mem / "full_history_human.md").write_text(md_base + md[0])
    _git(repo, "commit", "-qam", "A")
    _git(repo, "checkout", "-q", "side")
    _git(repo, "rebase", "main")
    return repo


def _hunks(text: str) -> int:
    return len(re.findall(r"^<<<<<<< ", text, flags=re.M))


def _blocks(text: str) -> list[dict]:
    out = []
    for chunk in re.split(r"^---\s*$", text, flags=re.M):
        if chunk.strip() and not chunk.lstrip().startswith("# Full history"):
            loaded = yaml.safe_load(chunk)
            assert isinstance(loaded, dict) and "session" in loaded, chunk
            out.append(loaded)
    return out


# ----------------------------------------------------------------------
# The defect
# ----------------------------------------------------------------------


def test_git_really_splits_the_appended_block_into_two_hunks(tmp_path: Path) -> None:
    """Premise check: if git ever stops aligning interior lines, every other
    arm here would pass vacuously against the old per-hunk resolver."""
    a = _ai_block("A", 306, "A suite", extra="duration_min: 10\n")
    b = _ai_block("B", 308, "B suite")
    repo = _rebase_conflict(tmp_path, (a, b))
    assert _hunks((repo / "MEMORY" / "full_history_ai.md").read_text()) == 2


def test_a_two_hunk_yaml_conflict_keeps_each_block_whole(tmp_path: Path, mod) -> None:
    a = _ai_block("A", 306, "A suite", extra="duration_min: 10\n")
    b = _ai_block("B", 308, "B suite")
    repo = _rebase_conflict(tmp_path, (a, b))
    assert mod.main([str(repo)]) == 0
    text = (repo / "MEMORY" / "full_history_ai.md").read_text()
    assert text == AI_BASE + a + b
    blocks = _blocks(text)
    assert [(x["session"], x["issue"], x["delta"]["suite"]) for x in blocks[1:]] == [
        ("A", 306, "A suite"),
        ("B", 308, "B suite"),
    ]


def test_a_two_hunk_prose_conflict_keeps_each_section_whole(tmp_path: Path, mod) -> None:
    """The prose file splits the same way on shared lines like "The suite is
    green." -- the prose sections of one night's run share a lot of them."""
    a = _md_section("2026-10-19 — A", "A body.")
    b = _md_section("2026-10-19 — B", "B body.")
    repo = _rebase_conflict(tmp_path, ("", ""), (a, b))
    human = repo / "MEMORY" / "full_history_human.md"
    assert _hunks(human.read_text()) == 2
    assert mod.main([str(repo)]) == 0
    assert human.read_text() == MD_BASE + a + b


def test_both_blocks_starting_with_the_same_session_line(tmp_path: Path, mod) -> None:
    """Two sessions stamped in the same minute: git hoists the shared
    `session:` line ABOVE the hunk, so a per-hunk resolution wrote block B
    with no session key at all."""
    a = _ai_block("2026-10-19T08:00Z", 306, "A suite")
    b = _ai_block("2026-10-19T08:00Z", 308, "B suite")
    repo = _rebase_conflict(tmp_path, (a, b))
    assert mod.main([str(repo)]) == 0
    text = (repo / "MEMORY" / "full_history_ai.md").read_text()
    assert text == AI_BASE + a + b
    assert [x["issue"] for x in _blocks(text)[1:]] == [306, 308]


def test_each_side_appending_two_blocks(tmp_path: Path, mod) -> None:
    a = _ai_block("A1", 1, "s1") + _ai_block("A2", 2, "s2")
    b = _ai_block("B1", 3, "s3") + _ai_block("B2", 4, "s4")
    repo = _rebase_conflict(tmp_path, (a, b))
    assert mod.main([str(repo)]) == 0
    text = (repo / "MEMORY" / "full_history_ai.md").read_text()
    assert text == AI_BASE + a + b
    assert [x["issue"] for x in _blocks(text)[1:]] == [1, 2, 3, 4]


def test_a_decision_trailer_still_survives(tmp_path: Path, mod) -> None:
    """#65's shape through the new path: a recorded decision on one side, so
    only `followups: []` is hoisted, and nothing may be duplicated or lost."""
    a = _ai_block("A", 306, "A suite").replace("decisions_made: []", 'decisions_made: ["D-015"]')
    b = _ai_block("B", 308, "B suite")
    repo = _rebase_conflict(tmp_path, (a, b))
    assert mod.main([str(repo)]) == 0
    text = (repo / "MEMORY" / "full_history_ai.md").read_text()
    assert text == AI_BASE + a + b
    assert _blocks(text)[1]["decisions_made"] == ["D-015"]


# ----------------------------------------------------------------------
# Refusals
# ----------------------------------------------------------------------


def test_an_entry_on_both_sides_after_they_diverge_is_refused(mod) -> None:
    """If the rebuilt sides still share a whole entry after the point where
    they diverge, one side changed something above it -- keeping "both" would
    write that entry twice. Hand-built, because git merges most such edits
    cleanly on its own; this pins the refusal, not how often git produces it."""
    old = _ai_block("old", 10, "s")
    text = (
        AI_BASE
        + "\n---\n<<<<<<< HEAD\nsession: X-edited\n=======\nsession: X\n>>>>>>> abc (B)\n"
        + "issue: 9\ndecisions_made: []\nfollowups: []\n---\n"
        + old
        + "\n---\n<<<<<<< HEAD\n"
        + _ai_block("A", 306, "A").removeprefix("\n---\n").rstrip("\n")
        + "\n=======\n"
        + _ai_block("B", 308, "B").removeprefix("\n---\n").rstrip("\n")
        + "\n>>>>>>> abc (B)\n"
    )
    with pytest.raises(RuntimeError, match="edited existing history"):
        mod.resolve_yaml(text)


def test_the_resolved_file_round_trips_through_git(tmp_path: Path, mod) -> None:
    """End to end: the rebase must be able to continue on the resolved file."""
    a = _ai_block("A", 306, "A suite", extra="duration_min: 10\n")
    b = _ai_block("B", 308, "B suite")
    repo = _rebase_conflict(tmp_path, (a, b))
    assert mod.main([str(repo)]) == 0
    _git(repo, "add", "MEMORY")
    cont = subprocess.run(
        ["git", "-c", "core.editor=true", "rebase", "--continue"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert cont.returncode == 0, cont.stderr
    assert _git(repo, "show", "HEAD:MEMORY/full_history_ai.md").stdout == AI_BASE + a + b
