"""The decisions-file half of the MEMORY YAML ratchet (#75, D-013).

`related_issues: [#188, #106]` is `related_issues: [` followed by a comment --
the mechanism D-010 settled for `followups` in `full_history_ai.md`, in a file
and a key D-010's own `scope:` line did not walk. `core_decisions_ai.md` is ONE
YAML sequence, so the first such line makes `yaml.safe_load` of the whole file
fail: when #75 measured it, a consumer could read zero decisions in 12 of 12
code repos, and `memory-check` was green on all of them because it asks
`test -f` and `grep -q "id: D-001"`, neither of which is a claim about YAML.

The unit is one `- id:` entry, loaded on its own. A whole-file load would say
"broken" for one bad entry and for ten, so it could neither see a new bad entry
arrive in an already-broken file nor credit a repair -- which in a file that is
broken everywhere today is the only thing a ratchet is for.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_memory_yaml.py"

yaml = pytest.importorskip("yaml")


def _load_module():
    spec = importlib.util.spec_from_file_location("check_memory_yaml", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MODULE = _load_module()


# Resolved at call time, not import time, so a revert probe against the
# pre-#75 script reports each arm red rather than one collection error.
def count(text: str) -> tuple[int, int, list[str]]:
    return _MODULE.count_unparseable_decisions(text)


def load_baseline(kind: str) -> dict[str, int]:
    return _MODULE.load_baseline(kind)


HEADER = "# Core Decisions (AI-readable, YAML, append-only)\n# Schema: see SKILL.md\n\n"


def _entry(n: int, related: str = "[]", alternatives: str = "[]") -> str:
    return f"""- id: D-{n:03d}
  date: 2026-01-01
  decision: a_thing
  alternatives_rejected: {alternatives}
  reversibility: cheap
  related_issues: {related}
  superseded_by: null

"""


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


# ----------------------------------------------------------------------
# The defect, and why the unit is the entry
# ----------------------------------------------------------------------


def test_one_bare_hash_makes_the_whole_file_unloadable() -> None:
    """The premise of #75, as the consumer sees it: not one entry lost, all."""
    text = HEADER + _entry(1) + _entry(2, "[#75]") + _entry(3)
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(text)
    assert count(text)[:2] == (1, 3)


def test_each_bad_entry_is_counted_once_and_good_ones_are_not() -> None:
    text = (
        HEADER
        + _entry(1, "[#1]")
        + _entry(2)
        + _entry(3, "[#3, #4]")
        + _entry(4, '["#5"]')
    )
    bad, total, reasons = count(text)
    assert (bad, total) == (2, 4)
    assert reasons[0].startswith("- id: D-001")
    assert reasons[1].startswith("- id: D-003")


@pytest.mark.parametrize(
    ("related", "alternatives"),
    [
        ("[#75]", "[]"),
        ("[ #75 ]", "[]"),
        ("[leh#212, #66]", "[]"),
        ("[]", "[#3_was_considered]"),
    ],
)
def test_a_bare_hash_in_any_list_breaks_its_entry(
    related: str, alternatives: str
) -> None:
    """D-013's rule is "every list item", not "related_issues": the mechanism
    is the flow sequence, and the key it happens to sit under is incidental."""
    assert count(HEADER + _entry(1, related, alternatives))[:2] == (1, 1)


@pytest.mark.parametrize(
    "related", ['["#75"]', '["#75", "#66"]', '["leh#212"]', "[leh#212]", "[]"]
)
def test_the_quoted_form_and_the_cross_repo_form_load(related: str) -> None:
    assert count(HEADER + _entry(1, related))[:2] == (0, 1)


def test_per_entry_counting_agrees_with_a_whole_file_load_once_repaired() -> None:
    """A per-entry split is only honest if it cannot report a file clean that
    a whole-file load still rejects. Repair every entry and both must agree."""
    broken = HEADER + _entry(1, "[#1]") + "# D-001 superseded\n" + _entry(2, "[#2, #3]")
    repaired = broken.replace("[#1]", '["#1"]').replace("[#2, #3]", '["#2", "#3"]')
    assert count(broken)[0] == 2
    assert count(repaired)[0] == 0
    loaded = yaml.safe_load(repaired)
    assert [d["id"] for d in loaded] == ["D-001", "D-002"]


def test_the_header_and_interleaved_comments_are_not_entries() -> None:
    text = HEADER + _entry(1) + "# D-002 superseded by D-003\n" + _entry(2)
    assert count(text)[:2] == (0, 2)
    assert count(HEADER)[:2] == (0, 0)


