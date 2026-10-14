"""`prune_stale_trending.py` reads the status `gh()` returns (#92).

`gh()` returns `(status, body)` and only raises on a transport failure, so a
refused call never reached the `except` around `close_stale`. A 403 on every
write printed `[closed] repo#N`, counted it, and exited 0 with the issue still
open; a 401 on the listing read as "no trending issues", also exit 0.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "prune_stale_trending.py"

STALE = {"number": 7, "title": "old trend", "updated_at": "2026-01-01T00:00:00Z"}


@pytest.fixture
def prune(monkeypatch):
    spec = importlib.util.spec_from_file_location("prune_stale_trending", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("GH_TOKEN", "x")
    return module


def _fake(close=200, label=200, comment=201, listing=200, calls=None):
    """One stale trending issue in rag-production-kit, none elsewhere."""

    def gh(method, path, body=None):
        if calls is not None:
            calls.append((method, path))
        if method == "GET":
            if listing != 200 and "rag-production-kit" in path:
                return listing, {"message": "Bad credentials"}
            if "rag-production-kit" in path and "page=1" in path:
                return 200, [dict(STALE)]
            return 200, []
        if method == "PATCH":
            return close, {} if close == 200 else {"message": "Resource not accessible"}
        if path.endswith("/labels"):
            return label, []
        return comment, {}

    return gh


def test_a_refused_close_is_not_counted_and_exits_1(prune, capsys) -> None:
    prune.gh = _fake(close=403)
    assert prune.main() == 1
    out, err = capsys.readouterr()
    assert "[closed]" not in out
    assert "closed 0 stale" in out
    assert "403" in err


def test_a_refused_close_writes_nothing_else(prune) -> None:
    """Close goes first, so a refusal leaves no `wontfix-stale` label and no
    "Auto-closed" comment on an issue that is still open."""
    calls: list = []
    prune.gh = _fake(close=403, calls=calls)
    prune.main()
    writes = [c for c in calls if c[0] != "GET"]
    assert writes == [("PATCH", "/repos/jt-mchorse/rag-production-kit/issues/7")]


def test_a_refused_listing_is_an_error_not_an_empty_repo(prune, capsys) -> None:
    prune.gh = _fake(listing=401)
    assert prune.main() == 1
    assert "401" in capsys.readouterr().err


def test_other_repos_are_still_pruned_after_one_listing_fails(prune, capsys) -> None:
    calls: list = []
    prune.gh = _fake(listing=401, calls=calls)
    prune.main()
    listed = {p.split("/")[3] for m, p in calls if m == "GET"}
    assert listed == set(prune.ALL_REPOS)


def test_a_refused_label_after_a_close_is_a_warning(prune, capsys) -> None:
    prune.gh = _fake(label=403)
    assert prune.main() == 0
    out, err = capsys.readouterr()
    assert "[closed] rag-production-kit#7" in out
    assert "closed 1 stale" in out
    assert "label returned 403" in err


def test_the_happy_path_closes_labels_and_comments(prune, capsys) -> None:
    """Control: without this, a script that refused everything would pass. It
    also pins close-first, so it is red against the pre-#92 label-first order."""
    calls: list = []
    prune.gh = _fake(calls=calls)
    assert prune.main() == 0
    out, err = capsys.readouterr()
    assert "closed 1 stale" in out
    assert err == ""
    writes = [c[0] + " " + c[1].rsplit("/", 1)[-1] for c in calls if c[0] != "GET"]
    assert writes == ["PATCH 7", "POST labels", "POST comments"]
