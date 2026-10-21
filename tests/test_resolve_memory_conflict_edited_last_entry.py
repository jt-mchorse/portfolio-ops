"""`resolve_memory_conflict.py` when a side edited the LAST existing entry (#104).

Under git's default `merge` conflict style an edit to the last entry lands in
the same hunk as the two appended entries, with no base section to show it is
history. The rebuilt sides then diverge INSIDE that entry, its edited and
original versions differ, so no whole section is shared past the cut and the
#95 refusal does not fire: the resolver wrote the edited entry, then the
original again, at rc 0. diff3/zdiff3 already refused it (#90).

The conflict text alone cannot tell that shape from two new entries that share
a heading or `session:` line (two sessions in the same minute), which must keep
resolving. The merge base in git's index (stage 1) can, so the real-git arms
below use a real `git rebase`; the hand-built arms pin what happens without one.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "resolve_memory_conflict.py"

AI_BASE = "# Full history\n\n---\nsession: base\nfocus: base\ndecisions_made: []\nfollowups: []\n---\n"
MD_BASE = "# History\n\n## base\n\nbase prose.\n"
MD_A = "\n## A\n\nA body.\n"
MD_B = "\n## B\n\nB body.\n"


def _ai_block(session: str, issue: int) -> str:
    return (
        f"\n---\nsession: {session}\nissue: {issue}\nfocus: F{issue}\n"
        "decisions_made: []\nfollowups: []\n---\n"
    )


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


def _rebase(
    repo: Path,
    base: tuple[str, str],
    main: tuple[str, str],
    side: tuple[str, str],
    *,
    style: str = "merge",
) -> Path:
    """Commit `base` (ai, md); main commits `main`, the branch `side`; rebase it."""
    mem = repo / "MEMORY"
    mem.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main", ".")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "merge.conflictStyle", style)

    def write(files: tuple[str, str]) -> None:
        (mem / "full_history_ai.md").write_text(files[0])
        (mem / "full_history_human.md").write_text(files[1])

    write(base)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "side")
    write(side)
    _git(repo, "commit", "-qam", "B")
    _git(repo, "checkout", "-q", "main")
    write(main)
    _git(repo, "commit", "-qam", "A")
    _git(repo, "checkout", "-q", "side")
    _git(repo, "rebase", "main")
    return repo


def _snapshot(repo: Path) -> tuple[bytes, bytes]:
    mem = repo / "MEMORY"
    return (mem / "full_history_ai.md").read_bytes(), (mem / "full_history_human.md").read_bytes()


def _conflicted(repo: Path, name: str) -> bool:
    return "<<<<<<< " in (repo / "MEMORY" / name).read_text()


def _assert_refused(repo: Path, mod, capsys) -> None:
    before = _snapshot(repo)
    assert mod.main([str(repo)]) == 1
    assert "edited existing history" in capsys.readouterr().err
    assert _snapshot(repo) == before


# ----------------------------------------------------------------------
# The defect: refused, nothing written
# ----------------------------------------------------------------------


def test_the_issue_repro_is_refused(tmp_path: Path, mod, capsys) -> None:
    """main edited the last prose entry and both sides appended after it. Was
    rc 0 with `## base` written twice, the original after the edited one."""
    repo = _rebase(
        tmp_path,
        (AI_BASE, MD_BASE),
        (AI_BASE, MD_BASE.replace("base prose.", "base prose, edited.") + MD_A),
        (AI_BASE, MD_BASE + MD_B),
    )
    assert _conflicted(repo, "full_history_human.md")
    _assert_refused(repo, mod, capsys)


def test_an_edited_last_heading_is_refused(tmp_path: Path, mod, capsys) -> None:
    """The edit is to the heading itself, so the two tails do not even open
    with the same line; only the merge base shows `## base` is history."""
    repo = _rebase(
        tmp_path,
        (AI_BASE, MD_BASE),
        (AI_BASE, MD_BASE.replace("## base", "## base (renamed)") + MD_A),
        (AI_BASE, MD_BASE + MD_B),
    )
    assert _conflicted(repo, "full_history_human.md")
    _assert_refused(repo, mod, capsys)


def test_both_sides_editing_the_last_entry_is_refused(tmp_path: Path, mod, capsys) -> None:
    """Neither side keeps the original, so no tail section matches the base;
    the base's last entry is simply missing from the shared prefix."""
    repo = _rebase(
        tmp_path,
        (AI_BASE, MD_BASE),
        (AI_BASE, MD_BASE.replace("base prose.", "base prose, main.") + MD_A),
        (AI_BASE, MD_BASE.replace("base prose.", "base prose, side.") + MD_B),
    )
    assert _conflicted(repo, "full_history_human.md")
    _assert_refused(repo, mod, capsys)


# Without a stage-1 base (hand-built text, or a path already staged) the shape
# is ambiguous and refused.

ISSUE_CONFLICT = (
    "# History\n\n## base\n\n<<<<<<< HEAD\nbase prose, edited.\n\n## A\n\nA body.\n"
    "=======\nbase prose.\n\n## B\n\nB body.\n>>>>>>> f01e01a (B)\n"
)


def test_without_a_base_the_issue_text_is_refused(mod) -> None:
    with pytest.raises(RuntimeError, match="no merge base"):
        mod.resolve_md(ISSUE_CONFLICT)


