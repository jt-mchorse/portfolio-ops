"""The unparseable-MEMORY-block ratchet (#66).

`#` begins a comment in YAML, so `followups: [#107]` is `followups: [` followed
by a comment -- an unterminated flow sequence, and the *whole* session block
fails `yaml.safe_load`. Measured across all thirteen repos on 2026-08-26:
**74 of 953 blocks** fail, and **71 of the 74 are that one spelling**, present in
every repo across the whole history.

`COWORK_HANDOFF.md` §3 calls this file "AI-optimized ... for fast machine
parsing", so 8% of the corpus being unloadable defeats the field's reason for
existing -- the first time anything actually parses it.

**These tests are about the ratchet, not about zero.** The checker compares each
repo against a committed baseline and fails only when a count *grows*. That shape
is deliberate: `MEMORY/` is append-only by rule (§10), and whether a mechanical
quote-insertion counts as rewriting history is JT's call (#66). Freezing the
count is how that call stays unforced -- and it is the same lesson `#65`'s
follow-up recorded, that a guard refusing to operate on already-damaged files is
useless on exactly the files that need it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_memory_yaml.py"
BASELINE = REPO_ROOT / "scripts" / "memory_yaml_baseline.json"

pytest.importorskip("yaml")


def _load_module():
    """Import scripts/check_memory_yaml.py by path.

    Same shape `test_audit_phase_a.py` uses, and for the same reason: `scripts/`
    is not a package, so `from scripts.check_memory_yaml import ...` resolves
    only when the repo root happens to be on `sys.path`. It did locally and did
    not on CI (`ModuleNotFoundError: No module named 'scripts'`), which is
    exactly the sort of import that works on one machine and not another.
    """
    spec = importlib.util.spec_from_file_location("check_memory_yaml", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MODULE = _load_module()
count_unparseable = _MODULE.count_unparseable
load_baseline = _MODULE.load_baseline


def _block(followups: str, session: str = "2026-01-01T00:00Z") -> str:
    return f"""---
session: {session}
issue: 1
focus: a_thing
decisions_made: []
followups: {followups}
---
"""


# ----------------------------------------------------------------------
# The defect itself
# ----------------------------------------------------------------------


def test_an_unquoted_hash_reference_makes_the_whole_block_unparseable() -> None:
    bad, total, reasons = count_unparseable(_block("[#107]"))
    assert (bad, total) == (1, 1)
    assert "flow node" in reasons[0] or "flow sequence" in reasons[0]


@pytest.mark.parametrize(
    "followups",
    ["[#107]", "[#1, #2]", "[#66]", "[ #107 ]", "[leh#212, #66]", "[#107, leh#212]"],
)
def test_a_hash_after_whitespace_or_a_bracket_breaks_the_block(followups: str) -> None:
    """The precise rule, which is narrower than "`#` breaks YAML"."""
    bad, total, _ = count_unparseable(_block(followups))
    assert (bad, total) == (1, 1), followups


@pytest.mark.parametrize(
    "followups",
    ["[leh#212]", "[csl#165, aiapp#102]", "[a#1]"],
)
def test_the_cross_repo_spelling_was_never_broken(followups: str) -> None:
    """Correction to #66's option analysis, measured (see the issue comment).

    YAML starts a comment at `#` only when it follows whitespace or begins the
    token. In `leh#212` the `#` follows `h`, so the whole thing is a plain
    scalar and the block parses. The issue argued for Option 1 partly because
    Option 2 ("drop the `#`") "loses the cross-repo form" -- but that form was
    never at risk. Option 1 is still right, for a different reason, which
    `test_the_d010_form_is_a_rule_that_can_be_followed_without_thinking`
    states.
    """
    bad, total, _ = count_unparseable(_block(followups))
    assert (bad, total) == (0, 1), followups


@pytest.mark.parametrize(
    "followups",
    ['["#107"]', '["#1", "#2"]', '["leh#212"]', '["csl#165", "aiapp#102"]', "[]"],
)
def test_the_d010_quoted_form_parses(followups: str) -> None:
    bad, total, _ = count_unparseable(_block(followups))
    assert (bad, total) == (0, 1), followups


def test_the_d010_form_is_a_rule_that_can_be_followed_without_thinking() -> None:
    """Why quote *everything* rather than only the bare-`#` items.

    The alternative rule is "quote a followup only when it starts with `#`",
    which is correct and which nobody will remember at 3am. "Quote every item"
    is one rule with no exceptions, and it is a superset -- so a session that
    applies it can never be wrong, whichever spelling it reaches for.
    """
    for spelling in ["#107", "leh#212", "csl#165", "1"]:
        bad, _, _ = count_unparseable(_block(f'["{spelling}"]'))
        assert bad == 0, spelling


def test_a_block_without_a_session_key_is_not_counted() -> None:
    """The file's prose header and any stray fence must not inflate the total."""
    assert count_unparseable("# Full history\n\nSome prose.\n")[1] == 0