def test_an_entry_that_loads_as_something_other_than_one_mapping_counts() -> None:
    """`- id: D-001` followed by a dedented key loads, but not as a decision."""
    text = "- id: D-001\n  date: 2026-01-01\n- stray\n"
    assert count(text)[0] == 1


# ----------------------------------------------------------------------
# The ratchet and the CLI
# ----------------------------------------------------------------------


def test_this_repos_decisions_file_is_within_its_baseline() -> None:
    proc = _run(
        "--kind",
        "decisions",
        "--file",
        str(REPO_ROOT / "MEMORY" / "core_decisions_ai.md"),
        # As CI passes it (#102); the directory name is not the repo's in a worktree.
        "--repo",
        "portfolio-ops",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_an_unquoted_new_entry_regresses_and_names_d013(tmp_path: Path) -> None:
    allowed = load_baseline("decisions")["portfolio-ops"]
    path = tmp_path / "core_decisions_ai.md"
    path.write_text(
        HEADER + "".join(_entry(i + 1, f"[#{i}]") for i in range(allowed + 1))
    )
    proc = _run("--kind", "decisions", "--file", str(path), "--repo", "portfolio-ops")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "REGRESSED" in proc.stdout
    assert "D-013" in proc.stderr
    assert 'related_issues: ["#75"]' in proc.stderr
    assert "decision entries" in proc.stderr


def test_a_quoted_new_entry_on_top_of_the_baseline_passes(tmp_path: Path) -> None:
    allowed = load_baseline("decisions")["portfolio-ops"]
    path = tmp_path / "core_decisions_ai.md"
    bad = "".join(_entry(i + 1, f"[#{i}]") for i in range(allowed))
    path.write_text(HEADER + bad + _entry(allowed + 1, '["#75"]'))
    proc = _run("--kind", "decisions", "--file", str(path), "--repo", "portfolio-ops")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_two_kinds_ratchet_against_their_own_baselines() -> None:
    """A history count must never be compared to a decisions allowance, or a
    repo with 10 bad session blocks could add 10 bad decisions unnoticed."""
    data = json.loads((REPO_ROOT / "scripts" / "memory_yaml_baseline.json").read_text())
    assert set(data["unparseable_by_repo"]) == set(
        data["unparseable_decisions_by_repo"]
    )
    assert load_baseline("history") == {
        k: int(v) for k, v in data["unparseable_by_repo"].items()
    }
    assert load_baseline("decisions") == {
        k: int(v) for k, v in data["unparseable_decisions_by_repo"].items()
    }


def test_default_kind_is_still_the_history_file(tmp_path: Path) -> None:
    """Every existing invocation (CI, Phase A, scripts/README) passes no --kind
    and must keep meaning what #66 shipped."""
    path = tmp_path / "full_history_ai.md"
    path.write_text("---\nsession: 2026-01-01\nfollowups: [#1]\n---\n")
    proc = _run("--file", str(path), "--repo", "brand-new-repo")
    assert proc.returncode == 1
    assert "D-010" in proc.stderr


def test_write_baseline_keeps_the_other_kinds_counts(
    tmp_path: Path, monkeypatch
) -> None:
    """Regenerating one kind must not erase the other kind's frozen counts --
    a dropped key reads as "no allowance", which is a different ratchet."""
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"unparseable_by_repo": {"portfolio-ops": 6}}))
    monkeypatch.setattr(_MODULE, "BASELINE_PATH", baseline)
    path = tmp_path / "core_decisions_ai.md"
    path.write_text(HEADER + _entry(1, "[#1]") + _entry(2))
    rc = _MODULE.main(
        [
            "--kind",
            "decisions",
            "--file",
            str(path),
            "--repo",
            "portfolio-ops",
            "--write-baseline",
        ]
    )
    assert rc == 0
    data = json.loads(baseline.read_text())
    assert data["unparseable_by_repo"] == {"portfolio-ops": 6}
    assert data["unparseable_decisions_by_repo"] == {"portfolio-ops": 1}


def test_ci_runs_the_decisions_ratchet() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "tests.yml").read_text()
    assert (
        "check_memory_yaml.py --kind decisions --file MEMORY/core_decisions_ai.md"
        in workflow
    )


def test_the_skill_template_teaches_the_quoted_form() -> None:
    """The template in the skill was itself `related_issues: [#NN, #NN]`, so
    every session that copied it wrote the unloadable spelling."""
    skill = (REPO_ROOT / "skills" / "portfolio-memory" / "SKILL.md").read_text()
    assert "related_issues: [#" not in skill
    assert 'related_issues: ["#NN", "#NN"]' in skill
