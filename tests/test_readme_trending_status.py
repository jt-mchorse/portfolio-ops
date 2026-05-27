"""Lock the README's Trending workflow section against pessimistic-fabrication drift.

The section must:

- still document the trending workflow (header present),
- name both shipped scripts by filename,
- never contain the literal "not yet implemented" claim again — D-003
  superseded D-002 on 2026-05-11; that line is what this test exists to
  catch the moment it tries to come back.

Related: portfolio-ops#1, MEMORY/core_decisions_ai.md (D-002 superseded by D-003).
"""
from __future__ import annotations

from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"


@pytest.fixture(scope="module")
def readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_exists() -> None:
    assert README.is_file(), f"README.md missing at {README}"


def test_trending_section_header_present(readme_text: str) -> None:
    # Either heading shape is fine — we only fail loudly if the section
    # disappears entirely.
    assert (
        "## Trending workflow" in readme_text
        or "## Trending workflow status" in readme_text
    ), "Trending workflow section header missing from README"


@pytest.mark.parametrize(
    "filename",
    ["scripts/trending_scan.py", "scripts/prune_stale_trending.py"],
)
def test_both_scripts_named(readme_text: str, filename: str) -> None:
    assert filename in readme_text, (
        f"README must name {filename}; without it, readers can't find the "
        f"implementation backing D-003."
    )


def test_not_yet_implemented_claim_absent(readme_text: str) -> None:
    forbidden = "not yet implemented"
    assert forbidden not in readme_text.lower(), (
        "README still says trending scripts are 'not yet implemented'. "
        "D-003 ships them; remove the stale line."
    )


def test_d003_referenced_somewhere(readme_text: str) -> None:
    assert "D-003" in readme_text, (
        "README's trending section should cite D-003 so readers can trace "
        "the stdlib-only decision back to MEMORY/core_decisions_*.md."
    )