# ----------------------------------------------------------------------
# The ratchet
# ----------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_this_repo_is_within_its_baseline() -> None:
    # `--repo` as CI's ratchet step passes it (#102): without it the name came
    # from the checkout directory, and a worktree not named portfolio-ops failed.
    proc = _run(
        "--file",
        str(REPO_ROOT / "MEMORY" / "full_history_ai.md"),
        "--repo",
        "portfolio-ops",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_a_file_at_its_baseline_passes(tmp_path: Path) -> None:
    baseline = load_baseline()["portfolio-ops"]
    path = tmp_path / "full_history_ai.md"
    path.write_text("".join(_block("[#1]", f"2026-01-{i + 1:02d}") for i in range(baseline)))
    proc = _run("--file", str(path), "--repo", "portfolio-ops")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_one_more_bad_block_than_the_baseline_fails(tmp_path: Path) -> None:
    baseline = load_baseline()["portfolio-ops"]
    path = tmp_path / "full_history_ai.md"
    path.write_text("".join(_block("[#1]", f"2026-01-{i + 1:02d}") for i in range(baseline + 1)))
    proc = _run("--file", str(path), "--repo", "portfolio-ops")
    assert proc.returncode == 1
    assert "REGRESSED" in proc.stdout
    assert "D-010" in proc.stderr
    assert 'followups: ["#107"]' in proc.stderr


def test_fewer_bad_blocks_than_the_baseline_passes(tmp_path: Path) -> None:
    """A ratchet loosens, never tightens on its own. A retro-fix must not have to
    regenerate the baseline in the same commit to stay green."""
    path = tmp_path / "full_history_ai.md"
    path.write_text(_block("[]"))
    proc = _run("--file", str(path), "--repo", "portfolio-ops")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_an_unknown_repo_gets_no_allowance(tmp_path: Path) -> None:
    """A repo added later starts at zero, so the convention applies to it from
    its first block -- the baseline is an amnesty for existing history, not a
    blanket one."""
    path = tmp_path / "full_history_ai.md"
    path.write_text(_block("[#1]"))
    proc = _run("--file", str(path), "--repo", "brand-new-repo")
    assert proc.returncode == 1


def test_a_missing_file_is_exit_2_not_a_silent_pass(tmp_path: Path) -> None:
    proc = _run("--file", str(tmp_path / "nope.md"), "--repo", "portfolio-ops")
    assert proc.returncode == 2
    assert "::error::" in proc.stderr


# ----------------------------------------------------------------------
# The baseline is a frozen measurement, not a moving target
# ----------------------------------------------------------------------


def test_the_baseline_covers_every_portfolio_repo() -> None:
    baseline = load_baseline()
    expected = {
        "agent-orchestration-platform",
        "ai-app-integration-tests",
        "chunking-strategies-lab",
        "embedding-model-shootout",
        "llm-cost-optimizer",
        "llm-eval-harness",
        "mcp-server-cookbook",
        "nextjs-streaming-ai-patterns",
        "portfolio-ops",
        "prompt-regression-suite",
        "python-async-llm-pipelines",
        "rag-production-kit",
        "vector-search-at-scale",
    }
    assert set(baseline) == expected


def test_the_baseline_totals_the_measured_74_plus_107s_29() -> None:
    """The number in #66, re-measured on 2026-08-26 against 953 blocks, plus
    the 29 glued or duplicate-key blocks #107's rule newly counts on the 13
    origin/main files of 2026-10-21 (each repo raised by exactly its own share,
    so no growth from before #107 was folded in). If a retro-fix lands, this
    test is the one that should be updated deliberately."""
    assert sum(load_baseline().values()) == 74 + 29


def test_the_baseline_is_not_vacuous() -> None:
    """A baseline of all-zeros would make the ratchet a gate, and a baseline of
    huge numbers would make it useless. Both are real failure modes for a
    committed allowance file."""
    values = list(load_baseline().values())
    assert all(v >= 0 for v in values)
    assert any(v > 0 for v in values), "an all-zero baseline is a gate, not a ratchet"
    assert max(values) <= 20, "an allowance this large would not catch a regression"


def test_the_baseline_explains_itself() -> None:
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert "RATCHET" in data["_comment"]
    assert "#66" in data["_comment"]


# ----------------------------------------------------------------------
# Orphaned fragments (#97)
# ----------------------------------------------------------------------

ORPHAN_NO_SESSION = '---\n  suite: "B suite"\ndecisions_made: []\nmeasured: "m"\nfollowups: []\n---\n'
ORPHAN_TRAILER_ONLY = "---\nfollowups: []\n---\n"


def test_an_orphaned_tail_without_the_session_substring_is_counted() -> None:
    """The shape #95's per-hunk resolution left in aiapp: before #97 a chunk
    counted only if `session:` appeared anywhere in it, so this read as clean."""
    for orphan in (ORPHAN_NO_SESSION, ORPHAN_TRAILER_ONLY):
        bad, total, reasons = count_unparseable(_block("[]") + "\n" + orphan)
        assert (bad, total) == (1, 2), orphan
        assert reasons


def test_an_orphan_that_loads_as_a_mapping_is_still_not_a_session() -> None:
    """`followups: []` alone is valid YAML; it is still no session entry."""
    bad, _, reasons = count_unparseable(_block("[]") + "\n" + ORPHAN_TRAILER_ONLY)
    assert bad == 1
    assert "no session key" in reasons[0]


def test_an_orphan_carrying_context_for_next_session_counts_once() -> None:
    """The orphans the old substring rule did see must not be double-counted."""
    orphan = '---\n  suite: "x"\ncontext_for_next_session:\n  - A\nfollowups: []\n---\n'
    assert count_unparseable(_block("[]") + "\n" + orphan)[:2] == (1, 2)


def test_a_comment_only_chunk_and_the_prose_header_are_not_blocks() -> None:
    text = "# Full history\n\nProse header.\n\n" + _block("[]") + "\n---\n# a note\n\n---\n"
    assert count_unparseable(text)[:2] == (0, 1)


def test_a_fence_less_session_entry_is_still_counted() -> None:
    assert count_unparseable("session: x\nfollowups: [#1]\n")[:2] == (1, 1)


# ----------------------------------------------------------------------
# The repo name `--file` implies (#102)
# ----------------------------------------------------------------------
#
# The name keys the baseline. Taken from the checkout directory, a worktree
# at /tmp/w/hunt2-ops was repo `hunt2-ops`: no baseline, allowance 0, and a
# false REGRESSED on a green main. These copy this repo's own MEMORY files
# into such a checkout, so the baseline they meet is the real one.

ODD_NAME = "hunt2-ops"
ORIGIN = "https://github.com/jt-mchorse/portfolio-ops.git"


def _checkout(
    tmp_path: Path, name: str = ODD_NAME, origin: str | None = ORIGIN
) -> Path:
    """A copy of this repo's MEMORY/ in a checkout named `name`."""
    root = tmp_path / name
    (root / "MEMORY").mkdir(parents=True)
    for f in ("full_history_ai.md", "core_decisions_ai.md"):
        (root / "MEMORY" / f).write_bytes((REPO_ROOT / "MEMORY" / f).read_bytes())
    if origin is not None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "remote", "add", "origin", origin], check=True
        )
    return root


