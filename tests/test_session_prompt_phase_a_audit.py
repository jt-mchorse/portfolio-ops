"""Lock the Phase A silent-rot audit step in SESSION_PROMPT.md.

`scripts/audit_phase_a.py` scans for six silent-rot fingerprints across
portfolio repos:

1. paired-failure (#19/#20)
2. stuck-registration (#19/#20)
3. stale-schedule (#19/#20)
4. phantom-ci (#27/#28)
5. missing-timeout (#35/#36)
6. missing-concurrency (#40/#41)

Issue #21 wired the audit into Phase A of the canonical session prompt as
an observational, non-blocking step that runs after the PR-review pass.

This file is the inverse-safety-net: if a future edit drops or breaks the
audit step in SESSION_PROMPT.md, pytest fails loudly with a specific message
naming what's missing. Mirrors the shape of
`tests/test_session_prompt_phase_a_loop.py` (which locks the PR-review loop).

Related: portfolio-ops#21 (audit wire-in), #46 (this lock's six-fingerprint
+ pyyaml-ensure extensions).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_PROMPT = REPO_ROOT / "session-runner" / "SESSION_PROMPT.md"
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_phase_a.py"

PORTFOLIO_REPOS = (
    "rag-production-kit",
    "agent-orchestration-platform",
    "llm-eval-harness",
    "prompt-regression-suite",
    "ai-app-integration-tests",
    "nextjs-streaming-ai-patterns",
    "python-async-llm-pipelines",
    "embedding-model-shootout",
    "chunking-strategies-lab",
    "llm-cost-optimizer",
    "vector-search-at-scale",
    "mcp-server-cookbook",
)
OPS_REPO = "portfolio-ops"
ALL_REPOS = PORTFOLIO_REPOS + (OPS_REPO,)

# The six canonical silent-rot fingerprints exposed by
# `scripts/audit_phase_a.py`. Order is the script's docstring order
# (paired-failure, stuck-registration, stale-schedule, phantom-ci,
# missing-timeout, missing-concurrency). When a seventh fingerprint
# lands, add it here AND update the SESSION_PROMPT.md audit step's
# description text — this list is the bridge between them.
FINGERPRINTS = (
    "paired-failure",
    "stuck-registration",
    "stale-schedule",
    "phantom-ci",
    "missing-timeout",
    "missing-concurrency",
)

# The audit step lives between the PR-review override note and the repo-pick
# step. We isolate that slice and assert on its contents. The slice runs from
# the "Silent-rot audit pass" header to the next top-level Phase A step.
AUDIT_SECTION_RE = re.compile(
    r"\*\*Silent-rot audit pass\*\*.*?(?=\n\d+\.\s+\*\*)",
    re.DOTALL,
)

# Audit-pass for-loop has the same `for r in <repos>; do` shape as the PR-review
# loop. We require the audit section to contain a for-loop with the full repo
# enumeration so a missed repo can't silently fall out of the scan.
FOR_LOOP_RE = re.compile(r"for\s+r\s+in\s+([^;]+);\s*do", re.MULTILINE)


@pytest.fixture(scope="module")
def prompt_text() -> str:
    return SESSION_PROMPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def audit_section(prompt_text: str) -> str:
    match = AUDIT_SECTION_RE.search(prompt_text)
    assert match is not None, (
        "Could not locate `**Silent-rot audit pass**` step in SESSION_PROMPT.md. "
        "Phase A audit loop was wired in via issue #21; if it has been "
        "restructured, update AUDIT_SECTION_RE in this test to match."
    )
    return match.group(0)


@pytest.fixture(scope="module")
def audit_loop_repos(audit_section: str) -> list[str]:
    match = FOR_LOOP_RE.search(audit_section)
    assert match is not None, (
        "Audit section in SESSION_PROMPT.md has no `for r in ...; do` loop. "
        "Phase A audit must iterate over all 13 repos; restore the loop or "
        "update this test if the iteration shape has deliberately changed."
    )
    return match.group(1).split()


def test_session_prompt_exists() -> None:
    assert SESSION_PROMPT.is_file(), f"SESSION_PROMPT.md missing at {SESSION_PROMPT}"


def test_audit_script_exists() -> None:
    assert AUDIT_SCRIPT.is_file(), (
        f"scripts/audit_phase_a.py missing at {AUDIT_SCRIPT}; Phase A audit "
        "step in SESSION_PROMPT.md references this script and would 404 at "
        "session-runtime if it disappears."
    )


def test_audit_section_references_script(audit_section: str) -> None:
    assert "scripts/audit_phase_a.py" in audit_section, (
        "Audit section in SESSION_PROMPT.md does not reference "
        "`scripts/audit_phase_a.py`. The wired-in step must name the script "
        "path explicitly so a session can copy-paste the command."
    )


def test_audit_section_uses_repo_flag(audit_section: str) -> None:
    assert "--repo" in audit_section, (
        "Audit invocation in SESSION_PROMPT.md must pass `--repo <name>` per "
        "audit_phase_a.py CLI contract; positional repo arg is not supported."
    )


def test_audit_section_documents_exit_codes(audit_section: str) -> None:
    for code_label in ("exit 0", "exit 1", "exit 2"):
        assert code_label in audit_section, (
            f"Audit section in SESSION_PROMPT.md must document `{code_label}` "
            "behavior (clean / findings / fetch-error). A session that doesn't "
            "know how to interpret exit codes will mis-handle real findings."
        )


def test_audit_section_marks_observational(audit_section: str) -> None:
    section_lower = audit_section.lower()
    assert any(token in section_lower for token in ("observational", "non-blocking", "do not auto")), (
        "Audit section must mark itself as observational / non-blocking. "
        "Without that framing a future session could treat findings as "
        "session-failing instead of reporting them in the Phase D summary."
    )


@pytest.mark.parametrize("repo", ALL_REPOS)
def test_audit_loop_includes_repo(audit_loop_repos: list[str], repo: str) -> None:
    assert repo in audit_loop_repos, (
        f"Phase A audit for-loop in SESSION_PROMPT.md is missing {repo!r}. "
        "Every repo on the same scheduled-merge cadence must also be in the "
        "audit loop, or its silent-rot fingerprints stay invisible."
    )


def test_audit_loop_has_no_unknown_repos(audit_loop_repos: list[str]) -> None:
    extras = set(audit_loop_repos) - set(ALL_REPOS)
    assert not extras, (
        f"Phase A audit for-loop contains unknown repo(s) {sorted(extras)!r}. "
        "If a new repo joins the portfolio, also add it to ALL_REPOS in this "
        "test (and audit COWORK_HANDOFF.md §2 + the PR-review loop alongside)."
    )


def test_audit_loop_count_matches_known_repos(audit_loop_repos: list[str]) -> None:
    assert len(audit_loop_repos) == len(ALL_REPOS), (
        f"Phase A audit for-loop has {len(audit_loop_repos)} repos; "
        f"expected {len(ALL_REPOS)} (12 portfolio repos + portfolio-ops). "
        "PR-review loop and audit loop must stay in lockstep."
    )


@pytest.mark.parametrize("fingerprint", FINGERPRINTS)
def test_audit_section_lists_fingerprint(audit_section: str, fingerprint: str) -> None:
    """Each of the six canonical fingerprint names must appear verbatim in
    the SESSION_PROMPT.md audit-section description, so a reader of the
    prompt knows what the audit covers.

    Drift shape this catches: PR #28 (phantom-ci), PR #36 (missing-timeout),
    and PR #41 (missing-concurrency) all extended `scripts/audit_phase_a.py`
    but only #46 propagated the names back into SESSION_PROMPT.md. Without
    this assertion, the next new fingerprint will silently fail to make it
    into the prompt.
    """
    assert fingerprint in audit_section, (
        f"Phase A audit description in SESSION_PROMPT.md does not name the "
        f"{fingerprint!r} fingerprint. `scripts/audit_phase_a.py` ships six "
        f"fingerprints today ({', '.join(FINGERPRINTS)}); the prompt must "
        "list each by name so an autonomous session knows what coverage to "
        "expect. If you intentionally dropped a fingerprint from the script, "
        "remove it from FINGERPRINTS in this test."
    )


def test_audit_section_pyyaml_ensure(audit_section: str) -> None:
    """The audit's bash one-liner must ensure pyyaml is importable before
    the per-repo loop runs.

    Two of the six fingerprints — `missing-timeout` and
    `missing-concurrency` — lazy-import `yaml` and degrade to a stderr
    `skipping <check>: pyyaml not installed` note when the import fails.
    Without an ensure step in the prompt, a fresh local-runner runs the
    audit at 4-of-6 capacity and the session-runner never knows. The
    canonical shape is an idempotent guard:

        python3 -c 'import yaml' 2>/dev/null || python3 -m pip install --quiet pyyaml

    A literal text match is loose — any shape that contains both
    ``import yaml`` and ``pyyaml`` near the audit invocation satisfies
    the lock. Drop or rename the guard and this fails with a pointer to
    PR #45 (the sibling fix on the `audit-cron.yml` cron path).
    """
    assert "import yaml" in audit_section and "pyyaml" in audit_section, (
        "Phase A audit section in SESSION_PROMPT.md is missing the pyyaml "
        "ensure step. Without it, `missing-timeout` and "
        "`missing-concurrency` silently skip on a fresh local venv, "
        "leaving the audit at 4-of-6 capacity. Restore the idempotent "
        "guard:\n"
        "    python3 -c 'import yaml' 2>/dev/null || python3 -m pip install --quiet pyyaml\n"
        "(or any equivalent shape that contains both 'import yaml' and "
        "'pyyaml'). The cron-path sibling lives in PR #45's "
        "audit-cron.yml install step."
    )


def test_audit_loop_matches_pr_review_loop(prompt_text: str, audit_loop_repos: list[str]) -> None:
    """The two loops must enumerate the same set in the same order; drift
    between them is the failure shape this lock catches."""
    all_loops = FOR_LOOP_RE.findall(prompt_text)
    assert len(all_loops) >= 2, (
        f"Expected at least two `for r in ...; do` loops in SESSION_PROMPT.md "
        f"(PR-review + audit); found {len(all_loops)}."
    )
    pr_review_repos = all_loops[0].split()
    assert pr_review_repos == audit_loop_repos, (
        "PR-review for-loop and audit for-loop in SESSION_PROMPT.md enumerate "
        f"different repo sets.\n  PR-review: {pr_review_repos}\n  audit:     "
        f"{audit_loop_repos}\nKeep both loops in lockstep so a repo can't be "
        "scanned-but-not-audited or audited-but-not-scanned."
    )
