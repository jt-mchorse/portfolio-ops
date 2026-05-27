"""Lock the bootstrap template against re-shipping pre-D-008 session cadence.

`templates/init-portfolio-repo.sh` is the script every new portfolio
repo's `CONTRIBUTING.md` is seeded from. The pre-D-008 version of that
template carried "~60-minute session cap" — a contract that
**D-008 (2026-05-14)** superseded with 180 min DAY / 360 min NIGHT and
a multi-issue loop. All twelve existing portfolio repos inherited the
stale claim because the template was the source.

This file is the inverse-safety-net: assert the template now reflects
D-008 cadence, and never accidentally re-ships the legacy 60-minute
wording.

Issue #3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INIT_SCRIPT = REPO_ROOT / "templates" / "init-portfolio-repo.sh"


@pytest.fixture(scope="module")
def init_script_text() -> str:
    return INIT_SCRIPT.read_text(encoding="utf-8")


def test_init_script_exists() -> None:
    assert INIT_SCRIPT.is_file(), f"init-portfolio-repo.sh missing at {INIT_SCRIPT}"


def test_pre_d008_60_minute_cap_phrase_absent(init_script_text: str) -> None:
    forbidden = "60-minute session cap"
    assert forbidden not in init_script_text, (
        "Bootstrap template still seeds the pre-D-008 cadence "
        f"({forbidden!r}). D-008 (2026-05-14) updated caps to 180/360 "
        "min with a multi-issue loop; the template must reflect that."
    )


def test_d008_referenced(init_script_text: str) -> None:
    assert "D-008" in init_script_text, (
        "Bootstrap template should cite D-008 explicitly so a future "
        "contributor reading a seeded CONTRIBUTING.md can trace the cap "
        "numbers back to MEMORY/core_decisions_*.md."
    )


@pytest.mark.parametrize("minutes", ["180", "360"])
def test_both_cap_numbers_present(init_script_text: str, minutes: str) -> None:
    assert minutes in init_script_text, (
        f"Bootstrap template missing the {minutes}-min cap number. "
        "Per D-008 both DAY (180) and NIGHT (360) caps must be cited."
    )
