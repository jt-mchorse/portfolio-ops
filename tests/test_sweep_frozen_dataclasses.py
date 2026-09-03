"""The sweep's population rule, pinned (portfolio-ops#71).

The #71 sweep lived as a snippet in an issue body, and its `MUTABLE` list
omitted `Any`. Re-running it with `Any` included finds nine more fields across
five repos, and one of them — `async_pipelines.tool_dispatch.ToolResult.value`
— is the only member of this class confirmed as a live defect since
(`python-async-llm-pipelines#106`).

So the sweep run to generalize a lens missed a third instance *in the package
the lens came from*, for the same reason that package's own docstring missed
it. These tests exist so the annotation set cannot narrow again without a red
test, and so the rest of the rule (frozen-only, immutable-first, copy
detection) is stated rather than assumed.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sweep_frozen_dataclasses import (  # noqa: E402
    IMMUTABLE_HINTS,
    MUTABLE_HINTS,
    copies_field,
    discover_dataclasses,
    main,
    mutable_fields,
    sweep,
)


# --- the annotation set ------------------------------------------------------


def test_any_is_in_the_mutable_hints() -> None:
    """The entry #71's sweep omitted, and the one the confirmed defect needed.

    Stated as its own test rather than folded into a table so the failure
    message names the actual regression: a scan looking only for
    `dict`/`list` is technically correct and blind to `value: Any`, which is
    exactly where an unconstrained mutable hides.
    """
    assert "Any" in MUTABLE_HINTS


def test_the_original_hints_are_all_still_present() -> None:
    """Adding `Any` must not have replaced the set #71 already validated."""
    for hint in ("dict", "list", "set[", "Mapping", "MutableMapping", "bytearray"):
        assert hint in MUTABLE_HINTS, hint


def test_immutable_hints_win_over_mutable_ones() -> None:
    """`tuple[dict[str, int], ...]` is immutable at the field level; reporting it
    would put noise on a worklist whose value is its signal-to-noise."""

    @dataclasses.dataclass(frozen=True)
    class Sample:
        rows: tuple[dict[str, int], ...] = ()
        frozen_set: frozenset[str] = frozenset()

    assert mutable_fields(Sample) == []
    assert set(IMMUTABLE_HINTS) == {"tuple", "frozenset"}


# --- field detection ---------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _AnyField:
    value: Any = None


@dataclasses.dataclass(frozen=True)
class _DictField:
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        import copy

        object.__setattr__(self, "extra", copy.deepcopy(self.extra))


@dataclasses.dataclass(frozen=True)
class _UncopiedDict:
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass  # not frozen
class _MutableClass:
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)


def test_an_any_field_is_detected() -> None:
    assert mutable_fields(_AnyField) == [("value", "Any")]


def test_a_copied_field_reads_as_copied() -> None:
    assert copies_field(_DictField, "extra") is True


def test_an_uncopied_field_reads_as_a_gap() -> None:
    assert copies_field(_UncopiedDict, "extra") is False


def test_a_class_with_no_post_init_is_a_gap_not_a_crash() -> None:
    """`ToolResult` has no `__post_init__` at all — the sweep must survive that
    rather than raising on `inspect.getsource(None)`."""
    assert getattr(_AnyField, "__post_init__", None) is None
    assert copies_field(_AnyField, "value") is False


def test_copy_detection_is_per_field() -> None:
    """A `__post_init__` that copies one field must not vouch for another."""

    @dataclasses.dataclass(frozen=True)
    class TwoFields:
        a: dict[str, Any] = dataclasses.field(default_factory=dict)
        b: dict[str, Any] = dataclasses.field(default_factory=dict)

        def __post_init__(self) -> None:
            object.__setattr__(self, "a", dict(self.a))

    assert copies_field(TwoFields, "a") is True
    assert copies_field(TwoFields, "b") is False


# --- the walk ----------------------------------------------------------------