def _one_hunk(ours: str, theirs: str) -> str:
    """A single default-style hunk between two whole files, common lines outside."""
    o, t = ours.splitlines(keepends=True), theirs.splitlines(keepends=True)
    p = 0
    while p < min(len(o), len(t)) and o[p] == t[p]:
        p += 1
    q = 0
    while q < min(len(o), len(t)) - p and o[-1 - q] == t[-1 - q]:
        q += 1
    mid_o, mid_t = o[p : len(o) - q], t[p : len(t) - q]
    return "".join(
        o[:p] + ["<<<<<<< HEAD\n"] + mid_o + ["=======\n"] + mid_t + [">>>>>>> abc (B)\n"] + o[len(o) - q :]
    )


def test_without_a_base_an_edited_last_yaml_block_is_refused(mod) -> None:
    """The YAML file's version. git's real merge realigns the shared `---`
    trailer and merges such an edit cleanly, so this shape is hand-built."""
    edited = AI_BASE.replace("followups: []", 'followups: ["#1"]')
    text = _one_hunk(edited + _ai_block("A", 306), AI_BASE + _ai_block("B", 308))
    assert text.count("<<<<<<< ") == 1 and "session: base\n" in text.split("<<<<<<<")[0]
    with pytest.raises(RuntimeError, match="session: base"):
        mod.resolve_yaml(text)


def test_without_a_git_index_main_refuses_and_writes_nothing(tmp_path: Path, mod, capsys) -> None:
    mem = tmp_path / "MEMORY"
    mem.mkdir()
    (mem / "full_history_ai.md").write_text(AI_BASE)
    (mem / "full_history_human.md").write_text(ISSUE_CONFLICT)
    assert mod.main([str(tmp_path)]) == 1
    assert "no merge base" in capsys.readouterr().err
    assert (mem / "full_history_human.md").read_text() == ISSUE_CONFLICT


# ----------------------------------------------------------------------
# Controls: what the refusal must not catch
# ----------------------------------------------------------------------


def test_given_its_base_the_same_text_with_nothing_edited_resolves(mod) -> None:
    """Control: the issue's conflict text is a legitimate append when the base
    really was `# History` alone -- two new entries both headed `## base`."""
    out = mod.resolve_md(ISSUE_CONFLICT, base="# History\n")
    assert out == (
        "# History\n\n## base\n\nbase prose, edited.\n\n## A\n\nA body.\n"
        "\n## base\n\nbase prose.\n\n## B\n\nB body.\n"
    )


def test_two_new_sections_with_the_same_heading_resolve(tmp_path: Path, mod) -> None:
    """Control: two sessions on the same day, same heading, real git."""
    a = "\n## 2026-10-21\n\nA body.\n"
    b = "\n## 2026-10-21\n\nB body.\n"
    repo = _rebase(tmp_path, (AI_BASE, MD_BASE), (AI_BASE, MD_BASE + a), (AI_BASE, MD_BASE + b))
    assert _conflicted(repo, "full_history_human.md")
    assert mod.main([str(repo)]) == 0
    assert (repo / "MEMORY" / "full_history_human.md").read_text() == MD_BASE + a + b


def test_two_new_blocks_with_the_same_session_line_resolve(tmp_path: Path, mod) -> None:
    """Control: the same minute in the YAML file, real git."""
    a = _ai_block("2026-10-21T07:15Z", 306)
    b = _ai_block("2026-10-21T07:15Z", 308)
    repo = _rebase(tmp_path, (AI_BASE, MD_BASE), (AI_BASE + a, MD_BASE), (AI_BASE + b, MD_BASE))
    assert _conflicted(repo, "full_history_ai.md")
    assert mod.main([str(repo)]) == 0
    assert (repo / "MEMORY" / "full_history_ai.md").read_text() == AI_BASE + a + b


def test_this_repos_real_memory_files_still_resolve(tmp_path: Path, mod) -> None:
    """Control: the base check against the real files' last entries, not a
    fixture's -- a false refusal here would block every real rebase."""
    ai = (REPO_ROOT / "MEMORY" / "full_history_ai.md").read_text()
    md = (REPO_ROOT / "MEMORY" / "full_history_human.md").read_text()
    a_ai, b_ai = _ai_block("2026-10-21T07:15Z", 306), _ai_block("2026-10-21T07:15Z", 308)
    a_md, b_md = "\n## 2026-10-21 — A\n\nA body.\n", "\n## 2026-10-21 — B\n\nB body.\n"
    repo = _rebase(tmp_path, (ai, md), (ai + a_ai, md + a_md), (ai + b_ai, md + b_md))
    assert _conflicted(repo, "full_history_ai.md") and _conflicted(repo, "full_history_human.md")
    assert mod.main([str(repo)]) == 0
    assert (repo / "MEMORY" / "full_history_ai.md").read_text() == ai + a_ai + b_ai
    assert (repo / "MEMORY" / "full_history_human.md").read_text() == md + a_md + b_md


def test_the_merge_base_is_read_from_the_index(tmp_path: Path, mod) -> None:
    """Control: stage 1 is there mid-rebase, and absent outside a repo."""
    repo = _rebase(
        tmp_path / "r",
        (AI_BASE, MD_BASE),
        (AI_BASE, MD_BASE + MD_A),
        (AI_BASE, MD_BASE + MD_B),
    )
    assert mod._merge_base(repo / "MEMORY" / "full_history_human.md") == MD_BASE
    loose = tmp_path / "loose"
    loose.mkdir()
    (loose / "full_history_human.md").write_text(MD_BASE)
    assert mod._merge_base(loose / "full_history_human.md") is None
