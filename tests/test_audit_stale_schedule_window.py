"""stale-schedule judges each scheduled workflow on its own runs (#82).

Measured live on portfolio-ops before this: one ``per_page=10`` window shared by
every scheduled workflow, so ``trending-weekly`` (failing every Sunday since
08-23) never had three runs in it and was never reported, while
``trending-daily``'s streak printed as the window size. And only ``failure``
counted, so a ``timed_out`` run -- red to ``main-branch-red`` -- broke a streak.

The stubs here answer only the ``per_page=100`` URL: a check that went back to
the old window would read an empty run list, which pins the window itself.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_phase_a.py"
URL = "actions/runs?event=schedule&per_page=100"
DAILY = ".github/workflows/daily.yml"
WEEKLY = ".github/workflows/weekly.yml"


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("audit_phase_a_82", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stub(runs: list[dict]):
    class _Resp:
        def __init__(self, payload: dict) -> None:
            self._p = payload

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self) -> bytes:
            return json.dumps(self._p).encode("utf-8")

    def urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        if URL in url:
            return _Resp({"workflow_runs": runs})
        return _Resp({"workflow_runs": [], "workflows": []})

    return urlopen


def _run(path: str, conclusion: str | None) -> dict:
    return {"path": path, "name": Path(path).stem, "conclusion": conclusion}


def _daily_and_weekly(weeks: int, weekly: str = "failure") -> list[dict]:
    """Newest first: seven daily runs, then one weekly, repeated."""
    runs: list[dict] = []
    for _ in range(weeks):
        runs += [_run(DAILY, "success")] * 7
        runs.append(_run(WEEKLY, weekly))
    return runs


def _check(audit, runs: list[dict], threshold: int = 3) -> list[dict]:
    with patch("urllib.request.urlopen", side_effect=_stub(runs)):
        return audit.check_stale_schedule("anyrepo", token=None, threshold=threshold)


def test_a_failing_weekly_job_beside_a_daily_one_is_flagged(audit) -> None:
    # Four weekly failures sit at positions 8, 16, 24, 32 -- outside any
    # newest-10 window but one, inside the 100-run one.
    findings = _check(audit, _daily_and_weekly(4))
    assert [f["workflow_path"] for f in findings] == [WEEKLY]
    assert findings[0]["consecutive_failures"] == 4


def test_a_healthy_weekly_job_beside_a_daily_one_is_not(audit) -> None:
    assert _check(audit, _daily_and_weekly(4, weekly="success")) == []


def test_timed_out_counts_as_red(audit) -> None:
    findings = _check(audit, [_run(DAILY, "timed_out")] * 3 + [_run(DAILY, "failure")] * 2)
    assert findings[0]["consecutive_failures"] == 5


@pytest.mark.parametrize("neutral", [None, "cancelled", "skipped"])
def test_a_run_with_no_verdict_is_stepped_over_not_a_reset(audit, neutral) -> None:
    runs = [_run(DAILY, neutral), _run(DAILY, "failure"), _run(DAILY, neutral)]
    runs += [_run(DAILY, "failure")] * 2 + [_run(DAILY, "success")]
    findings = _check(audit, runs)
    assert findings[0]["consecutive_failures"] == 3
    assert findings[0]["streak_is_lower_bound"] is False


@pytest.mark.parametrize("green", ["success", "neutral", "action_required"])
def test_any_other_conclusion_still_ends_the_streak(audit, green) -> None:
    runs = [_run(DAILY, "failure"), _run(DAILY, green)] + [_run(DAILY, "failure")] * 5
    assert _check(audit, runs) == []


def test_a_streak_that_fills_the_window_is_reported_as_a_lower_bound(audit) -> None:
    findings = _check(audit, [_run(DAILY, "failure")] * 4)
    assert findings[0]["streak_is_lower_bound"] is True
    line = audit.format_finding(findings[0])
    assert "has at least 4 consecutive failures" in line


def test_an_exact_streak_prints_without_at_least(audit) -> None:
    findings = _check(audit, [_run(DAILY, "failure")] * 3 + [_run(DAILY, "success")])
    assert "has 3 consecutive failures" in audit.format_finding(findings[0])


def test_the_weekly_finding_comes_out_of_audit_repo(audit) -> None:
    # Through the orchestrator, not only the check.
    with patch("urllib.request.urlopen", side_effect=_stub(_daily_and_weekly(4))):
        findings = audit.audit_repo("anyrepo", token=None)
    stale = [f for f in findings if f["kind"] == "stale-schedule"]
    assert [f["workflow_path"] for f in stale] == [WEEKLY]
