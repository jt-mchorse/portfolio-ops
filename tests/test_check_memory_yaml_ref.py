"""`check_memory_yaml.py --root --ref`: ratchet what is on main, not the checkout (#112).

Phase A is the only place the cross-repo ratchet runs, and it runs over the
local clones under ``~/projects/portfolio``. Those clones are wherever the last
session left them. On 2026-10-26, 12 of the 13 were on old ``session/*``
branches or a detached HEAD, and a working-tree ``--root`` run reported 7 repos
REGRESSED (aop, aiapp, ems, lco, leh, rag, vsas) on damage that #109 had
already repaired on main. The same run with ``--ref origin/main`` exited 0.

These arms build real git clones in which the working tree and ``origin/main``
disagree, in both directions. A ``--ref`` that silently fell back to the working
tree would be green on one direction only.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
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

GOOD = {
    "history": '---\nsession: 2026-01-01\nfollowups: ["#1"]\n---\n',
    "decisions": '- id: D-001\n  related_issues: ["#1"]\n\n',
}
BAD = {
    "history": GOOD["history"] + "---\nsession: 2026-01-02\nfollowups: [#2]\n---\n",
    "decisions": GOOD["decisions"] + "- id: D-002\n  related_issues: [#2]\n\n",
}
FILES = {"history": "full_history_ai.md", "decisions": "core_decisions_ai.md"}


def _git(clone: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(clone),
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _clone(root: Path, repo: str, *, main: dict[str, str], tree: dict[str, str]) -> Path:
    """A clone whose ``origin/main`` holds ``main`` and whose checked-out
    ``session/old`` branch holds ``tree``, which is the shape Phase A meets."""
    clone = root / "portfolio-ops" if repo == "portfolio-ops" else root / "repos" / repo
    (clone / "MEMORY").mkdir(parents=True)
    _git(clone, "init", "-q")
    for kind, name in FILES.items():
        (clone / "MEMORY" / name).write_text(main[kind])
    _git(clone, "add", "MEMORY")
    _git(clone, "commit", "-q", "-m", "main")
    _git(clone, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(clone, "checkout", "-q", "-b", "session/old")
    for kind, name in FILES.items():
        (clone / "MEMORY" / name).write_text(tree[kind])
    _git(clone, "commit", "-q", "-am", "old session branch")
    return clone


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    """alpha-repo: main clean, checkout damaged (the 10-26 false alarm).
    beta-repo: main damaged, checkout clean (a real regression a working-tree
    read would hide). Every baseline allows 0."""
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "unparseable_by_repo": {"alpha-repo": 0, "beta-repo": 0},
                "unparseable_decisions_by_repo": {"alpha-repo": 0, "beta-repo": 0},
            }
        )
    )
    monkeypatch.setattr(_MODULE, "BASELINE_PATH", baseline)
    _clone(tmp_path, "alpha-repo", main=GOOD, tree=BAD)
    _clone(tmp_path, "beta-repo", main=BAD, tree=GOOD)
    return tmp_path


@pytest.mark.parametrize("kind", ["history", "decisions"])
def test_a_stale_checkout_is_not_a_regression_at_origin_main(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _MODULE.main(
        ["--root", str(root), "--kind", kind, "--repo", "alpha-repo", "--ref", "origin/main"]
    )
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "alpha-repo" in out and "0 / 1" in out, out


@pytest.mark.parametrize("kind", ["history", "decisions"])
def test_a_regression_on_origin_main_is_caught_under_a_clean_checkout(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _MODULE.main(
        ["--root", str(root), "--kind", kind, "--repo", "beta-repo", "--ref", "origin/main"]
    )
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "REGRESSED" in out, out


@pytest.mark.parametrize("kind", ["history", "decisions"])
def test_without_ref_the_working_tree_is_still_what_is_read(
    root: Path, kind: str
) -> None:
    """Control: the existing --root behaviour is unchanged when --ref is absent.
    Green on the pre-#112 script too."""
    assert _MODULE.main(["--root", str(root), "--kind", kind, "--repo", "alpha-repo"]) == 1
    assert _MODULE.main(["--root", str(root), "--kind", kind, "--repo", "beta-repo"]) == 0


def test_reading_at_a_ref_leaves_the_checkout_alone(root: Path) -> None:
    clone = root / "repos" / "alpha-repo"
    before = (clone / "MEMORY" / FILES["history"]).read_text()
    _MODULE.main(["--root", str(root), "--ref", "origin/main"])
    assert _git(clone, "rev-parse", "--abbrev-ref", "HEAD") == "session/old"
    assert (clone / "MEMORY" / FILES["history"]).read_text() == before
    assert _git(clone, "status", "--porcelain") == ""


def test_a_missing_ref_is_exit_2_naming_the_clone(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _MODULE.main(["--root", str(root), "--ref", "origin/no-such-branch"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "alpha-repo" in err and "origin/no-such-branch" in err, err


def test_a_missing_clone_is_exit_2_not_a_silent_pass(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _MODULE.main(["--root", str(root), "--repo", "gamma-repo", "--ref", "origin/main"])
    assert rc == 2
    assert "gamma-repo" in capsys.readouterr().err


def test_a_file_absent_at_the_ref_is_exit_2(root: Path) -> None:
    clone = root / "repos" / "alpha-repo"
    _git(clone, "rm", "-q", "MEMORY/core_decisions_ai.md")
    _git(clone, "commit", "-q", "-m", "drop decisions")
    _git(clone, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert (
        _MODULE.main(
            ["--root", str(root), "--kind", "decisions", "--repo", "alpha-repo", "--ref", "origin/main"]
        )
        == 2
    )


def test_ref_with_file_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "full_history_ai.md"
    path.write_text(GOOD["history"])
    with pytest.raises(SystemExit) as exc:
        _MODULE.main(["--file", str(path), "--repo", "x", "--ref", "origin/main"])
    assert exc.value.code == 2
    assert "cannot be combined with --file" in capsys.readouterr().err
