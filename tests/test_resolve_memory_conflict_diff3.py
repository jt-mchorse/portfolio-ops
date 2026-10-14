"""`resolve_memory_conflict.py` under `merge.conflictStyle=diff3` / `zdiff3` (#90).

The two-way regex had no base section. Under either style git writes a third
one, `||||||| <base label>`, between ours and `=======`, and the lazy
`(.*?)\\n=======` swallowed that marker line into block_a. The tool then wrote it
back into both MEMORY files, printed `resolved:` and exited 0 -- the file no
longer loaded as YAML. diff3 additionally hoists nothing, so each side is
already a closed `---` block and the separators the tool added put an empty
document between them.

Every conflict here comes from a real `git rebase` with the style pinned per
call, so the result does not depend on the developer's global git config.
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

STYLES = ["merge", "diff3", "zdiff3"]

# Defined here rather than read from the module, so the `merge` row stays a
# control that also passes against the pre-#90 script.
MARKER = re.compile(r"^(?:<{7}|\|{7}|={7}|>{7})(?: |$)", re.MULTILINE)


def _load_module():
    spec = importlib.util.spec_from_file_location("resolve_memory_conflict", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load_module()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )


def _block(session: str, decisions: str = "[]") -> str:
    return f"\n---\nsession: {session}\nfocus: f\ndecisions_made: {decisions}\nfollowups: []\n---\n"


def _make_conflict(repo: Path, style: str, edit_base: bool = False) -> Path:
    """Two branches append to both MEMORY files; rebase one onto the other.

    With `edit_base`, both branches also rewrite the base block's
    session line, differently, so the conflict is no longer append-only.
    """
    mem = repo / "MEMORY"
    mem.mkdir(parents=True, exist_ok=True)
    ai = mem / "full_history_ai.md"
    human = mem / "full_history_human.md"
    _git(repo, "init", "-q", "-b", "main", ".")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    ai.write_text("# history\n" + _block("base"), encoding="utf-8")
    human.write_text("# history\n\n## base\n\nbase text.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "checkout", "-qb", "branch-a")
    text = ai.read_text(encoding="utf-8")
    if edit_base:
        text = text.replace("session: base\n", "session: base-A\n", 1)
    ai.write_text(text + _block("A"), encoding="utf-8")
    human.write_text(human.read_text(encoding="utf-8") + "\n## A\n\naaa.\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "A")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-qb", "branch-b")
    text = ai.read_text(encoding="utf-8")
    if edit_base:
        text = text.replace("session: base\n", "session: base-B\n", 1)
    ai.write_text(text + _block("B", "[D-015]"), encoding="utf-8")
    human.write_text(human.read_text(encoding="utf-8") + "\n## B\n\nbbb.\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "B")

    _git(repo, "-c", f"merge.conflictStyle={style}", "rebase", "branch-a")
    assert "<<<<<<<" in ai.read_text(encoding="utf-8"), "fixture produced no conflict"
    if style != "merge":
        assert "|||||||" in ai.read_text(encoding="utf-8"), (
            f"{style} produced no base section; the fixture no longer exercises #90"
        )
    return repo


def _sessions(text: str) -> dict:
    return {
        loaded["session"]: loaded
        for loaded in (yaml.safe_load(b) for b in text.split("\n---\n") if "session:" in b)
    }


@pytest.mark.parametrize("style", STYLES)
def test_every_style_resolves_to_loadable_blocks(tmp_path: Path, mod, style: str) -> None:
    repo = _make_conflict(tmp_path, style)
    assert mod.main([str(repo)]) == 0

    ai = (repo / "MEMORY" / "full_history_ai.md").read_text(encoding="utf-8")
    human = (repo / "MEMORY" / "full_history_human.md").read_text(encoding="utf-8")
    for text in (ai, human):
        assert not MARKER.search(text), text
    sessions = _sessions(ai)
    assert set(sessions) == {"base", "A", "B"}
    assert sessions["B"]["decisions_made"] == ["D-015"]
    assert "## A" in human and "## B" in human


@pytest.mark.parametrize("style", ["diff3", "zdiff3"])
def test_a_three_way_style_resolves_byte_identically_to_the_default(
    tmp_path: Path, mod, style: str
) -> None:
    """The default style is the shape the tool was written against; the same two
    appends must produce the same files whatever the operator's git config,
    including no empty `---` document between blocks under diff3."""
    default = _make_conflict(tmp_path / "merge", "merge")
    other = _make_conflict(tmp_path / style, style)
    assert mod.main([str(default)]) == 0
    assert mod.main([str(other)]) == 0
    for name in ("full_history_ai.md", "full_history_human.md"):
        assert (other / "MEMORY" / name).read_bytes() == (
            default / "MEMORY" / name
        ).read_bytes(), name


def test_a_non_empty_base_is_refused_and_nothing_is_written(tmp_path: Path, mod, capsys) -> None:
    """A base with text means a side rewrote an existing entry. Keeping both
    sides would keep the old and the new version of it, so the tool must stop."""
    repo = _make_conflict(tmp_path, "diff3", edit_base=True)
    ai = repo / "MEMORY" / "full_history_ai.md"
    before = ai.read_bytes()

    assert mod.main([str(repo)]) == 1
    assert ai.read_bytes() == before
    assert "non-empty base" in capsys.readouterr().err


def test_an_empty_base_is_not_refused(mod) -> None:
    """Control for the refusal: an empty base section is the normal case."""
    text = "<<<<<<< HEAD\nA\n||||||| parent of abc (x)\n=======\nB\n>>>>>>> abc (x)\n"
    assert mod.resolve_md(text) == "A\n\nB\n"


def test_the_marker_guard_catches_a_shape_the_regex_does_not_know(
    tmp_path: Path, mod, capsys
) -> None:
    """The guard is independent of the regex: restore the pre-#90 two-way regex
    and the zdiff3 conflict must now exit 1 with the file untouched, instead of
    the `resolved:` + exit 0 the issue reported."""
    repo = _make_conflict(tmp_path, "zdiff3")
    ai = repo / "MEMORY" / "full_history_ai.md"
    before = ai.read_bytes()
    mod.CONFLICT = re.compile(
        r"<<<<<<< HEAD\n(.*?)\n()=======\n(.*?)\n>>>>>>> [^\n]*\n", re.DOTALL
    )

    assert mod.main([str(repo)]) == 1
    assert ai.read_bytes() == before
    assert "Conflict markers remain" in capsys.readouterr().err


def test_a_marker_shaped_line_already_in_the_prose_is_tolerated(tmp_path: Path, mod) -> None:
    """The guard compares against the file minus its conflicts, not against zero:
    a MEMORY file that documents the marker shape at a line start must still
    resolve (the #25 class)."""
    mem = tmp_path / "MEMORY"
    mem.mkdir()
    (mem / "full_history_ai.md").write_text("", encoding="utf-8")
    human = mem / "full_history_human.md"
    human.write_text(
        "## doc\n\n=======\n\n<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> abc (x)\n",
        encoding="utf-8",
    )
    assert mod.main([str(tmp_path)]) == 0
    assert human.read_text(encoding="utf-8") == "## doc\n\n=======\n\nA\n\nB\n"
