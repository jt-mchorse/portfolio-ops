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


# ----------------------------------------------------------------------------
# check_phantom_ci — #32, the 4th fingerprint shape (zero-job push runs)
# ----------------------------------------------------------------------------

def _push_run(sha: str, conclusion: str | None, latest_check_runs_count: int, wf_id: int = 100, name: str = "tests") -> dict:
    return {
        "id": int(sha[:7], 16),
        "head_sha": sha + "0" * (40 - len(sha)),
        "conclusion": conclusion,
        "latest_check_runs_count": latest_check_runs_count,
        "workflow_id": wf_id,
        "name": name,
        "path": ".github/workflows/tests.yml",
    }


def _active_wf(wf_id: int = 100, name: str = "tests", path: str = ".github/workflows/tests.yml") -> dict:
    """Build a minimal workflow record for the active-workflows endpoint."""
    return {"id": wf_id, "name": name, "path": path, "state": "active"}


# Default `actions/workflows` response: workflow id 100 (the default in
# _push_run) is active. Phantom tests that want to test the "disabled
# historical workflow is filtered out" path override this explicitly.
_DEFAULT_WORKFLOWS = {"workflows": [_active_wf()]}


def test_check_phantom_ci_flags_three_of_three_zero_job_failures(audit_module):
    """Three consecutive zero-job push runs on main = phantom finding."""
    responses = {
        "actions/workflows": _DEFAULT_WORKFLOWS,
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                _push_run("aaa1111", "failure", 0),
                _push_run("bbb2222", "failure", 0),
                _push_run("ccc3333", "failure", 0),
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_phantom_ci("sickrepo", token=None)
    assert len(findings) == 1
    assert findings[0]["kind"] == "phantom-ci"
    assert findings[0]["phantom_count"] == 3
    assert findings[0]["window"] == 3
    assert findings[0]["sample_shas"] == ["aaa11110", "bbb22220", "ccc33330"]


def test_check_phantom_ci_clean_when_jobs_present(audit_module):
    """Three push runs each with non-zero jobs = no finding even if failures."""
    responses = {
        "actions/workflows": _DEFAULT_WORKFLOWS,
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                _push_run("aaa1111", "failure", 2),
                _push_run("bbb2222", "success", 2),
                _push_run("ccc3333", "failure", 1),
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_phantom_ci("anyrepo", token=None)
    assert findings == []


def test_check_phantom_ci_below_threshold(audit_module):
    """One phantom + two healthy = no finding (default threshold = 3)."""
    responses = {
        "actions/workflows": _DEFAULT_WORKFLOWS,
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                _push_run("aaa1111", "failure", 0),
                _push_run("bbb2222", "success", 2),
                _push_run("ccc3333", "success", 2),
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_phantom_ci("anyrepo", token=None)
    assert findings == []


def test_check_phantom_ci_threshold_boundary(audit_module):
    """Three phantoms among five total = finding (threshold = 3 of last 5)."""
    responses = {
        "actions/workflows": _DEFAULT_WORKFLOWS,
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                _push_run("aaa1111", "failure", 0),
                _push_run("bbb2222", "success", 2),
                _push_run("ccc3333", "failure", 0),
                _push_run("ddd4444", "success", 2),
                _push_run("eee5555", "failure", 0),
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_phantom_ci("anyrepo", token=None)
    assert len(findings) == 1
    assert findings[0]["phantom_count"] == 3
    assert findings[0]["window"] == 5


def test_check_phantom_ci_empty_runs_list(audit_module):
    """No push runs at all = no finding (no signal to evaluate)."""
    responses = {
        "actions/workflows": _DEFAULT_WORKFLOWS,
        "actions/runs?event=push&branch=main": {"workflow_runs": []},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_phantom_ci("anyrepo", token=None)
    assert findings == []


def test_check_phantom_ci_null_conclusion_counts_as_phantom(audit_module):
    """A still-in-progress or aborted-pre-jobs run with conclusion=null and 0 jobs counts."""
    responses = {
        "actions/workflows": _DEFAULT_WORKFLOWS,
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                _push_run("aaa1111", None, 0),
                _push_run("bbb2222", "failure", 0),
                _push_run("ccc3333", None, 0),
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_phantom_ci("anyrepo", token=None)
    assert len(findings) == 1
    assert findings[0]["phantom_count"] == 3


def test_check_phantom_ci_falls_back_to_jobs_endpoint(audit_module):
    """When latest_check_runs_count is absent, the script falls back to /jobs total_count."""
    def _run_no_count(sha, conclusion):
        r = _push_run(sha, conclusion, 0)
        r.pop("latest_check_runs_count")
        return r

    responses = {
        "actions/workflows": _DEFAULT_WORKFLOWS,
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                _run_no_count("aaa1111", "failure"),
                _run_no_count("bbb2222", "failure"),
                _run_no_count("ccc3333", "failure"),
            ]
        },
        "/jobs": {"total_count": 0, "jobs": []},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_phantom_ci("anyrepo", token=None)
    assert len(findings) == 1
    assert findings[0]["kind"] == "phantom-ci"


def test_check_phantom_ci_skips_disabled_workflow_phantom_history(audit_module):
    """Post-fix: phantom history from a now-disabled workflow should not surface.

    Regression target: after PR #28 + #31 closed the YAML parse bug, the old
    `ci.yml` workflow (id 283921465) still had 5/5 phantom push runs in its
    history. The fix renamed it out of existence so it stopped triggering, but
    /actions/runs still returns the historical phantoms. Without an active-set
    filter the audit would cry wolf about a closed bug indefinitely.
    """
    responses = {
        # Only workflow id 297708322 (the new `tests` workflow) is active.
        # The historical `.github/workflows/ci.yml` (id 100) is not in the list.
        "actions/workflows": {"workflows": [_active_wf(wf_id=297708322, name="tests")]},
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                _push_run("aaa1111", "failure", 0, wf_id=100),  # historical disabled
                _push_run("bbb2222", "failure", 0, wf_id=100),
                _push_run("ccc3333", "failure", 0, wf_id=100),
            ]
        },
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_phantom_ci("portfolio-ops", token=None)
    assert findings == []


# ---------------------------------------------------------------------------
# missing-timeout (#35)
# ---------------------------------------------------------------------------


def _b64(text: str) -> str:
    import base64

    return base64.b64encode(text.encode("utf-8")).decode("ascii")


_WORKFLOW_ALL_GUARDED = """\
name: ci
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - run: echo lint
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - run: echo test
"""

_WORKFLOW_ONE_UNGUARDED = """\
name: ci
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - run: echo lint
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo test
"""

_WORKFLOW_ALL_UNGUARDED = """\
name: ci
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: echo lint
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo test
  memory-check:
    runs-on: ubuntu-latest
    steps:
      - run: echo memory
"""


def test_check_missing_timeout_clean_when_all_guarded(audit_module):
    """A workflow whose jobs all set timeout-minutes should produce no finding."""
    responses = {
        "actions/workflows": {
            "workflows": [
                {"id": 1, "name": "ci", "path": ".github/workflows/ci.yml", "state": "active"},
            ]
        },
        "contents/.github/workflows/ci.yml": {"content": _b64(_WORKFLOW_ALL_GUARDED)},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_missing_timeout("anyrepo", token=None)
    assert findings == []


def test_check_missing_timeout_flags_single_unguarded_job(audit_module):
    """A workflow with one unguarded job should surface that job specifically."""
    responses = {
        "actions/workflows": {
            "workflows": [
                {"id": 1, "name": "ci", "path": ".github/workflows/ci.yml", "state": "active"},
            ]
        },
        "contents/.github/workflows/ci.yml": {"content": _b64(_WORKFLOW_ONE_UNGUARDED)},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_missing_timeout("anyrepo", token=None)
    assert len(findings) == 1
    assert findings[0]["kind"] == "missing-timeout"
    assert findings[0]["jobs_missing"] == ["test"]
    assert findings[0]["workflow_name"] == "ci"


def test_check_missing_timeout_flags_all_unguarded_jobs(audit_module):
    """A workflow with every job unguarded should list every job (sorted)."""
    responses = {
        "actions/workflows": {
            "workflows": [
                {"id": 1, "name": "ci", "path": ".github/workflows/ci.yml", "state": "active"},
            ]
        },
        "contents/.github/workflows/ci.yml": {"content": _b64(_WORKFLOW_ALL_UNGUARDED)},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_missing_timeout("anyrepo", token=None)
    assert len(findings) == 1
    # sorted() applies — alphabetical order, not source order.
    assert findings[0]["jobs_missing"] == ["lint", "memory-check", "test"]


def test_check_missing_timeout_skips_disabled_workflows(audit_module):
    """Disabled workflows are skipped — operator chose to disable; not silent rot."""
    responses = {
        "actions/workflows": {
            "workflows": [
                {"id": 1, "name": "old", "path": ".github/workflows/old.yml", "state": "disabled_manually"},
            ]
        },
        "contents/.github/workflows/old.yml": {"content": _b64(_WORKFLOW_ALL_UNGUARDED)},
    }
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        findings = audit_module.check_missing_timeout("anyrepo", token=None)
    assert findings == []


def test_check_missing_timeout_skips_when_pyyaml_missing(audit_module, capsys):
    """If pyyaml isn't importable, return [] and emit a stderr note.

    Other fingerprints must continue to work (stdlib-only); the script
    must not hard-fail on a missing optional import.
    """
    responses = {
        "actions/workflows": {
            "workflows": [
                {"id": 1, "name": "ci", "path": ".github/workflows/ci.yml", "state": "active"},
            ]
        },
        "contents/.github/workflows/ci.yml": {"content": _b64(_WORKFLOW_ALL_UNGUARDED)},
    }
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("simulated missing pyyaml")
        return real_import(name, *args, **kwargs)

    import builtins

    with (
        patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)),
        patch.object(builtins, "__import__", side_effect=fake_import),
    ):
        findings = audit_module.check_missing_timeout("anyrepo", token=None)
    assert findings == []
    err = capsys.readouterr().err
    assert "pyyaml not installed" in err
    assert "anyrepo" in err
