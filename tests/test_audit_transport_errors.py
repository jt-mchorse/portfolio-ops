"""Every way a GitHub request fails is the fetch-error exit 2, never exit 1 (#88).

`main` mapped `HTTPError` and `URLError` to 2. A timeout or reset while
reading the body (`TimeoutError`, `ConnectionResetError` -- `OSError`s that
are not `URLError`s) and a 200 whose body is not JSON escaped as tracebacks at
exit 1: the code audit-cron files findings on, where exit 2 is the one it
refuses to file on. `_gh_get` now re-raises each as a `URLError`.
"""

from __future__ import annotations

import importlib.util
import io
import urllib.error
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "audit_phase_a.py"


@pytest.fixture(scope="module")
def audit_module():
    spec = importlib.util.spec_from_file_location("audit_phase_a_transport", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Resp(io.BytesIO):
    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _raising(exc: BaseException):  # type: ignore[no-untyped-def]
    def urlopen(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise exc

    return urlopen


@pytest.mark.parametrize(
    "urlopen",
    [
        pytest.param(_raising(TimeoutError("The read operation timed out")), id="read-timeout"),
        pytest.param(_raising(ConnectionResetError(54, "Connection reset by peer")), id="reset"),
        pytest.param(lambda *a, **k: _Resp(b"<html>proxy login</html>"), id="html-200"),
        pytest.param(lambda *a, **k: _Resp(b"\xff\xfe"), id="undecodable-200"),
        # Controls: what was already exit 2 stays exit 2.
        pytest.param(_raising(urllib.error.URLError("refused")), id="urlerror"),
        pytest.param(
            _raising(urllib.error.HTTPError("https://api.github.com/x", 502, "Bad Gateway", {}, None)),  # type: ignore[arg-type]
            id="http-502",
        ),
    ],
)
def test_a_failed_fetch_is_exit_2_with_one_error_line(audit_module, urlopen) -> None:
    err = io.StringIO()
    with patch("urllib.request.urlopen", side_effect=urlopen), redirect_stderr(err):
        rc = audit_module.main(["--repo", "llm-eval-harness"])
    assert rc == 2
    lines = err.getvalue().strip().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("error: ")
    assert "llm-eval-harness" in lines[0]


def test_a_value_error_inside_a_check_is_not_relabelled_a_network_failure(audit_module) -> None:
    # The translation lives in `_gh_get`, not in a blanket `except ValueError`
    # in `main`, so a bug in a check still crashes loudly.
    def boom(repo, token):  # type: ignore[no-untyped-def]
        raise ValueError("a bug in a check")

    with patch.object(audit_module, "audit_repo", boom), pytest.raises(ValueError, match="a bug"):
        audit_module.main(["--repo", "llm-eval-harness"])