def _run_in(
    root: Path, *args: str, kind: str = "history"
) -> subprocess.CompletedProcess[str]:
    name = "full_history_ai.md" if kind == "history" else "core_decisions_ai.md"
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--kind",
            kind,
            "--file",
            str(root / "MEMORY" / name),
            *args,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        # No walking up into whatever repo holds tmp_path.
        env={**os.environ, "GIT_CEILING_DIRECTORIES": str(root.parent)},
        check=False,
    )


@pytest.mark.parametrize("kind", ["history", "decisions"])
def test_an_oddly_named_checkout_of_this_repo_is_within_its_baseline(
    tmp_path: Path, kind: str
) -> None:
    proc = _run_in(_checkout(tmp_path), kind=kind)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.startswith("portfolio-ops "), proc.stdout


@pytest.mark.parametrize(
    "origin",
    [
        "https://github.com/jt-mchorse/portfolio-ops.git",
        "https://github.com/jt-mchorse/portfolio-ops",
        "https://github.com/jt-mchorse/portfolio-ops/",
        "git@github.com:jt-mchorse/portfolio-ops.git",
        "ssh://git@github.com/jt-mchorse/portfolio-ops.git",
        "/Users/someone/projects/portfolio/portfolio-ops",
    ],
)
def test_every_origin_url_shape_names_the_repo(tmp_path: Path, origin: str) -> None:
    proc = _run_in(_checkout(tmp_path, origin=origin))
    assert proc.stdout.startswith("portfolio-ops "), proc.stdout + proc.stderr


def test_a_file_outside_any_checkout_falls_back_to_the_directory_name(
    tmp_path: Path,
) -> None:
    proc = _run_in(_checkout(tmp_path, origin=None))
    assert proc.stdout.startswith(f"{ODD_NAME} "), proc.stdout + proc.stderr


def test_a_checkout_with_no_origin_falls_back_to_the_directory_name(
    tmp_path: Path,
) -> None:
    root = _checkout(tmp_path, origin=None)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    proc = _run_in(root)
    assert proc.stdout.startswith(f"{ODD_NAME} "), proc.stdout + proc.stderr


def test_an_explicit_repo_still_wins_over_the_origin(tmp_path: Path) -> None:
    proc = _run_in(_checkout(tmp_path), "--repo", "llm-eval-harness")
    assert proc.stdout.startswith("llm-eval-harness "), proc.stdout + proc.stderr
