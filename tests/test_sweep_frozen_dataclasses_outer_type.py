"""The sweep classifies a field by its OUTERMOST type (portfolio-ops#113).

Until #113 `mutable_fields()` tested substrings of the whole annotation, and it
tested the "immutable" substrings first. `dict[str, tuple[float, str]]`
mentions `tuple`, so it was skipped. That is how
`eval_harness.runs.StoredRun.rows` never appeared in the sweep and had to be
found by hand. The mutable list was also case-sensitive and had only `"set["`,
so `List[str]`, `Set[str]` and a bare `set` were never reported. On origin/main
91a7f76 the issue's probe class, with five mutable fields, reported one of them.

The tuple rule was written "so `tuple[dict, ...]` is not reported for its
element type", which is a statement about the outer type. These arms pin that
reading both ways, for string annotations (`from __future__ import
annotations`) and for runtime type objects, because the two arrive as
different text.
"""

from __future__ import annotations

import dataclasses
import sys
import typing
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sweep_frozen_dataclasses import (  # noqa: E402
    IMMUTABLE_HINTS,
    MUTABLE_HINTS,
    mutable_fields,
    sweep,
)


def _reported(annotation: Any) -> bool:
    cls = dataclasses.make_dataclass("Probe", [("f", annotation)], frozen=True)
    return [name for name, _ in mutable_fields(cls)] == ["f"]


# The issue's five rows first, then the shapes the outer-type rule has to see
# through, then names the old substring rule could not tell apart.
MUTABLE_TEXT = [
    "dict[str, tuple[int, int]]",
    "list[tuple[str, str]]",
    "List[str]",
    "set",
    "dict[str, int]",
    "typing.List[str]",
    "Set[int]",
    "Dict[str, Tuple[int, int]]",
    "dict[str, tuple[float, str]]",  # leh StoredRun.rows
    "Optional[dict[str, tuple[int, int]]]",
    "typing.Optional[List[str]]",
    "dict[str, int] | None",
    "None | list[tuple[int, int]]",
    "Union[int, set]",
    "Annotated[dict[str, tuple[int, int]], 'meta']",
    "Final[list[tuple[int, int]]]",
    "'dict[str, tuple[int, int]]'",
    "Any",
    "typing.Any",
    "Mapping[str, tuple[int, ...]]",
    "MutableSequence[int]",
    "MutableSet[str]",
    "bytearray",
    "defaultdict[str, list[int]]",
    "collections.OrderedDict[str, int]",
    "Counter[str]",
    "Deque[int]",
]

IMMUTABLE_TEXT = [
    "tuple[dict, ...]",
    "tuple[dict[str, list[int]], ...]",
    "Tuple[List[int], ...]",
    "frozenset[str]",
    "FrozenSet[str]",
    "Optional[tuple[dict, ...]]",
    "tuple[list[int], ...] | None",
    "int",
    "str | None",
    "Literal['dict', 'list']",
    "Callable[[dict], list]",
    "type[dict]",
]


@pytest.mark.parametrize("annotation", MUTABLE_TEXT)
def test_a_mutable_outer_type_is_reported(annotation: str) -> None:
    assert _reported(annotation), annotation


@pytest.mark.parametrize("annotation", IMMUTABLE_TEXT)
def test_an_immutable_or_scalar_outer_type_is_not(annotation: str) -> None:
    assert not _reported(annotation), annotation


# Runtime type objects: a module without `from __future__ import annotations`
# hands the sweep `<class 'set'>`, `typing.List[str]`, `dict[str, int] | None`.
MUTABLE_RUNTIME = [
    dict[str, tuple[int, int]],
    list[tuple[str, str]],
    typing.List[str],
    set,
    dict,
    bytearray,
    dict[str, int],
    typing.Optional[dict[str, tuple[int, int]]],
    dict[str, int] | None,
    typing.Any,
    OrderedDict[str, int],
]

IMMUTABLE_RUNTIME = [
    tuple[dict, ...],
    typing.Tuple[typing.List[int], ...],
    frozenset[str],
    typing.Optional[tuple[dict, ...]],
    int,
    str,
]


@pytest.mark.parametrize("annotation", MUTABLE_RUNTIME, ids=str)
def test_a_mutable_runtime_type_is_reported(annotation: Any) -> None:
    assert _reported(annotation), annotation


@pytest.mark.parametrize("annotation", IMMUTABLE_RUNTIME, ids=str)
def test_an_immutable_runtime_type_is_not(annotation: Any) -> None:
    assert not _reported(annotation), annotation


def test_an_unparseable_annotation_falls_back_to_the_substring_rule() -> None:
    """A class defined inside a function stringifies as
    `list[test.<locals>.Row]`, which `ast` cannot parse. That must not drop a
    field the old rule reported."""
    assert _reported("list[test.<locals>.Row]")
    assert not _reported("weird.<locals>.Row")


def _package(name: str, src: str, tmp_path: Path) -> str:
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "m.py").write_text(src, encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    return name


@pytest.mark.parametrize("future", [True, False], ids=["string", "runtime"])
def test_the_issue_probe_end_to_end(tmp_path: Path, future: bool) -> None:
    """The probe from #113: five mutable fields, one tuple-of-dict control.
    origin/main reported `e` alone."""
    src = (
        ("from __future__ import annotations\n" if future else "")
        + "from dataclasses import dataclass\n"
        "from typing import List\n"
        "@dataclass(frozen=True)\n"
        "class R:\n"
        "    a: dict[str, tuple[int, int]]\n"
        "    b: list[tuple[str, str]]\n"
        "    c: List[str]\n"
        "    d: set\n"
        "    e: dict[str, int]\n"
        "    f: tuple[dict, ...]\n"
    )
    name = _package(f"swept_outer_{'s' if future else 'r'}", src, tmp_path)
    gaps = sorted(field for _, field, _, copied in sweep(name) if not copied)
    assert gaps == ["a", "b", "c", "d", "e"]


def test_the_two_hint_sets_are_disjoint() -> None:
    """An outer type cannot be both; an overlap would make the answer depend
    on which set the classifier happens to consult first."""
    assert not IMMUTABLE_HINTS & MUTABLE_HINTS
