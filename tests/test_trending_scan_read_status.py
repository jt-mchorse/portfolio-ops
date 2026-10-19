"""`trending_scan.py`'s guarding reads fail closed (#99).

`gh()` returns `(status, body)` and only raises on a transport error. The cap
check and the title dedupe each read GitHub before a write, and both used to
treat a refused read as "nothing there": with every GET answering 403 the cap
read 0/30 and the dedupe an empty set, so a rate-limited run filed a duplicate
at exit 0. The sibling #92 recorded and did not fix.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "trending_scan.py"


@pytest.fixture
def ts(monkeypatch):
    spec = importlib.util.spec_from_file_location("trending_scan_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves the class's module through sys.modules.
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setenv("GH_TOKEN", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    monkeypatch.setattr(module.time, "sleep", lambda s: None)
    return module


def _gh(search=200, listing=200, titles=200, titles_page2=200, posts=None, n_open=3):
    def gh(method, path, body=None):
        if method == "POST":
            if posts is not None:
                posts.append(path)
            return 201, {"number": 99}
        if path.startswith("/search/"):
            return (200, {"total_count": n_open}) if search == 200 else (search, {"message": "no"})
        if "state=open" in path:
            return (200, [{}]) if listing == 200 else (listing, {"message": "no"})
        # title listing
        if "page=1&" in path:
            if titles != 200:
                return titles, {"message": "Bad credentials"}
            return 200, [{"title": f"[trending] t{i}"} for i in range(100)]
        if "page=2&" in path:
            if titles_page2 != 200:
                return titles_page2, {"message": "Server Error"}
            return 200, [{"title": "[trending] Already filed"}]
        return 200, []

    return gh


def _run_main(ts, monkeypatch, gh):
    ts.gh = gh
    finding = ts.Finding(**{f.name: "x" for f in dataclasses.fields(ts.Finding)})
    monkeypatch.setattr(ts, "gather_findings", lambda mode: [finding])
    monkeypatch.setattr(
        ts,
        "call_claude_eval",
        lambda key, f: {"map": "rag-production-kit", "title": "Already filed"},
    )
    monkeypatch.setattr(sys, "argv", ["trending_scan", "--mode", "daily"])
    return ts.main()


# ----------------------------------------------------------------------
# The cap
# ----------------------------------------------------------------------


def test_search_ok_is_the_count(ts) -> None:
    ts.gh = _gh(n_open=7)
    assert ts.count_open_trending_issues(ts.ALL_REPOS) == 7


def test_every_read_refused_is_an_error_not_zero(ts) -> None:
    ts.gh = _gh(search=403, listing=403)
    with pytest.raises(ts.GitHubReadError, match="403"):
        ts.count_open_trending_issues(ts.ALL_REPOS)


def test_the_fallback_counts_when_every_repo_answers(ts) -> None:
    ts.gh = _gh(search=422)
    assert ts.count_open_trending_issues(ts.ALL_REPOS) == len(ts.ALL_REPOS)


def test_one_refused_repo_in_the_fallback_is_an_error(ts) -> None:
    """A lower bound cannot prove the run is under the cap."""
    base = _gh(search=403)

    def gh(method, path, body=None):
        if "mcp-server-cookbook" in path and "state=open" in path:
            return 502, {"message": "Bad Gateway"}
        return base(method, path, body)

    ts.gh = gh
    with pytest.raises(ts.GitHubReadError, match="mcp-server-cookbook"):
        ts.count_open_trending_issues(ts.ALL_REPOS)


def test_a_refused_cap_read_exits_1_before_any_evaluation(ts, monkeypatch, capsys) -> None:
    evaluated: list = []
    monkeypatch.setattr(ts, "call_claude_eval", lambda k, f: evaluated.append(f))
    ts.gh = _gh(search=403, listing=403)
    monkeypatch.setattr(sys, "argv", ["trending_scan", "--mode", "daily"])
    monkeypatch.setattr(ts, "gather_findings", lambda mode: pytest.fail("gathered"))
    assert ts.main() == 1
    assert evaluated == []
    assert "verified cap" in capsys.readouterr().err


# ----------------------------------------------------------------------
# The dedupe
# ----------------------------------------------------------------------


def test_a_refused_first_page_is_an_error_not_an_empty_set(ts) -> None:
    ts.gh = _gh(titles=401)
    with pytest.raises(ts.GitHubReadError, match="page 1 returned 401"):
        ts.existing_issue_titles("rag-production-kit")


def test_a_refused_later_page_is_an_error_not_a_partial_set(ts) -> None:
    ts.gh = _gh(titles_page2=500)
    with pytest.raises(ts.GitHubReadError, match="page 2 returned 500"):
        ts.existing_issue_titles("rag-production-kit")


def test_an_empty_first_page_is_still_none(ts) -> None:
    def gh(method, path, body=None):
        return 200, []

    ts.gh = gh
    assert ts.existing_issue_titles("rag-production-kit") == set()


def test_both_pages_read_finds_the_title_on_page_2(ts) -> None:
    ts.gh = _gh()
    assert "[trending] Already filed" in ts.existing_issue_titles("rag-production-kit")


def test_a_refused_dedupe_files_nothing_and_exits_1(ts, monkeypatch, capsys) -> None:
    posts: list = []
    assert _run_main(ts, monkeypatch, _gh(titles=403, posts=posts)) == 1
    assert posts == []
    err = capsys.readouterr().err
    assert "not filing" in err and "403" in err


def test_a_duplicate_found_on_page_2_is_skipped_at_exit_0(ts, monkeypatch) -> None:
    """Control: when every read answers, the dedupe works and the run is clean."""
    posts: list = []
    assert _run_main(ts, monkeypatch, _gh(posts=posts)) == 0
    assert posts == []


def test_a_new_title_is_filed_at_exit_0(ts, monkeypatch) -> None:
    posts: list = []
    gh = _gh(posts=posts)
    ts.gh = gh
    finding = ts.Finding(**{f.name: "x" for f in dataclasses.fields(ts.Finding)})
    monkeypatch.setattr(ts, "gather_findings", lambda mode: [finding])
    monkeypatch.setattr(
        ts, "call_claude_eval", lambda k, f: {"map": "rag-production-kit", "title": "Brand new"}
    )
    monkeypatch.setattr(sys, "argv", ["trending_scan", "--mode", "daily"])
    assert ts.main() == 0
    assert posts == ["/repos/jt-mchorse/rag-production-kit/issues"]
