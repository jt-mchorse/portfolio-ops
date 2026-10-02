"""paired-failure counts every red conclusion, not only "failure".

`check_paired_failure` tested `"failure" in conclusions` while the module's
`RED_CONCLUSIONS` (what `main-branch-red` treats as red) also holds
`timed_out`: a SHA with a success and a time-out was not flagged.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from test_audit_phase_a import _make_urlopen_stub  # noqa: E402


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("audit_phase_a_pf", TESTS.parent / "scripts" / "audit_phase_a.py")
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _runs(*conclusions: str) -> dict:
    return {
        "actions/runs?event=push&branch=main": {
            "workflow_runs": [
                {"head_sha": "a" * 40, "name": f"wf{i}", "path": f".github/workflows/wf{i}.yml", "conclusion": c}
                for i, c in enumerate(conclusions)
            ]
        },
        "/repos/jt-mchorse/anyrepo": {"default_branch": "main"},
    }


@pytest.mark.parametrize(
    ("conclusions", "flagged"),
    [
        (("success", "timed_out"), True),
        (("success", "failure"), True),
        (("success", "cancelled"), False),
        (("success", "success"), False),
        (("failure", "timed_out"), False),
    ],
)
def test_a_success_beside_any_red_conclusion_is_flagged(audit, conclusions, flagged) -> None:
    with patch("urllib.request.urlopen", side_effect=_make_urlopen_stub(_runs(*conclusions))):
        findings = audit.check_paired_failure("anyrepo", token=None)
    assert bool(findings) is flagged


def test_the_red_set_is_the_modules_own(audit) -> None:
    assert {"failure", "timed_out"} <= set(audit.RED_CONCLUSIONS)
