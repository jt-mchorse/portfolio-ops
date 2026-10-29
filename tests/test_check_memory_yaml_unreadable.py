"""`check_memory_yaml.py --root`: an unreadable repo does not stop the run (#118).

Until #118 the per-repo loop returned 2 on the first missing clone, ref or
file, so every repo after it went unread. Phase A logs exit 2 as "usage/IO
error" and moves on, which means a regression in a later repo went unreported
for that run. Measured on 7015040: a root holding only
``repos/vector-search-at-scale``, with 20 bare ``[#1]`` blocks at origin/main,
gave ``REGRESSED`` rc 1 under ``--repo vector-search-at-scale`` and stopped at
``agent-orchestration-platform not found`` rc 2 in the documented form.

``aaa-missing`` sorts ahead of every real repo in each arm below, so the
unreadable repo is always met first, which is the order that hid the
regression.
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
    spec = importlib.util.spec_from_file_location("check_memory_yaml_unreadable", SCRIPT)
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
KINDS = ["history", "decisions"]


def _git(clone: Path, *args: str) -> None:
    subprocess.run(
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
    )


def _clone(root: Path, repo: str, content: dict[str, str]) -> Path:
    """A clone whose working tree and ``origin/main`` both hold ``content``."""
    clone = root / "repos" / repo
    (clone / "MEMORY").mkdir(parents=True)
    _git(clone, "init", "-q")
    for kind, name in FILES.items():
        (clone / "MEMORY" / name).write_text(content[kind])
    _git(clone, "add", "MEMORY")
    _git(clone, "commit", "-q", "-m", "main")
    _git(clone, "update-ref", "refs/remotes/origin/main", "HEAD")
    return clone


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    """aaa-missing: in the baseline, no clone. clean-repo: within baseline.
    zzz-regressed: one bad entry over a baseline of 0. Default runs take
    their repo list from the baseline, sorted, so aaa-missing is read first."""
    repos = ["aaa-missing", "clean-repo", "zzz-regressed"]
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "unparseable_by_repo": dict.fromkeys(repos, 0),
                "unparseable_decisions_by_repo": dict.fromkeys(repos, 0),
            }
        )
    )
    monkeypatch.setattr(_MODULE, "BASELINE_PATH", baseline)
    _clone(tmp_path, "clean-repo", GOOD)
    _clone(tmp_path, "zzz-regressed", BAD)
    return tmp_path


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    rc = _MODULE.main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


@pytest.mark.parametrize("kind", KINDS)
def test_a_missing_clone_ahead_of_a_regression_is_exit_1_at_a_ref(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The documented Phase A form: every baseline repo, at origin/main."""
    rc, out, err = _run(capsys, "--root", str(root), "--ref", "origin/main", "--kind", kind)
    assert rc == 1, out + err
    assert "zzz-regressed" in out and "REGRESSED" in out, out
    assert "aaa-missing" in err, err


@pytest.mark.parametrize("kind", KINDS)
def test_a_missing_file_ahead_of_a_regression_is_exit_1_in_the_working_tree(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same loop without --ref had the same early return."""
    rc, out, err = _run(capsys, "--root", str(root), "--kind", kind)
    assert rc == 1, out + err
    assert "zzz-regressed" in out and "REGRESSED" in out, out
    assert "aaa-missing" in err, err


@pytest.mark.parametrize("kind", KINDS)
def test_a_missing_ref_ahead_of_a_regression_is_exit_1(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clone that exists but has no origin/main, the other IO error."""
    _clone(root, "aaa-missing", GOOD)
    _git(root / "repos" / "aaa-missing", "update-ref", "-d", "refs/remotes/origin/main")
    rc, out, err = _run(capsys, "--root", str(root), "--ref", "origin/main", "--kind", kind)
    assert rc == 1, out + err
    assert "zzz-regressed" in out and "REGRESSED" in out, out
    assert "aaa-missing" in err and "origin/main" in err, err


@pytest.mark.parametrize("kind", KINDS)
def test_a_file_absent_at_the_ref_ahead_of_a_regression_is_exit_1(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    clone = _clone(root, "aaa-missing", GOOD)
    _git(clone, "rm", "-q", f"MEMORY/{FILES[kind]}")
    _git(clone, "commit", "-q", "-m", "drop")
    _git(clone, "update-ref", "refs/remotes/origin/main", "HEAD")
    rc, out, err = _run(capsys, "--root", str(root), "--ref", "origin/main", "--kind", kind)
    assert rc == 1, out + err
    assert "zzz-regressed" in out and "REGRESSED" in out, out


@pytest.mark.parametrize("kind", KINDS)
def test_an_io_error_with_no_regression_is_exit_2_and_every_repo_is_still_read(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 2 still means an IO error, but it is now decided after the loop:
    the repos after the unreadable one are each printed."""
    rc, out, err = _run(
        capsys,
        "--root",
        str(root),
        "--ref",
        "origin/main",
        "--kind",
        kind,
        "--repo",
        "aaa-missing",
        "--repo",
        "clean-repo",
    )
    assert rc == 2, out + err
    assert "clean-repo" in out and "ok" in out, out
    assert "aaa-missing" in err, err


@pytest.mark.parametrize("kind", KINDS)
def test_every_repo_readable_and_clean_is_still_exit_0(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Control: green on the pre-#118 script too."""
    rc, out, err = _run(
        capsys, "--root", str(root), "--ref", "origin/main", "--kind", kind, "--repo", "clean-repo"
    )
    assert rc == 0, out + err


def test_write_baseline_writes_nothing_when_a_repo_is_unreadable(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Control: the pre-#118 script returned 2 before reaching the write too.
    Pinned so that keeping the loop going cannot start freezing a partial
    baseline."""
    before = _MODULE.BASELINE_PATH.read_text()
    rc, out, err = _run(capsys, "--root", str(root), "--ref", "origin/main", "--write-baseline")
    assert rc == 2, out + err
    assert _MODULE.BASELINE_PATH.read_text() == before
    assert "wrote" not in out
