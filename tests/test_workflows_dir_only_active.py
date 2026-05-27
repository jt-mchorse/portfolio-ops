"""Lock that `.github/workflows/` only contains active portfolio-ops workflows.

The repo also has a `workflows/` directory at the root — that's the *template*
directory consumed by `templates/init-portfolio-repo.sh` (line 44 copies
`workflows/ci-template.yml` into each new repo's `.github/workflows/ci.yml`).
Template files (anything matching `*-template.yml`) belong only in `workflows/`,
never in `.github/workflows/`.

The bootstrap commit (2026-05-10) accidentally placed `ci-template.yml` in
`.github/workflows/` as well. GitHub Actions then dutifully tried to execute
it on every push, and every run failed because two workflows shared `name: ci`
(real `ci.yml` plus the template). 17 days of silent paired-failure runs
followed before a session noticed.

This file is the inverse-safety-net: enumerate exactly the active workflows
expected to live in `.github/workflows/`, reject any template-shaped file there,
and fail loudly if either invariant breaks.

Related: portfolio-ops#13.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
TEMPLATES_DIR = REPO_ROOT / "workflows"

# The exact set of workflow files that should live in .github/workflows/.
# verify.yml = portfolio-ops's own test/memory-check CI (added in #2 as ci.yml,
# renamed in #18 to force a fresh workflow registration after GitHub Actions
# kept stale state from the 17-day name-collision with the deleted template).
# trending-daily.yml / trending-weekly.yml = scheduled scanners that file
# issues across the 12 portfolio repos (in repo since bootstrap).
EXPECTED_ACTIVE_WORKFLOWS = (
    "verify.yml",
    "trending-daily.yml",
    "trending-weekly.yml",
)


def _active_workflow_filenames() -> list[str]:
    return sorted(p.name for p in ACTIVE_WORKFLOWS_DIR.glob("*.yml"))


def test_active_workflows_dir_exists() -> None:
    assert ACTIVE_WORKFLOWS_DIR.is_dir(), (
        f".github/workflows/ missing at {ACTIVE_WORKFLOWS_DIR}"
    )


def test_templates_dir_exists() -> None:
    # Sanity-check the *other* directory; if this assertion ever fails,
    # `init-portfolio-repo.sh` is broken too.
    assert TEMPLATES_DIR.is_dir(), (
        f"workflows/ template directory missing at {TEMPLATES_DIR}. "
        "init-portfolio-repo.sh depends on it."
    )


@pytest.mark.parametrize("filename", EXPECTED_ACTIVE_WORKFLOWS)
def test_expected_active_workflow_present(filename: str) -> None:
    path = ACTIVE_WORKFLOWS_DIR / filename
    assert path.is_file(), (
        f"Expected active workflow {filename!r} missing from .github/workflows/. "
        "If this workflow was renamed or removed deliberately, update "
        "EXPECTED_ACTIVE_WORKFLOWS in this test."
    )


def test_no_unexpected_files_in_active_workflows_dir() -> None:
    actual = set(_active_workflow_filenames())
    expected = set(EXPECTED_ACTIVE_WORKFLOWS)
    extras = actual - expected
    assert not extras, (
        f".github/workflows/ contains unexpected file(s) {sorted(extras)!r}. "
        "If you added a new active workflow, also add it to "
        "EXPECTED_ACTIVE_WORKFLOWS in this test. Template files belong in "
        "the repo-root `workflows/` directory, not here."
    )


def test_no_template_files_in_active_workflows_dir() -> None:
    template_shaped = [
        name for name in _active_workflow_filenames() if "-template" in name
    ]
    assert not template_shaped, (
        f".github/workflows/ contains template file(s) {template_shaped!r}. "
        "Template files (anything matching `*-template.yml`) belong in the "
        "repo-root `workflows/` directory only. GitHub Actions executes "
        "*everything* under .github/workflows/, so a misplaced template "
        "causes silent paired-failure runs on every push (see issue #13)."
    )
