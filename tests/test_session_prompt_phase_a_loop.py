"""Lock the Phase A PR-review for-loop in SESSION_PROMPT.md.

The canonical session prompt at `session-runner/SESSION_PROMPT.md` contains a
shell `for r in ...; do` loop that enumerates every repo a scheduled session
sweeps for ready PRs. Prior session memory caught a real bug: portfolio-ops
itself was missing from that list, so PRs opened against portfolio-ops sat
unseen until a session manually noticed them.

This file is the inverse-safety-net: assert the loop contains all 13 repos
(12 portfolio repos plus portfolio-ops itself), and never silently drops one.

Related: portfolio-ops#9.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_PROMPT = REPO_ROOT / "session-runner" / "SESSION_PROMPT.md"

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

# Matches `for r in <space-separated repos>; do` on a single line.
FOR_LOOP_RE = re.compile(r"for\s+r\s+in\s+([^;]+);\s*do", re.MULTILINE)


@pytest.fixture(scope="module")
def prompt_text() -> str:
    return SESSION_PROMPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def for_loop_repos(prompt_text: str) -> list[str]:
    match = FOR_LOOP_RE.search(prompt_text)
    assert match is not None, (
        "Could not locate `for r in ...; do` loop in SESSION_PROMPT.md. "
        "Phase A PR-review pass depends on this loop; if it has been "
        "restructured, update this test to match."
    )
    return match.group(1).split()


def test_session_prompt_exists() -> None:
    assert SESSION_PROMPT.is_file(), f"SESSION_PROMPT.md missing at {SESSION_PROMPT}"


@pytest.mark.parametrize("repo", ALL_REPOS)
def test_phase_a_loop_includes_repo(for_loop_repos: list[str], repo: str) -> None:
    assert repo in for_loop_repos, (
        f"Phase A PR-review for-loop in SESSION_PROMPT.md is missing {repo!r}. "
        "Every repo on the same scheduled-merge cadence must be in this loop, "
        "or its ready PRs silently wait for a manual sweep (see issue #9)."
    )


def test_phase_a_loop_has_no_unknown_repos(for_loop_repos: list[str]) -> None:
    extras = set(for_loop_repos) - set(ALL_REPOS)
    assert not extras, (
        f"Phase A PR-review for-loop contains unknown repo(s) {sorted(extras)!r}. "
        "If a new repo is added to the portfolio, also add it to ALL_REPOS in "
        "this test (and audit COWORK_HANDOFF.md §2 alongside)."
    )


def test_phase_a_loop_count_matches_known_repos(for_loop_repos: list[str]) -> None:
    assert len(for_loop_repos) == len(ALL_REPOS), (
        f"Phase A PR-review for-loop has {len(for_loop_repos)} repos; "
        f"expected {len(ALL_REPOS)} (12 portfolio repos + portfolio-ops)."
    )
