"""`resolve_memory_conflict.py` against conflicts produced by real `git rebase` (#65).

`tests/test_resolve_memory_conflict.py` opens with "Fixtures here are hand-rolled
minimal shapes — no real repo state required." That is exactly what hid this
defect: a hand-rolled fixture is written to match the shape the code expects, so
it can never discover a shape git actually produces.

Git hoists the two blocks' **common suffix** out of the conflict region, and it
does so line by line. `resolve_yaml` hardcoded the reattached trailer as
`decisions_made: []` + `followups: []`, which is the whole trailer only when
*both* sessions recorded nothing. When one recorded a decision, only
`followups: []` is common; `decisions_made:` differs and stays inside the region
attached to block_a — so appending the hardcoded pair produced a duplicate key::

    session: A
    decisions_made: [D-015]      <- what the session recorded
    decisions_made: []           <- fabricated by the resolver
    followups: []

`yaml.safe_load` keeps the LAST duplicate, so the recorded decision silently
vanished while the tool printed `resolved:` and exited 0. Measured across the
four cases below, three were malformed; the sound one was the both-empty
control. Of the ten session entries written the night this was found, seven had
a non-empty trailer — the tool failed precisely on the entries worth writing
down.

Every case here is built by `git init` + two branches + `git rebase`, so the
conflict text is whatever git really emits.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "resolve_memory_conflict.py"

BASE_BLOCK = "---\nsession: base\nfocus: base\ndecisions_made: []\nfollowups: []\n---\n"

EMPTY_TRAILER = "decisions_made: []\nfollowups: []"
DECISION_TRAILER = "decisions_made: [D-015]\nfollowups: []"
OTHER_DECISION_TRAILER = "decisions_made: [D-010]\nfollowups: []"
FOLLOWUP_TRAILER = "decisions_made: []\nfollowups: [#107]"


def _load_module():
    spec = importlib.util.spec_from_file_location("resolve_memory_conflict", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )


def _make_conflict(tmp_path: Path, trailer_a: str, trailer_b: str) -> Path:
    """Build a real append-only rebase conflict. Returns the repo path."""
    repo = tmp_path
    (repo / "MEMORY").mkdir(parents=True, exist_ok=True)
    hist = repo / "MEMORY" / "full_history_ai.md"

    _git(repo, "init", "-q", "-b", "main", ".")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")

    hist.write_text("# history\n\n" + BASE_BLOCK, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "checkout", "-qb", "branch-a")
    hist.write_text(
        hist.read_text(encoding="utf-8")
        + f"\n---\nsession: A\nfocus: aaa\n{trailer_a}\n---\n",
        encoding="utf-8",
    )
    _git(repo, "commit", "-qam", "A")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-qb", "branch-b")
    hist.write_text(
        hist.read_text(encoding="utf-8")
        + f"\n---\nsession: B\nfocus: bbb\n{trailer_b}\n---\n",
        encoding="utf-8",
    )
    _git(repo, "commit", "-qam", "B")

    _git(repo, "rebase", "branch-a")
    assert "<<<<<<<" in hist.read_text(encoding="utf-8"), (
        "expected git to produce a conflict; the fixture no longer reproduces "
        "the append-only shape this tool exists for"
    )
    return repo


# (label, trailer_a, trailer_b). The first row is the control: the only shape
# the tool was originally written against.
CASES = [
    ("both empty (control)", EMPTY_TRAILER, EMPTY_TRAILER),
    ("A records a decision", DECISION_TRAILER, EMPTY_TRAILER),
    ("B has a followup", EMPTY_TRAILER, FOLLOWUP_TRAILER),
    ("both record decisions", DECISION_TRAILER, OTHER_DECISION_TRAILER),
]


def test_the_table_covers_more_than_the_control() -> None:
    assert len(CASES) >= 4
    non_empty = [c for c in CASES if EMPTY_TRAILER not in (c[1], c[2])]
    assert non_empty, "at least one case where NEITHER side is the empty trailer"


@pytest.mark.parametrize(("label", "ta", "tb"), CASES, ids=[c[0] for c in CASES])
def test_every_block_keeps_exactly_one_trailer(
    tmp_path: Path, mod, label: str, ta: str, tb: str
) -> None:
    repo = _make_conflict(tmp_path, ta, tb)
    assert mod.main([str(repo)]) == 0

    text = (repo / "MEMORY" / "full_history_ai.md").read_text(encoding="utf-8")
    assert "<<<<<<<" not in text
    for block in text.split("\n---\n"):
        if "session:" not in block:
            continue
        assert block.count("decisions_made:") == 1, block
        assert block.count("followups:") == 1, block


# The followup case is excluded from the YAML round-trip below, and the reason
# is a SEPARATE pre-existing defect rather than anything this fix does: `#`
# begins a comment in YAML, so `followups: [#107]` is `followups: [` plus a
# comment — an unterminated flow sequence that fails to load. Measured across
# the portfolio while writing this file: 74 of 936 session blocks fail
# `yaml.safe_load`, 71 of them for exactly this reason, in all thirteen repos.
# Filed as portfolio-ops#66. Excluded here rather than papered over, so this
# file does not quietly assert that the convention is fine.
YAML_LOADABLE_CASES = [c for c in CASES if "#" not in c[1] + c[2]]


@pytest.mark.parametrize(
    ("label", "ta", "tb"), YAML_LOADABLE_CASES, ids=[c[0] for c in YAML_LOADABLE_CASES]
)
def test_every_block_round_trips_through_a_yaml_loader(
    tmp_path: Path, mod, label: str, ta: str, tb: str
) -> None:
    """The defect was invisible to a shape check that only counted `---`: the
    file parsed, and `yaml.safe_load` quietly dropped the duplicate."""
    repo = _make_conflict(tmp_path, ta, tb)
    assert mod.main([str(repo)]) == 0

    text = (repo / "MEMORY" / "full_history_ai.md").read_text(encoding="utf-8")
    sessions = {}
    for block in text.split("\n---\n"):
        if "session:" not in block:
            continue
        loaded = yaml.safe_load(block)
        sessions[loaded["session"]] = loaded
    assert set(sessions) == {"base", "A", "B"}


def test_the_excluded_case_is_excluded_for_the_documented_reason() -> None:
    """Pin why `B has a followup` is not in the round-trip list, so the
    exclusion cannot quietly widen. If portfolio-ops#66 changes the convention,
    this fails and the exclusion goes away with it."""
    assert len(YAML_LOADABLE_CASES) == len(CASES) - 1
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load("followups: [#107]")


def test_a_recorded_decision_survives_verbatim(tmp_path: Path, mod) -> None:
    """The data-loss assertion, stated directly.

    Before the fix this read `[]` — the fabricated duplicate won, and the
    session's link to the decision it made was gone with no error.
    """
    repo = _make_conflict(tmp_path, DECISION_TRAILER, EMPTY_TRAILER)
    assert mod.main([str(repo)]) == 0

    text = (repo / "MEMORY" / "full_history_ai.md").read_text(encoding="utf-8")
    block = next(b for b in text.split("\n---\n") if "session: A" in b)
    assert yaml.safe_load(block)["decisions_made"] == ["D-015"]


def test_both_sides_decisions_survive(tmp_path: Path, mod) -> None:
    repo = _make_conflict(tmp_path, DECISION_TRAILER, OTHER_DECISION_TRAILER)
    assert mod.main([str(repo)]) == 0

    text = (repo / "MEMORY" / "full_history_ai.md").read_text(encoding="utf-8")
    by_session = {
        yaml.safe_load(b)["session"]: yaml.safe_load(b)
        for b in text.split("\n---\n")
        if "session:" in b
    }
    assert by_session["A"]["decisions_made"] == ["D-015"]
    assert by_session["B"]["decisions_made"] == ["D-010"]


def test_a_followup_survives(tmp_path: Path, mod) -> None:
    repo = _make_conflict(tmp_path, EMPTY_TRAILER, FOLLOWUP_TRAILER)
    assert mod.main([str(repo)]) == 0

    text = (repo / "MEMORY" / "full_history_ai.md").read_text(encoding="utf-8")
    block = next(b for b in text.split("\n---\n") if "session: B" in b)
    # `#107` is a YAML comment character, so the value loads as None — that is
    # pre-existing and not what this test is about. Assert on the text.
    assert "followups: [#107]" in block


def test_the_control_output_is_unchanged(tmp_path: Path, mod) -> None:
    """The shape the tool always handled must resolve byte-identically, or every
    previously-resolved file would have to be re-checked."""
    repo = _make_conflict(tmp_path, EMPTY_TRAILER, EMPTY_TRAILER)
    assert mod.main([str(repo)]) == 0

    text = (repo / "MEMORY" / "full_history_ai.md").read_text(encoding="utf-8")
    assert text == (
        "# history\n\n"
        "---\nsession: base\nfocus: base\ndecisions_made: []\nfollowups: []\n---\n\n"
        "---\nsession: A\nfocus: aaa\ndecisions_made: []\nfollowups: []\n---\n\n"
        "---\nsession: B\nfocus: bbb\ndecisions_made: []\nfollowups: []\n---\n"
    )


def test_the_shape_guard_refuses_to_write_a_duplicated_key(tmp_path: Path, mod) -> None:
    """The guard is worth more than the fix: it turns a plausible-looking file
    that silently lost data into a non-zero exit.

    Driven through `check_block_shape` directly, because the resolver no longer
    produces this shape — which is the point.
    """
    bad = (
        "---\nsession: A\nfocus: aaa\n"
        "decisions_made: [D-015]\ndecisions_made: []\nfollowups: []\n---\n"
    )
    with pytest.raises(RuntimeError, match="decisions_made"):
        mod.check_block_shape(bad, Path("MEMORY/full_history_ai.md"))


def test_the_shape_guard_passes_a_healthy_file(tmp_path: Path, mod) -> None:
    """Control for the guard: without this, a guard that raised on everything
    would satisfy the test above."""
    good = (
        "---\nsession: A\nfocus: aaa\ndecisions_made: [D-015]\nfollowups: []\n---\n\n"
        "---\nsession: B\nfocus: bbb\ndecisions_made: []\nfollowups: []\n---\n"
    )
    mod.check_block_shape(good, Path("MEMORY/full_history_ai.md"))


def test_the_markdown_path_still_works_on_a_real_conflict(tmp_path: Path, mod) -> None:
    """`resolve_md` has no trailer to munge, so the same class should not apply —
    confirmed against a real conflict rather than assumed."""
    repo = tmp_path
    (repo / "MEMORY").mkdir(parents=True, exist_ok=True)
    hist = repo / "MEMORY" / "full_history_human.md"

    _git(repo, "init", "-q", "-b", "main", ".")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    hist.write_text("# history\n\n## base\n\nbase text.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "checkout", "-qb", "branch-a")
    hist.write_text(hist.read_text(encoding="utf-8") + "\n## A\n\naaa.\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "A")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-qb", "branch-b")
    hist.write_text(hist.read_text(encoding="utf-8") + "\n## B\n\nbbb.\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "B")
    _git(repo, "rebase", "branch-a")

    assert "<<<<<<<" in hist.read_text(encoding="utf-8")
    assert mod.main([str(repo)]) == 0

    text = hist.read_text(encoding="utf-8")
    assert "<<<<<<<" not in text
    assert "## A" in text and "## B" in text and "## base" in text
