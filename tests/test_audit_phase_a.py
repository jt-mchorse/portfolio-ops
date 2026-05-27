"""Tests for scripts/audit_phase_a.py.

Fixture strategy: monkeypatch `urllib.request.urlopen` to return canned JSON
responses matching the three GitHub Actions endpoints the audit hits.

Coverage:
- paired-failure: a SHA produces both success + failure across two runs.
- stuck-registration: a workflow with name == path (parser fallback).
- stale-schedule: a scheduled workflow with 3+ consecutive failures.
- clean: all three endpoints return healthy data; exit 0.
- CLI integration: --repo filter + --json output + exit code.

Related: portfolio-ops#19.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_phase_a.py"


@pytest.fixture(scope="module")
def audit_module():
    """Import scripts/audit_phase_a.py as a module."""
    spec = importlib.util.spec_from_file_location("audit_phase_a", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_urlopen_stub(responses: dict[str, dict]):
    """Build a urlopen stub. responses maps path-suffix to JSON dict."""

    class _StubResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

    def stub(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        for suffix, payload in responses.items():
            if suffix in url:
                return _StubResponse(payload)
        return _StubResponse({"workflow_runs": [], "workflows": []})

    return stub


def test_check_paired_failure_flags_mixed_conclusions(audit_module):
    """A SHA with one success + one failure should produce a paired-failure finding."""
    responses = {
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                {"head_sha": "abc12345...", "conclusion": "success", "name": "ci", "path": ".github/workflows/ci.yml"},
                {"head_sha": "abc12345...", "conclusion": "failure", "name": ".github/workflows/template.yml", "path": ".github/workflows/template.yml"},
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_paired_failure("anyrepo", token=None)
    assert len(findings) == 1
    assert findings[0]["kind"] == "paired-failure"
    assert findings[0]["repo"] == "anyrepo"
    assert findings[0]["sha"] == "abc12345"


def test_check_paired_failure_ignores_single_run_per_sha(audit_module):
    """A SHA with only one run (even if failing) is not a paired-failure."""
    responses = {
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                {"head_sha": "abc12345...", "conclusion": "failure", "name": "ci", "path": ".github/workflows/ci.yml"},
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_paired_failure("anyrepo", token=None)
    assert findings == []


def test_check_paired_failure_ignores_uniform_success(audit_module):
    """Multiple runs per SHA, all success: not a finding."""
    responses = {
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                {"head_sha": "abc12345...", "conclusion": "success", "name": "ci", "path": ".github/workflows/ci.yml"},
                {"head_sha": "abc12345...", "conclusion": "success", "name": "lint", "path": ".github/workflows/lint.yml"},
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_paired_failure("anyrepo", token=None)
    assert findings == []


def test_check_stuck_registration_flags_path_as_name(audit_module):
    """A workflow with name starting with .github/workflows/ is stuck."""
    responses = {
        "actions/workflows": {
            "workflows": [
                {"id": 999, "name": ".github/workflows/broken.yml", "path": ".github/workflows/broken.yml", "state": "active"},
                {"id": 100, "name": "healthy", "path": ".github/workflows/healthy.yml", "state": "active"},
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_stuck_registration("anyrepo", token=None)
    assert len(findings) == 1
    assert findings[0]["workflow_id"] == 999
    assert findings[0]["registered_name"] == ".github/workflows/broken.yml"


def test_check_stuck_registration_ignores_disabled(audit_module):
    """Disabled workflows are skipped (operator chose to disable; not silent rot)."""
    responses = {
        "actions/workflows": {
            "workflows": [
                {"id": 999, "name": ".github/workflows/broken.yml", "path": ".github/workflows/broken.yml", "state": "disabled_manually"},
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_stuck_registration("anyrepo", token=None)
    assert findings == []


def test_check_stale_schedule_flags_consecutive_failures(audit_module):
    """3+ consecutive scheduled failures with no successes is a finding."""
    responses = {
        "actions/runs?event=schedule": {
            "workflow_runs": [
                {"path": ".github/workflows/cron.yml", "name": "cron", "conclusion": "failure"},
                {"path": ".github/workflows/cron.yml", "name": "cron", "conclusion": "failure"},
                {"path": ".github/workflows/cron.yml", "name": "cron", "conclusion": "failure"},
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_stale_schedule("anyrepo", token=None)
    assert len(findings) == 1
    assert findings[0]["consecutive_failures"] == 3


def test_check_stale_schedule_stops_at_first_success(audit_module):
    """A success between failures resets the consecutive count."""
    responses = {
        "actions/runs?event=schedule": {
            "workflow_runs": [
                {"path": ".github/workflows/cron.yml", "name": "cron", "conclusion": "failure"},
                {"path": ".github/workflows/cron.yml", "name": "cron", "conclusion": "success"},
                {"path": ".github/workflows/cron.yml", "name": "cron", "conclusion": "failure"},
                {"path": ".github/workflows/cron.yml", "name": "cron", "conclusion": "failure"},
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_stale_schedule("anyrepo", token=None)
    # Only 1 consecutive failure at the top, below the threshold of 3.
    assert findings == []


def test_check_stale_schedule_honors_threshold(audit_module):
    """Threshold parameter changes the flag bar."""
    responses = {
        "actions/runs?event=schedule": {
            "workflow_runs": [
                {"path": ".github/workflows/cron.yml", "name": "cron", "conclusion": "failure"},
                {"path": ".github/workflows/cron.yml", "name": "cron", "conclusion": "failure"},
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings_t3 = audit_module.check_stale_schedule("anyrepo", token=None, threshold=3)
        findings_t2 = audit_module.check_stale_schedule("anyrepo", token=None, threshold=2)
    assert findings_t3 == []
    assert len(findings_t2) == 1


def test_audit_repo_with_no_findings_returns_empty(audit_module):
    """All three checks return empty for a healthy repo."""
    responses = {
        "actions/runs?event=push&branch=main": {"workflow_runs": []},
        "actions/workflows": {"workflows": [
            {"id": 1, "name": "ci", "path": ".github/workflows/ci.yml", "state": "active"}
        ]},
        "actions/runs?event=schedule": {"workflow_runs": []},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.audit_repo("healthyrepo", token=None)
    assert findings == []


def test_main_clean_repo_returns_zero_and_prints_clean(audit_module, capsys):
    """End-to-end: a healthy repo returns 0 and prints 'clean'."""
    responses = {
        "actions/runs?event=push&branch=main": {"workflow_runs": []},
        "actions/workflows": {"workflows": [
            {"id": 1, "name": "ci", "path": ".github/workflows/ci.yml", "state": "active"}
        ]},
        "actions/runs?event=schedule": {"workflow_runs": []},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        exit_code = audit_module.main(["--repo", "healthyrepo"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "clean" in out


def test_main_with_findings_returns_one_and_prints_summary(audit_module, capsys):
    """End-to-end: a repo with findings returns 1 and prints structured summary."""
    responses = {
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                {"head_sha": "deadbeef...", "conclusion": "success", "name": "ci", "path": ".github/workflows/ci.yml"},
                {"head_sha": "deadbeef...", "conclusion": "failure", "name": ".github/workflows/dead.yml", "path": ".github/workflows/dead.yml"},
            ]
        },
        "actions/workflows": {"workflows": [
            {"id": 1, "name": "ci", "path": ".github/workflows/ci.yml", "state": "active"}
        ]},
        "actions/runs?event=schedule": {"workflow_runs": []},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        exit_code = audit_module.main(["--repo", "sickrepo"])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "findings: 1" in out
    assert "paired-failure" in out
    assert "deadbeef" in out


def test_main_json_output(audit_module, capsys):
    """--json emits one JSON object per finding (line-delimited)."""
    responses = {
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                {"head_sha": "deadbeef...", "conclusion": "success", "name": "ci", "path": ".github/workflows/ci.yml"},
                {"head_sha": "deadbeef...", "conclusion": "failure", "name": ".github/workflows/dead.yml", "path": ".github/workflows/dead.yml"},
            ]
        },
        "actions/workflows": {"workflows": []},
        "actions/runs?event=schedule": {"workflow_runs": []},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        exit_code = audit_module.main(["--repo", "sickrepo", "--json"])
    out = capsys.readouterr().out
    assert exit_code == 1
    # Should be parseable as JSON Lines.
    lines = [line for line in out.strip().split("\n") if line]
    parsed = [json.loads(line) for line in lines]
    assert len(parsed) == 1
    assert parsed[0]["kind"] == "paired-failure"
