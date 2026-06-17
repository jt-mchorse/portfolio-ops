"""Lock that every workflow YAML in this repo parses cleanly.

PR #28 / issue #27 closed a 21-day silent CI outage caused by a single
unquoted colon-space in `.github/workflows/ci.yml`:

    - name: Verify D-001 baseline decision exists
      run: grep -q "id: D-001" MEMORY/core_decisions_ai.md

`yaml.safe_load()` rejected line 37 with
`ScannerError: mapping values are not allowed here in line 37, column 25`.
GitHub Actions' lenient parser silently *completed* the workflow run with
zero jobs and `conclusion=failure`. `statusCheckRollup` stayed empty so PR
auto-merge in Phase A couldn't tell that no CI ran. Every push since
2026-05-27 hit this — direct main pushes too — and no PR-level signal made
it visible.

This file is the inverse-safety-net: parse every workflow under
`.github/workflows/` and `workflows/` with PyYAML and fail loudly if any
file is unparseable. A `jobs:` non-empty assertion catches the broader
"valid YAML, no actual workflow" failure mode in case GitHub Actions
silently absorbs another shape the same way.

Related: portfolio-ops#27, #28, #30.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
TEMPLATES_DIR = REPO_ROOT / "workflows"


def _all_workflow_files() -> list[Path]:
    files: list[Path] = []
    for directory in (ACTIVE_WORKFLOWS_DIR, TEMPLATES_DIR):
        if directory.is_dir():
            files.extend(sorted(directory.glob("*.yml")))
    return files


def _ids(files: list[Path]) -> list[str]:
    return [str(p.relative_to(REPO_ROOT)) for p in files]


WORKFLOW_FILES = _all_workflow_files()


def test_at_least_one_workflow_file_exists() -> None:
    # Smoke check: if this fails, the parametrized tests below silently degrade
    # to a no-op. The fixture-discovery boundary is its own assertion.
    assert WORKFLOW_FILES, (
        f"No *.yml files found under {ACTIVE_WORKFLOWS_DIR} or {TEMPLATES_DIR}. "
        "If the workflows were intentionally removed, delete this lock test."
    )


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=_ids(WORKFLOW_FILES))
def test_workflow_yaml_parses_cleanly(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # pragma: no cover - assertion message is the point
        rel = path.relative_to(REPO_ROOT)
        pytest.fail(
            f"{rel} failed yaml.safe_load:\n{exc}\n"
            "GitHub Actions' parser is lenient enough to *complete* a workflow "
            "with an unparseable file, emitting zero jobs and `conclusion=failure` "
            "with an empty `statusCheckRollup` — the exact silent-CI shape that "
            "blocked portfolio-ops for 21 days (#27). Fix the YAML, do not skip this lock."
        )
    assert isinstance(parsed, dict), (
        f"{path.relative_to(REPO_ROOT)} parsed to {type(parsed).__name__}, "
        "expected a top-level mapping. A workflow file should be a YAML mapping "
        "with at least `name`, `on`, and `jobs` keys."
    )


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=_ids(WORKFLOW_FILES))
def test_workflow_has_non_empty_jobs(path: Path) -> None:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    rel = path.relative_to(REPO_ROOT)
    jobs = parsed.get("jobs")
    assert isinstance(jobs, dict) and jobs, (
        f"{rel} parses but has no `jobs:` mapping (got {jobs!r}). A workflow "
        "with no jobs is the broader shape of the phantom-failure bug — valid "
        "YAML, but GitHub Actions still emits a completed/failure run with "
        "zero work. If this file is intentionally a re-usable workflow with "
        "only `on:` and a callable surface, exempt it explicitly in this test."
    )
