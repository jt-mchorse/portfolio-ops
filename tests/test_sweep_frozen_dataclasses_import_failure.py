"""One unsweepable name must not end the sweep (portfolio-ops#122).

`main` called `sweep()` straight inside its per-name loop. A package whose
`__init__` raised, a name that was not installed, or a plain module (no
`__path__` to walk) raised out of the loop with a traceback, so every name
after it went unswept. The traceback's exit code was 1, which says nothing
about whether the sweep was partial.

Each failure is now an `::error::` line on stderr, the loop moves on, and the
exit code is 2 when any name was not swept. Gaps still exit 0: the script is a
measurement, not a gate (`test_main_exits_zero_even_with_gaps`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sweep_frozen_dataclasses import main  # noqa: E402

GAPPY = (
    "from dataclasses import dataclass\n"
    "from typing import Any\n"
    "@dataclass(frozen=True)\n"
    "class Gappy:\n"
    "    value: Any = None\n"
)


def _package(name: str, init: str, modules: dict[str, str], tmp_path: Path) -> str:
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text(init, encoding="utf-8")
    for mod_name, src in modules.items():
        (root / f"{mod_name}.py").write_text(src, encoding="utf-8")
    if str(tmp_path) not in sys.path:
        sys.path.insert(0, str(tmp_path))
    return name


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    rc = main(["sweep_frozen_dataclasses.py", *argv])
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


@pytest.mark.parametrize(
    "init",
    [
        pytest.param('raise ImportError("boom")\n', id="ImportError"),
        pytest.param('raise RuntimeError("boom")\n', id="RuntimeError"),
        pytest.param("import a_module_that_does_not_exist_anywhere_122\n", id="missing-dep"),
    ],
)
def test_a_raising_package_does_not_stop_the_next_one(
    init: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The issue's own probe: the broken package sorts FIRST on the command
    line, so before the fix the gappy one after it was never reached."""
    tag = init.split("(")[0].split()[-1].lower()
    broken = _package(f"swept_122_broken_{tag}", init, {}, tmp_path)
    gappy = _package(f"swept_122_gappy_{tag}", "", {"mod": GAPPY}, tmp_path)
    rc, out, err = _run([broken, gappy], capsys)
    assert f"GAP  {gappy}.mod.Gappy.value" in out
    assert f"::error::{broken}: " in err
    assert "boom" in err or "a_module_that_does_not_exist_anywhere_122" in err
    assert rc == 2


def test_a_name_that_is_not_installed_is_reported_and_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gappy = _package("swept_122_gappy_missing", "", {"mod": GAPPY}, tmp_path)
    rc, out, err = _run(["swept_122_no_such_package_anywhere", gappy], capsys)
    assert f"GAP  {gappy}.mod.Gappy.value" in out
    assert "::error::swept_122_no_such_package_anywhere: ModuleNotFoundError" in err
    assert rc == 2


def test_every_failure_is_reported_not_only_the_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two broken names around a good one: both are named, the good one is
    swept, and the summary counts both."""
    first = _package("swept_122_broken_one", 'raise ImportError("one")\n', {}, tmp_path)
    gappy = _package("swept_122_gappy_middle", "", {"mod": GAPPY}, tmp_path)
    last = _package("swept_122_broken_two", 'raise ImportError("two")\n', {}, tmp_path)
    rc, out, err = _run([first, gappy, last], capsys)
    assert f"::error::{first}: ImportError: one" in err
    assert f"::error::{last}: ImportError: two" in err
    assert f"2 package(s) not swept: {first}, {last}" in err
    assert f"GAP  {gappy}.mod.Gappy.value" in out
    assert rc == 2


def test_a_plain_module_is_swept_not_a_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A module has no `__path__`. The walk used to read it unconditionally and
    raise `AttributeError`, which ended the sweep the same way an import error
    did. A module name is a reasonable thing to pass, so its own dataclasses
    are swept."""
    (tmp_path / "swept_122_plain_module.py").write_text(GAPPY, encoding="utf-8")
    gappy = _package("swept_122_gappy_after_module", "", {"mod": GAPPY}, tmp_path)
    rc, out, err = _run(["swept_122_plain_module", gappy], capsys)
    assert "GAP  swept_122_plain_module.Gappy.value" in out
    assert f"GAP  {gappy}.mod.Gappy.value" in out
    assert "::error::" not in err
    assert rc == 0


def test_a_complete_sweep_with_gaps_still_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Control: a gap is a candidate, not a finding, so the exit code for a
    complete sweep does not change. Only a partial sweep is 2."""
    gappy = _package("swept_122_gappy_clean", "", {"mod": GAPPY}, tmp_path)
    rc, out, err = _run([gappy], capsys)
    assert "1 gap(s)" in out
    assert err == ""
    assert rc == 0
