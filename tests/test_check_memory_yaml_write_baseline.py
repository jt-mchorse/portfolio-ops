"""Lock: ``--write-baseline`` merges into the per-kind map, never replaces it (#111).

Until #111 the write was ``data[key] = counts``, and ``counts`` holds only the
repos the run checked. A ``--repo`` or ``--file`` re-freeze, which is the
pending nextjs 13 -> 11 re-freeze from #66 and also the form CI runs, deleted
every other repo's entry. A default run takes its repo list from
``sorted(baseline)``, so those repos then dropped out of the ratchet with
rc 0 and no message. Measured on an origin/main snapshot of all 13 repos:
after ``--repo nextjs-streaming-ai-patterns --write-baseline`` the next default
run printed one line, not thirteen.

``test_write_baseline_keeps_the_other_kinds_counts`` (#75) guarded the other
*kind*. These arms guard the other *repos*, for both kinds.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_memory_yaml.py"

pytest.importorskip("yaml")


def _load_module():
    spec = importlib.util.spec_from_file_location("check_memory_yaml", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MODULE = _load_module()

REPOS = ("alpha-repo", "beta-repo", "portfolio-ops")
BAD_HISTORY = "---\nsession: 2026-01-01\nfollowups: [#1]\n---\n"
GOOD_HISTORY = '---\nsession: 2026-01-02\nfollowups: ["#1"]\n---\n'
BAD_DECISION = "- id: D-001\n  related_issues: [#1]\n\n"
GOOD_DECISION = '- id: D-002\n  related_issues: ["#1"]\n\n'


def _baseline() -> dict[str, dict[str, int]]:
    return {
        "unparseable_by_repo": {"alpha-repo": 5, "beta-repo": 6, "portfolio-ops": 7},
        "unparseable_decisions_by_repo": {
            "alpha-repo": 2,
            "beta-repo": 3,
            "portfolio-ops": 4,
        },
    }


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    """A checkout root where every repo has ONE bad entry of each kind, and a
    baseline that allows more, so any re-frozen repo visibly moves to 1."""
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(_baseline()))
    monkeypatch.setattr(_MODULE, "BASELINE_PATH", baseline)
    for repo in REPOS:
        mem = (
            tmp_path / "portfolio-ops" / "MEMORY"
            if repo == "portfolio-ops"
            else tmp_path / "repos" / repo / "MEMORY"
        )
        mem.mkdir(parents=True)
        (mem / "full_history_ai.md").write_text(BAD_HISTORY + GOOD_HISTORY)
        (mem / "core_decisions_ai.md").write_text(BAD_DECISION + GOOD_DECISION)
    return tmp_path


def _written(root: Path) -> dict:
    return json.loads((root / "baseline.json").read_text())


@pytest.mark.parametrize(
    ("kind", "key", "other_key"),
    [
        ("history", "unparseable_by_repo", "unparseable_decisions_by_repo"),
        ("decisions", "unparseable_decisions_by_repo", "unparseable_by_repo"),
    ],
)
def test_a_one_repo_write_changes_that_repo_only(
    root: Path, kind: str, key: str, other_key: str
) -> None:
    rc = _MODULE.main(
        ["--root", str(root), "--kind", kind, "--repo", "beta-repo", "--write-baseline"]
    )
    assert rc == 0
    data = _written(root)
    expected = dict(_baseline()[key], **{"beta-repo": 1})
    assert data[key] == expected
    assert data[other_key] == _baseline()[other_key]


@pytest.mark.parametrize("kind", ["history", "decisions"])
def test_the_ci_file_form_keeps_every_other_repo(root: Path, kind: str) -> None:
    """The exact shape tests.yml runs: --file MEMORY/... --repo portfolio-ops."""
    key = _MODULE.KINDS[kind]["key"]
    path = root / "portfolio-ops" / "MEMORY" / _MODULE.KINDS[kind]["file"]
    rc = _MODULE.main(
        [
            "--kind",
            kind,
            "--file",
            str(path),
            "--repo",
            "portfolio-ops",
            "--write-baseline",
        ]
    )
    assert rc == 0
    assert _written(root)[key] == dict(_baseline()[key], **{"portfolio-ops": 1})


@pytest.mark.parametrize("kind", ["history", "decisions"])
def test_a_full_write_still_refreezes_every_repo(root: Path, kind: str) -> None:
    """Control: a default run checks every baseline repo, so merging and
    replacing agree there. This arm is green on the unfixed script too."""
    key = _MODULE.KINDS[kind]["key"]
    rc = _MODULE.main(["--root", str(root), "--kind", kind, "--write-baseline"])
    assert rc == 0
    assert _written(root)[key] == {repo: 1 for repo in REPOS}


def test_a_new_repo_is_added_without_dropping_the_rest(root: Path) -> None:
    mem = root / "repos" / "gamma-repo" / "MEMORY"
    mem.mkdir(parents=True)
    (mem / "full_history_ai.md").write_text(GOOD_HISTORY)
    rc = _MODULE.main(["--root", str(root), "--repo", "gamma-repo", "--write-baseline"])
    assert rc == 0
    written = _written(root)["unparseable_by_repo"]
    assert written == dict(_baseline()["unparseable_by_repo"], **{"gamma-repo": 0})
    assert list(written) == sorted(written)


def test_the_next_default_run_still_checks_every_repo(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The consequence the issue measured: after a one-repo re-freeze, a
    default run must still print, and so still ratchet, every repo."""
    assert (
        _MODULE.main(["--root", str(root), "--repo", "beta-repo", "--write-baseline"])
        == 0
    )
    capsys.readouterr()
    assert _MODULE.main(["--root", str(root)]) == 0
    out = capsys.readouterr().out
    for repo in REPOS:
        assert repo in out, out
