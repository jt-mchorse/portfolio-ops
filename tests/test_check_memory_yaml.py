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
    proc = _run("--file", str(REPO_ROOT / "MEMORY" / "full_history_ai.md"))
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


def test_the_baseline_totals_the_measured_74() -> None:
    """The number in #66, re-measured on 2026-08-26 against 953 blocks. If a
    retro-fix lands, this test is the one that should be updated deliberately."""
    assert sum(load_baseline().values()) == 74


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
