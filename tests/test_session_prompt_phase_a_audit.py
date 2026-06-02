"""Lock the Phase A silent-rot audit step in SESSION_PROMPT.md.

`scripts/audit_phase_a.py` (shipped in PR #20, issue #19) scans for three
silent-rot fingerprints — paired-failure, stuck-registration, stale-schedule —
across portfolio repos. Issue #21 wired it into Phase A of the canonical
session prompt as an observational, non-blocking step that runs after the
PR-review pass.

This file is the inverse-safety-net: if a future edit drops or breaks the
audit step in SESSION_PROMPT.md, pytest fails loudly with a specific message
naming what's missing. Mirrors the shape of
`tests/test_session_prompt_phase_a_loop.py` (which locks the PR-review loop).

Related: portfolio-ops#21.
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
