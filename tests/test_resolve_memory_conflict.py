"""Tests for `scripts/resolve_memory_conflict.py`.

The resolver handles append-only rebase conflicts in MEMORY/full_history_*.md.
Fixtures here are hand-rolled minimal shapes — no real repo state required.

Related: portfolio-ops#11.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "resolve_memory_conflict.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("resolve_memory_conflict", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


# ---- YAML fixtures ----------------------------------------------------------

# Real-world conflict shape reproduced from `git merge` on
# MEMORY/full_history_ai.md (verified empirically): the `---` opener of the
# new block stays in the prefix (above the `<<<<<<<` marker) and the trailer
# (`decisions_made: []`, `followups: []`, `---`) is shared after the
# `>>>>>>>` marker because git's diff aligns on the repeated trailer lines.
YAML_CONFLICT = """\
# Session History (AI-readable, append-only)

Schema: see .skills/portfolio-memory/SKILL.md

---
session: 2026-05-26T00:00Z
duration_min: 30
issue: 100
focus: prior_session
decisions_made: []
followups: []
---

---
<<<<<<< HEAD
session: 2026-05-27T01:00Z
duration_min: 15
issue: 200
focus: branch_a_work
=======
session: 2026-05-27T02:00Z
duration_min: 20
issue: 201
focus: branch_b_work
>>>>>>> abc1234 (branch b commit)
decisions_made: []
followups: []
---
"""

YAML_EXPECTED = """\
# Session History (AI-readable, append-only)

Schema: see .skills/portfolio-memory/SKILL.md

---
session: 2026-05-26T00:00Z
duration_min: 30
issue: 100
focus: prior_session
decisions_made: []
followups: []
---

---
session: 2026-05-27T01:00Z
duration_min: 15
issue: 200
focus: branch_a_work
decisions_made: []
followups: []
---

---
session: 2026-05-27T02:00Z
duration_min: 20
issue: 201
focus: branch_b_work
decisions_made: []
followups: []
---
"""

# ---- MD fixtures ------------------------------------------------------------

MD_CONFLICT = """\
# Session History (human-readable)

---

## 2026-05-26 — Issue #100
**Duration:** ~30 min

- Prior session entry kept verbatim.

<<<<<<< HEAD
## 2026-05-27 — Issue #200 (branch a)
**Duration:** ~15 min

- Branch a body line one.
- Branch a body line two.
=======
## 2026-05-27 — Issue #201 (branch b)
**Duration:** ~20 min

- Branch b body line one.
>>>>>>> abc1234 (branch b commit)
"""

MD_EXPECTED = """\
# Session History (human-readable)

---

## 2026-05-26 — Issue #100
**Duration:** ~30 min

- Prior session entry kept verbatim.

## 2026-05-27 — Issue #200 (branch a)
**Duration:** ~15 min

- Branch a body line one.
- Branch a body line two.

## 2026-05-27 — Issue #201 (branch b)
**Duration:** ~20 min

- Branch b body line one.
"""


# ---- YAML tests -------------------------------------------------------------


def test_resolve_yaml_removes_conflict_markers(mod) -> None:
    out = mod.resolve_yaml(YAML_CONFLICT)
    assert "<<<<<<<" not in out
    assert "=======" not in out
    assert ">>>>>>>" not in out


def test_resolve_yaml_keeps_both_blocks(mod) -> None:
    out = mod.resolve_yaml(YAML_CONFLICT)
    assert "branch_a_work" in out
    assert "branch_b_work" in out


def test_resolve_yaml_block_order_preserved(mod) -> None:
    out = mod.resolve_yaml(YAML_CONFLICT)
    assert out.index("branch_a_work") < out.index("branch_b_work")


def test_resolve_yaml_trailer_attached_to_first_block(mod) -> None:
    """Each kept block must end with the standard YAML trailer so it parses
    independently. Counting trailers verifies block_a gets one (it wasn't in
    the conflict, the resolver had to add it)."""
    out = mod.resolve_yaml(YAML_CONFLICT)
    assert out.count("decisions_made: []\nfollowups: []\n---") == 3  # prior + a + b


def test_resolve_yaml_matches_expected(mod) -> None:
    assert mod.resolve_yaml(YAML_CONFLICT) == YAML_EXPECTED


def test_resolve_yaml_noop_on_clean_text(mod) -> None:
    clean = "session: foo\ndecisions_made: []\nfollowups: []\n---\n"
    assert mod.resolve_yaml(clean) == clean


# ---- MD tests ---------------------------------------------------------------


def test_resolve_md_removes_conflict_markers(mod) -> None:
    out = mod.resolve_md(MD_CONFLICT)
    assert "<<<<<<<" not in out
    assert "=======" not in out
    assert ">>>>>>>" not in out


def test_resolve_md_keeps_both_blocks(mod) -> None:
    out = mod.resolve_md(MD_CONFLICT)
    assert "branch a" in out
    assert "branch b" in out


def test_resolve_md_block_order_preserved(mod) -> None:
    out = mod.resolve_md(MD_CONFLICT)
    assert out.index("branch a") < out.index("branch b")


def test_resolve_md_matches_expected(mod) -> None:
    assert mod.resolve_md(MD_CONFLICT) == MD_EXPECTED


def test_resolve_md_noop_on_clean_text(mod) -> None:
    clean = "## Some session\n\n- bullet\n"
    assert mod.resolve_md(clean) == clean


# ---- CLI integration tests --------------------------------------------------


def test_main_resolves_real_filesystem(mod, tmp_path: Path) -> None:
    repo = tmp_path / "fake-repo"
    memory = repo / "MEMORY"
    memory.mkdir(parents=True)
    ai = memory / "full_history_ai.md"
    human = memory / "full_history_human.md"
    ai.write_text(YAML_CONFLICT, encoding="utf-8")
    human.write_text(MD_CONFLICT, encoding="utf-8")

    exit_code = mod.main([str(repo)])

    assert exit_code == 0
    assert "<<<<<<<" not in ai.read_text(encoding="utf-8")
    assert "<<<<<<<" not in human.read_text(encoding="utf-8")
    assert ai.read_text(encoding="utf-8") == YAML_EXPECTED
    assert human.read_text(encoding="utf-8") == MD_EXPECTED


def test_main_dry_run_does_not_write(mod, tmp_path: Path) -> None:
    repo = tmp_path / "fake-repo"
    memory = repo / "MEMORY"
    memory.mkdir(parents=True)
    ai = memory / "full_history_ai.md"
    ai.write_text(YAML_CONFLICT, encoding="utf-8")

    exit_code = mod.main([str(repo), "--dry-run"])

    assert exit_code == 0
    assert ai.read_text(encoding="utf-8") == YAML_CONFLICT


def test_main_missing_memory_dir_errors(mod, tmp_path: Path) -> None:
    repo = tmp_path / "no-memory"
    repo.mkdir()
    exit_code = mod.main([str(repo)])
    assert exit_code == 1


def test_main_no_conflicts_returns_zero(mod, tmp_path: Path) -> None:
    repo = tmp_path / "clean-repo"
    memory = repo / "MEMORY"
    memory.mkdir(parents=True)
    (memory / "full_history_ai.md").write_text("clean content\n", encoding="utf-8")
    (memory / "full_history_human.md").write_text("clean content\n", encoding="utf-8")
    assert mod.main([str(repo)]) == 0
