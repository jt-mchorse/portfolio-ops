"""Lock that every workflow job has a sensible `timeout-minutes` bound.

Companion to `test_workflows_yaml_parseable.py` (#30 / #31) — same
silent-rot prevention arc, different failure mode. Final hop in the
portfolio-wide propagation of the timeout-minutes lock.

The failure mode this catches: GitHub Actions defaults to 360 minutes
(6 hours) per job when no `timeout-minutes` is set. A hung job —
`pip install` stall, infinite asyncio loop, stuck Anthropic API call —
therefore burns the full 6-hour ceiling before the runner kills it.
That's quota the operator pays for whether the run produced anything or
not.

This file is the **inverse safety net** to the audit-side
`scripts/audit_phase_a.py --check missing-timeout` fingerprint shipped
in #35 / PR #36. Both layers protect the same invariant:

  - the audit fingerprint catches portfolio-wide drift *post-deploy*
    (weekly cron run), surfacing every unprotected job in every repo;
  - this lock catches regressions *at PR-test time before merge*,
    making the failure mode loud locally and in CI rather than waiting
    for the next audit-cron run.

Two layers at two cadences — same invariant. Symmetric with the
silent-CI arc that landed earlier this year: `test_workflows_yaml_parseable.py`
catches YAML parse failures pre-merge, `audit_phase_a.py --check
phantom-ci` catches them post-deploy (#32).

Sister implementations across the 12 portfolio repos:
  - Python: `llm-eval-harness#63` (canonical), `rag-production-kit#55`,
    `chunking-strategies-lab#42`, `embedding-model-shootout#52`,
    `vector-search-at-scale#44`, `python-async-llm-pipelines#51`,
    `llm-cost-optimizer#59`, `prompt-regression-suite#56`.
  - TypeScript (Vitest): `nextjs-streaming-ai-patterns#37`,
    `agent-orchestration-platform#44`, `ai-app-integration-tests#39`.
  - JS (node:test stdlib): `mcp-server-cookbook#49`.

Spec / origin: this repo's #38.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Policy band for this repo. Tight enough to flag an accidental
# `timeout-minutes: 360`; wide enough for the audit-cron job (Anthropic
# API + RSS + GitHub-API scans run in well under 5 min). Bumping the
# ceiling is intentional and should land with a comment naming the
# workload that forced the change.
MIN_TIMEOUT_MINUTES = 1
MAX_TIMEOUT_MINUTES = 30


def _all_workflow_files() -> list[Path]:
    if not ACTIVE_WORKFLOWS_DIR.is_dir():
        return []
    return sorted(ACTIVE_WORKFLOWS_DIR.glob("*.yml"))


def _all_jobs() -> list[tuple[str, str, dict[str, Any]]]:
    """Return (workflow_filename, job_id, job_body) for every job.

    Flattened across all workflow files so pytest parametrization
    surfaces each missing or out-of-band timeout as its own failure,
    not a single "one of N jobs is broken" summary line.
    """
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for path in _all_workflow_files():
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            continue
        jobs = parsed.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_id, body in jobs.items():
            if isinstance(body, dict):
                rows.append((path.name, str(job_id), body))
    return rows


ALL_JOBS = _all_jobs()


def test_at_least_one_job_discovered() -> None:
    # Smoke check: parametrization silently degrades to a no-op if the
    # discovery fixture returns []. Make that loud.
    assert ALL_JOBS, (
        f"No jobs discovered under {ACTIVE_WORKFLOWS_DIR}. Either the "
        "workflow files were removed or YAML discovery is broken; this "
        "lock should not silently pass in either case."
    )


@pytest.mark.parametrize(
    ("workflow", "job_id", "body"),
    ALL_JOBS,
    ids=[f"{wf}::{jid}" for (wf, jid, _) in ALL_JOBS],
)
def test_job_has_timeout_minutes(workflow: str, job_id: str, body: dict[str, Any]) -> None:
    timeout = body.get("timeout-minutes")
    assert timeout is not None, (
        f"{workflow}::{job_id} has no `timeout-minutes` set. GitHub "
        f"Actions defaults to 360 min/job when this is missing — a hung "
        f"job (network stall, infinite loop, stuck Anthropic API call) "
        f"burns the full 6-hour ceiling before the runner kills it. "
        f"Set `timeout-minutes:` on this job. For this repo's workloads, "
        f"15 is the policy default; stay in [{MIN_TIMEOUT_MINUTES}, "
        f"{MAX_TIMEOUT_MINUTES}]. The audit-side fingerprint in "
        f"`scripts/audit_phase_a.py --check missing-timeout` is the "
        f"post-deploy companion to this lock."
    )


@pytest.mark.parametrize(
    ("workflow", "job_id", "body"),
    ALL_JOBS,
    ids=[f"{wf}::{jid}" for (wf, jid, _) in ALL_JOBS],
)
def test_job_timeout_is_int(workflow: str, job_id: str, body: dict[str, Any]) -> None:
    timeout = body.get("timeout-minutes")
    if timeout is None:
        pytest.skip("covered by test_job_has_timeout_minutes")
    msg = (
        f"{workflow}::{job_id} has `timeout-minutes: {timeout!r}` "
        f"({type(timeout).__name__}); GitHub Actions requires an integer. "
        "A YAML string like `'15'` is parsed but rejected at workflow-load "
        "time, producing a silent failure shape similar to #27 (the unquoted "
        "colon-space silent-CI outage)."
    )
    # `bool` is a subclass of `int` in Python; reject it explicitly so a
    # stray `timeout-minutes: true` (parsed as 1) doesn't sneak past.
    assert isinstance(timeout, int), msg
    assert not isinstance(timeout, bool), msg


@pytest.mark.parametrize(
    ("workflow", "job_id", "body"),
    ALL_JOBS,
    ids=[f"{wf}::{jid}" for (wf, jid, _) in ALL_JOBS],
)
def test_job_timeout_in_policy_band(workflow: str, job_id: str, body: dict[str, Any]) -> None:
    timeout = body.get("timeout-minutes")
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        pytest.skip("covered by test_job_timeout_is_int")
    assert MIN_TIMEOUT_MINUTES <= timeout <= MAX_TIMEOUT_MINUTES, (
        f"{workflow}::{job_id} has `timeout-minutes: {timeout}` outside the "
        f"policy band [{MIN_TIMEOUT_MINUTES}, {MAX_TIMEOUT_MINUTES}]. Values "
        f"above the ceiling reintroduce most of the unbounded-job quota burn; "
        f"values at 0 disable the timeout entirely (GitHub Actions semantics). "
        f"If a future workload genuinely needs a wider bound, bump "
        f"MAX_TIMEOUT_MINUTES with a comment naming the workload."
    )
