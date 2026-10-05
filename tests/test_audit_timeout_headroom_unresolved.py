"""A workflow whose job names resolve to nothing does not audit clean (#84, D-012).

`resolve_job_timeout`'s docstring promised the unresolved count rides on every
`timeout-headroom` finding so "a matcher that resolves nothing cannot look like
a clean repo". The count only travelled ON findings, so a workflow where nothing
resolved produced none: measured, a job named `Test ${{ matrix.python }}` at 99%
of its cap gave `headroom: []` and `main([...])` printed `clean`, rc 0.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from test_audit_phase_a import (  # noqa: E402
    _headroom_job,
    _headroom_responses,
    _headroom_run,
    _make_urlopen_stub,
)

SCRIPT = TESTS.parent / "scripts" / "audit_phase_a.py"

_EXPRESSION_NAME = """\
name: ci
on: [push]
jobs:
  test:
    name: "Test ${{ matrix.python }}"
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      matrix:
        python: ["3.11", "3.12"]
    steps:
      - run: echo test
"""

_LITERAL = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - run: echo test
"""


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("audit_phase_a_84", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _check(audit, workflow: str, jobs: list[dict]) -> list[dict]:
    responses = _headroom_responses(workflow, [_headroom_run(101)], {101: jobs})
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        return audit.check_timeout_headroom("anyrepo", token=None)


def test_a_workflow_that_resolves_nothing_is_a_finding(audit) -> None:
    findings = _check(audit, _EXPRESSION_NAME, [_headroom_job("Test 3.12", 14, 50), _headroom_job("Test 3.11", 14, 40)])
    assert [f["kind"] for f in findings] == ["timeout-headroom-unresolved"]
    assert findings[0]["unresolved_jobs"] == ["Test 3.11", "Test 3.12"]
    line = audit.format_finding(findings[0])
    assert "Test 3.11, Test 3.12" in line
    assert "unwatched" in line


def test_the_cli_does_not_print_clean_for_it(audit, capsys: pytest.CaptureFixture[str]) -> None:
    responses = _headroom_responses(_EXPRESSION_NAME, [_headroom_run(101)], {101: [_headroom_job("Test 3.12", 14, 50)]})
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(responses)):
        rc = audit.main(["--repo", "anyrepo"])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "timeout-headroom-unresolved" in out
    assert "clean" not in out.splitlines()[0]


def test_no_second_line_when_a_headroom_finding_already_carries_the_count(audit) -> None:
    # The matrix-cap workflow resolves `test (3.12)` (at 97%) and not `test 3.11`.
    from test_audit_phase_a import _WORKFLOW_MATRIX_CAP

    findings = _check(audit, _WORKFLOW_MATRIX_CAP, [_headroom_job("test (3.12)", 14, 30), _headroom_job("test 3.11", 14, 30)])
    assert [f["kind"] for f in findings] == ["timeout-headroom"]
    assert findings[0]["unresolved_jobs"] == ["test 3.11"]


def test_a_fully_resolved_workflow_under_the_bar_stays_silent(audit) -> None:
    assert _check(audit, _LITERAL, [_headroom_job("test", 3, 0)]) == []


def test_the_new_kind_has_a_declared_identity() -> None:
    sys.path.insert(0, str(TESTS.parent / "scripts"))
    from audit_issue_sync import IDENTITY_FIELDS

    assert IDENTITY_FIELDS["timeout-headroom-unresolved"] == ("repo", "workflow_path")
