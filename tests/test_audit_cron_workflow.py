"""Lock that `.github/workflows/audit-cron.yml` has the shape the issue spec
requires (portfolio-ops#24).

The file is the only mechanism that catches silent rot in the 7+ day window
when no autonomous session runs. If a future PR accidentally:
  - changes the cron from weekly to never (cron typo),
  - drops the `workflow_dispatch` trigger (operator can't smoke-test),
  - removes the `issues: write` permission (filing fails silently in CI),
  - drops the `--label audit-cron` dedupe path (duplicate issues every week),
  - or removes the call to `scripts/audit_phase_a.py` itself,
the cron survives but stops doing its job. This lock fails loudly on each
of those shapes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_CRON_PATH = REPO_ROOT / ".github" / "workflows" / "audit-cron.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    assert AUDIT_CRON_PATH.is_file(), (
        f"{AUDIT_CRON_PATH} missing. Audit-cron is the post-deploy net for "
        "silent rot during session-less windows; removing it without "
        "replacement reintroduces the failure-mode it exists to cover."
    )
    return yaml.safe_load(AUDIT_CRON_PATH.read_text(encoding="utf-8"))


def test_workflow_name(workflow: dict) -> None:
    assert workflow.get("name") == "audit-cron"


def test_weekly_cron_schedule(workflow: dict) -> None:
    # `on` is a reserved YAML token that PyYAML may parse as True; allow either key.
    triggers = workflow.get("on") or workflow.get(True)
    assert isinstance(triggers, dict), f"`on:` missing or malformed: {triggers!r}"
    schedule = triggers.get("schedule")
    assert isinstance(schedule, list) and schedule, (
        "audit-cron must run on a schedule; got "
        f"{schedule!r}. Manual-only defeats the purpose."
    )
    crons = [entry.get("cron") for entry in schedule]
    assert "0 14 * * 1" in crons, (
        f"Expected weekly Monday 14:00 UTC cron (`0 14 * * 1`); got {crons!r}. "
        "If the cadence changed, update both this lock and the issue rationale."
    )


def test_manual_dispatch_trigger(workflow: dict) -> None:
    triggers = workflow.get("on") or workflow.get(True)
    assert "workflow_dispatch" in triggers, (
        "`workflow_dispatch` must be present so the operator can smoke-test "
        "the cron without waiting for the next Monday."
    )


def test_issues_write_permission(workflow: dict) -> None:
    permissions = workflow.get("permissions", {})
    assert permissions.get("issues") == "write", (
        f"`permissions.issues` must be `write` so the cron can file its rolling "
        f"audit issue; got {permissions!r}. Without this, filing fails silently."
    )


def test_audit_script_invoked(workflow: dict) -> None:
    text = AUDIT_CRON_PATH.read_text(encoding="utf-8")
    assert "scripts/audit_phase_a.py" in text, (
        "audit-cron.yml must call `scripts/audit_phase_a.py`. If the script "
        "was renamed, update both."
    )


def test_dedupe_label_reference(workflow: dict) -> None:
    text = AUDIT_CRON_PATH.read_text(encoding="utf-8")
    # The dedupe gate is "skip if any open [audit-cron]-labeled issue exists."
    # Both the lookup (--label audit-cron in gh issue list) and the file
    # (--label audit-cron in gh issue create) must reference the same label.
    occurrences = text.count("--label audit-cron")
    assert occurrences >= 2, (
        f"Expected at least 2 references to `--label audit-cron` (one in the "
        f"dedupe lookup, one in the issue-create call); got {occurrences}. "
        "Dropping the dedupe label means a fresh issue files every week even "
        "while the prior one is still open."
    )


def test_pyyaml_installed(workflow: dict) -> None:
    # scripts/audit_phase_a.py's missing-timeout and missing-concurrency
    # fingerprints lazy-import pyyaml and degrade to "no findings" plus a
    # stderr note when it's absent. The audit-cron job MUST install pyyaml
    # explicitly so both checks function on schedule; without it, half of
    # the audit silently no-ops every Monday. See portfolio-ops#44.
    audit_job = workflow.get("jobs", {}).get("audit", {})
    steps = audit_job.get("steps", [])
    install_step = None
    for step in steps:
        run = step.get("run", "")
        if "pip install" in run and "pyyaml" in run:
            install_step = step
            break
    assert install_step is not None, (
        "audit-cron.yml's `audit` job must have a step that runs "
        "`pip install ... pyyaml` before invoking scripts/audit_phase_a.py. "
        "Without pyyaml, the missing-timeout and missing-concurrency "
        "fingerprints silently no-op and the weekly audit only catches "
        "the four stdlib-checkable shapes. See portfolio-ops#44."
    )
    # Defense-in-depth: ordering. The install step must come BEFORE the
    # `Run silent-rot audit` step. A swap would silently keep CI green
    # (pyyaml gets installed; just too late to help the audit).
    install_idx = steps.index(install_step)
    audit_idx = next(
        (i for i, step in enumerate(steps) if step.get("id") == "audit"),
        None,
    )
    assert audit_idx is not None, (
        "audit-cron.yml's `audit` job must have a step with `id: audit` "
        "that invokes scripts/audit_phase_a.py — the rest of the job "
        "branches on its exit code."
    )
    assert install_idx < audit_idx, (
        "The pyyaml install step must run BEFORE the audit step "
        f"(install_idx={install_idx}, audit_idx={audit_idx}). Installing "
        "after the audit silently keeps CI green while the audit still "
        "skips the two yaml-dependent fingerprints."
    )


def test_audit_step_has_gh_token_env(workflow: dict) -> None:
    """Lock that the `audit` step declares `GH_TOKEN: ${{ github.token }}`
    so `scripts/audit_phase_a.py` doesn't fall back to the unauth GitHub
    API path (60 req/h).

    Symmetric to #48 / PR #49 (the session-runner sibling). The cron path
    makes the same several-API-calls-per-repo × 13 repos request pattern
    as the session-runner path; without GH_TOKEN, urllib.request inside
    the audit script hits HTTP 403 rate-limit partway through the loop
    and the last few repos return `fetch-error` lines that look like
    real findings but are self-inflicted. Dropping the env block keeps
    CI green (the workflow itself doesn't depend on the audit's API
    calls), so the regression is silent until someone reads the audit
    output and sees the gap.

    Failure shape this catches: a future PR removes the `env: GH_TOKEN:`
    block from the audit step or renames the variable. The lock fires
    immediately with a pointer back to PR #49 (session-runner sibling)
    and #45 (scripts/README.md local-operator pattern that motivates
    the symmetry).
    """
    audit_job = workflow.get("jobs", {}).get("audit", {})
    steps = audit_job.get("steps", [])
    audit_step = next((s for s in steps if s.get("id") == "audit"), None)
    assert audit_step is not None, (
        "audit-cron.yml's `audit` job must have a step with `id: audit` "
        "that invokes scripts/audit_phase_a.py — the rest of the job "
        "branches on its exit code. This test relies on that id to find "
        "the right step; if the id changed deliberately, update this lock."
    )
    env = audit_step.get("env", {}) or {}
    assert env.get("GH_TOKEN") == "${{ github.token }}", (
        "audit-cron.yml's `audit` step must declare "
        "`env: GH_TOKEN: ${{ github.token }}`. Without it, "
        "`scripts/audit_phase_a.py`'s urllib.request calls fall back to "
        "the unauth GitHub API path (60 req/h) and hit HTTP 403 partway "
        "through the 13-repo loop. The session-runner sibling at PR #49 "
        "ships the same guard for `session-runner/SESSION_PROMPT.md` step 4; "
        "this lock keeps the cron path symmetric. See #48 / PR #49 for the "
        "session-runner shape and PR #45's scripts/README.md for the "
        f"local-operator pattern. Current env: {env!r}."
    )


def test_listed_in_active_workflows_lock() -> None:
    # If audit-cron.yml is added to .github/workflows/ but NOT to the
    # EXPECTED_ACTIVE_WORKFLOWS tuple in tests/test_workflows_dir_only_active.py,
    # that other lock test fails with "unexpected file" — verify the entry
    # was added so the two locks agree.
    lock_path = REPO_ROOT / "tests" / "test_workflows_dir_only_active.py"
    text = lock_path.read_text(encoding="utf-8")
    assert '"audit-cron.yml"' in text, (
        "tests/test_workflows_dir_only_active.py must include "
        "`audit-cron.yml` in EXPECTED_ACTIVE_WORKFLOWS or that lock fails."
    )
