"""The decisions ratchet counts a repeated key and a repeated id (#117).

#107 taught the history counter that a block can load and still have lost an
entry: ``yaml.safe_load`` keeps the last copy of a repeated key and says
nothing. ``--kind decisions`` had no such check. Two branches that each append
``- id: D-002`` and merge cleanly under ``MEMORY/*.md merge=union`` leave one
entry with ``title``/``status``/``related_issues`` twice, which loads as the
later decision alone and passed the ratchet as ``0 / 2``.

The glued arms build the entry the way it is really made: a real ``git merge``
with the #107 attribute in ``.git/info/attributes``.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_memory_yaml.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_memory_yaml", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


count = _load_module().count_unparseable_decisions

BASE = '- id: D-001\n  title: "base"\n  status: accepted\n  related_issues: ["#1"]\n'


def _decision(id_: str, title: str, issue: str) -> str:
    return (
        f'\n- id: {id_}\n  title: "{title}"\n  status: accepted\n'
        f'  related_issues: ["{issue}"]\n'
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )


def _union_merge(repo: Path, ours: str, theirs: str) -> str:
    """Append ``ours`` on main and ``theirs`` on a branch, union-merge, return the file."""
    f = repo / "MEMORY" / "core_decisions_ai.md"
    f.parent.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main", ".")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    f.write_text(BASE, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "side")
    f.write_text(BASE + theirs, encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "theirs")
    _git(repo, "checkout", "-q", "main")
    f.write_text(BASE + ours, encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "ours")
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "attributes").write_text(
        "MEMORY/*.md merge=union\n", encoding="utf-8"
    )
    merge = _git(repo, "merge", "-q", "side", "-m", "merge")
    assert merge.returncode == 0, merge.stdout + merge.stderr
    return f.read_text(encoding="utf-8")


def test_a_union_merge_of_two_same_id_appends_is_counted(tmp_path: Path) -> None:
    """The issue's repro: one `- id: D-002` line, every other line kept twice."""
    text = _union_merge(
        tmp_path,
        _decision("D-002", "beta choice", "#3"),
        _decision("D-002", "alpha choice", "#2"),
    )
    assert text.count("- id: D-002") == 1 and text.count("title:") == 3, text
    bad, total, reasons = count(text)
    assert (bad, total) == (1, 2), text
    assert reasons == ["- id: D-002: duplicate key(s): title, status, related_issues"]


def test_a_union_merged_file_regresses_the_cli(tmp_path: Path) -> None:
    text = _union_merge(
        tmp_path / "repo",
        _decision("D-002", "beta choice", "#3"),
        _decision("D-002", "alpha choice", "#2"),
    )
    f = tmp_path / "core_decisions_ai.md"
    f.write_text(text, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--kind", "decisions", "--file", str(f)]
        + ["--repo", "no-such-repo"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "1 / 2" in proc.stdout and "REGRESSED" in proc.stdout
    assert "duplicate key(s): title" in proc.stderr


def test_a_repeated_id_across_whole_entries_is_counted() -> None:
    """Two entries each loadable on their own, one id: the later copy counts.
    A union merge never writes this (both appends share the id line, so it is
    kept once); a conflict resolved by keeping both sides does."""
    text = BASE + _decision("D-002", "a", "#2") + _decision("D-002", "b", "#3")
    bad, total, reasons = count(text)
    assert (bad, total) == (1, 3)
    assert reasons == ["- id: D-002: duplicate id"]


def test_a_quoted_id_repeats_a_bare_one() -> None:
    text = BASE + _decision("D-002", "a", "#2") + _decision('"D-002"', "b", "#3")
    bad, _, reasons = count(text)
    assert bad == 1 and reasons == ['- id: "D-002": duplicate id']


def test_an_unloadable_entry_still_claims_its_id() -> None:
    """The id is read from the `- id:` line, so a first copy that fails to load
    (the D-013 bare `#`) still makes a later copy a repeat."""
    broken = "\n- id: D-002\n  related_issues: [#2]\n"
    text = BASE + broken + _decision("D-002", "b", "#3")
    bad, total, reasons = count(text)
    assert (bad, total) == (2, 3)
    assert reasons[1] == "- id: D-002: duplicate id"


def test_distinct_ids_sharing_a_prefix_are_not_counted() -> None:
    """Control: D-002 and D-020 are two ids, and a trailing comment is not part
    of the id."""
    text = (
        BASE
        + _decision("D-002", "a", "#2")
        + _decision("D-020", "b", "#3")
        + _decision("D-021  # superseded", "c", "#4")
    )
    assert count(text) == (0, 4, [])


def test_a_key_repeated_under_different_parents_is_not_counted() -> None:
    """Control: only the entry's own mapping is checked, as #107 checks only a
    block's top level. `count` in two nested mappings is not a repeat."""
    text = BASE + (
        "\n- id: D-002\n  measured:\n    count: 1\n  baseline:\n    count: 2\n"
    )
    assert count(text) == (0, 2, [])


def test_an_unloadable_entry_with_a_repeated_key_is_counted_once() -> None:
    """Control: an entry that already fails to load is one failure, not two."""
    text = BASE + '\n- id: D-002\n  title: "a"\n  title: "b"\n  related_issues: [#2]\n'
    bad, total, reasons = count(text)
    assert (bad, total) == (1, 2)
    assert "duplicate" not in reasons[0]