def _package(name: str, modules: dict[str, str], tmp_path: Path) -> str:
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    for mod_name, src in modules.items():
        (root / f"{mod_name}.py").write_text(src, encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    return name


def test_sweep_reports_frozen_gaps_and_skips_mutable_classes(tmp_path: Path) -> None:
    src = (
        "from dataclasses import dataclass, field\n"
        "from typing import Any\n"
        "@dataclass(frozen=True)\n"
        "class Frozen:\n"
        "    value: Any = None\n"
        "@dataclass\n"
        "class NotFrozen:\n"
        "    extra: dict = field(default_factory=dict)\n"
    )
    name = _package("swept_pkg_a", {"mod": src}, tmp_path)
    rows = sweep(name)
    names = {f"{n}.{f}" for n, f, _, _ in rows}
    assert "swept_pkg_a.mod.Frozen.value" in names
    # A non-frozen dataclass is out of scope: its field can be rebound anyway,
    # so "the copy is missing" says nothing about it.
    assert not any("NotFrozen" in n for n in names)


def test_the_walk_does_not_double_count_a_reexported_class(tmp_path: Path) -> None:
    """`obj.__module__ == module.__name__` is load-bearing: without it a class
    re-exported from a package `__init__` appears once per importing module and
    the worklist's count inflates."""
    defining = (
        "from dataclasses import dataclass\n"
        "from typing import Any\n"
        "@dataclass(frozen=True)\n"
        "class Shared:\n"
        "    value: Any = None\n"
    )
    reexport = "from .defining import Shared\n"
    name = _package(
        "swept_pkg_b", {"defining": defining, "reexport": reexport}, tmp_path
    )
    rows = sweep(name)
    shared = [r for r in rows if r[0].endswith(".Shared")]
    assert len(shared) == 1, shared


def test_an_unimportable_module_is_skipped_not_fatal(tmp_path: Path) -> None:
    """A module behind an optional extra must not stop the sweep — the whole
    point is that it runs on a base install of every repo."""
    good = (
        "from dataclasses import dataclass\n"
        "from typing import Any\n"
        "@dataclass(frozen=True)\n"
        "class Good:\n"
        "    value: Any = None\n"
    )
    bad = "import a_module_that_does_not_exist_anywhere\n"
    name = _package("swept_pkg_c", {"good": good, "bad": bad}, tmp_path)
    rows = sweep(name)
    assert any(r[0].endswith(".Good") for r in rows)


def test_discover_finds_nothing_in_an_empty_package(tmp_path: Path) -> None:
    name = _package("swept_pkg_d", {}, tmp_path)
    import importlib

    assert discover_dataclasses(importlib.import_module(name)) == {}


# --- the entry point ---------------------------------------------------------


def test_main_requires_an_argument(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["sweep_frozen_dataclasses.py"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_exits_zero_even_with_gaps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A measurement, not a gate. Making it a gate would fail every repo on a
    worklist whose real-hit rate is about a third — #71's own triage found one
    of its two spot-checks not reachable."""
    src = (
        "from dataclasses import dataclass\n"
        "from typing import Any\n"
        "@dataclass(frozen=True)\n"
        "class Frozen:\n"
        "    value: Any = None\n"
    )
    name = _package("swept_pkg_e", {"mod": src}, tmp_path)
    assert main(["sweep_frozen_dataclasses.py", name]) == 0
    out = capsys.readouterr().out
    assert "GAP" in out
    assert "candidate, not a bug" in out


def test_dropping_any_would_hide_the_confirmed_defect_shape(tmp_path: Path) -> None:
    """The regression this file exists for, stated end to end.

    `ToolResult.value: Any` with no `__post_init__` is the shape #71's sweep
    could not see and #106 confirmed as a live defect. Rebuild it and assert the
    sweep reports it — so narrowing `MUTABLE_HINTS` fails here rather than
    silently shrinking a portfolio-wide worklist.
    """
    src = (
        "from dataclasses import dataclass\n"
        "from typing import Any\n"
        "@dataclass(frozen=True)\n"
        "class ToolResult:\n"
        "    tool_call_id: str = ''\n"
        "    ok: bool = True\n"
        "    value: Any = None\n"
    )
    name = _package("swept_pkg_f", {"tool_dispatch": src}, tmp_path)
    rows = sweep(name)
    hits = [r for r in rows if r[1] == "value" and not r[3]]
    assert hits, rows
    assert any("Any" in annotation for _, _, annotation, _ in hits)


def test_the_module_docstring_names_the_confirmed_case() -> None:
    """Cheap guard against the reasoning being edited out of the script while
    the code stays — the *why* is the durable part of a worklist tool."""
    import scripts.sweep_frozen_dataclasses as module

    doc = module.__doc__ or ""
    assert "ToolResult.value" in doc
    assert "Any" in doc
