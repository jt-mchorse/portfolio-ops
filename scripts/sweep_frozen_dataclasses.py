#!/usr/bin/env python3
"""Find frozen dataclasses whose mutable field is not copied in (portfolio-ops#71).

`frozen=True` stops attribute rebinding. It does nothing about a `dict` or a
`list` the caller still holds a reference to, so a "frozen" record can gain a
new top-level key after construction. `python-async-llm-pipelines` hit that
twice (`RunResult.extra` #100, `ToolCall.arguments` #102) and
`vector-search-at-scale#135` hit it again, which is what prompted the
portfolio-wide sweep in #71.

**Why this is a committed, tested script and not a snippet in an issue.**
The #71 sweep lived as ~40 lines pasted into an issue body, and its population
rule was wrong: `MUTABLE` listed `dict`, `list`, `set[`, `Mapping`,
`MutableMapping`, `bytearray` and **not `Any`**. Re-running it with `Any`
included finds nine more fields across five repos — and one of them,
`async_pipelines.tool_dispatch.ToolResult.value`, is the only member of this
class confirmed as a live defect since (`python-async-llm-pipelines#106`:
a frozen `ToolResult` gains a new top-level key after construction, and three
results from one tool share one object).

So the sweep that was run to generalize the lens missed a third instance *in
the very package the lens came from*, for the same reason that package's own
docstring missed it — `Any` is where an unconstrained mutable value hides, and
a scan that looks for `dict`/`list` is technically correct and blind to exactly
the case it exists for. `tests/test_sweep_frozen_dataclasses.py` pins `Any` in
the annotation set with an arm that fails if it is dropped.

**A `GAP` is a candidate, not a bug.** It means only "frozen dataclass, mutable
field, no `object.__setattr__` copy in `__post_init__`". Whether it is a defect
depends on reachability — is the field ever constructed from data a caller
retains, and does anything downstream read it later? #71's own triage found
`rag_kit.streaming.StreamEvent.payload` reachable and
`prompt_regression.diff.DiffResult.*` not. This script measures; a human
triages.

Usage::

    python3 scripts/sweep_frozen_dataclasses.py <import-name> [<import-name> ...]

Run from inside the target repo (its package must be importable). Exits 0
always: this is a measurement, not a gate. Making it a gate would file 21 bug
reports for a list whose real-hit rate is about a third.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
import sys
from typing import Any

#: Annotations that cannot hold a mutable object, checked first so
#: `tuple[dict, ...]` is not reported for its element type.
IMMUTABLE_HINTS: tuple[str, ...] = ("tuple", "frozenset")

#: Annotations that can. `Any` is the load-bearing entry (#71's sweep omitted
#: it): an unconstrained field is precisely where a mutable value hides, and it
#: is where the one confirmed defect in this class was found. Removing it makes
#: the whole sweep under-count, silently and portfolio-wide.
MUTABLE_HINTS: tuple[str, ...] = (
    "dict",
    "list",
    "set[",
    "Mapping",
    "MutableMapping",
    "bytearray",
    "Any",
)


def mutable_fields(cls: type) -> list[tuple[str, str]]:
    """`(field_name, annotation)` for each field that could hold a mutable."""
    out: list[tuple[str, str]] = []
    for field in dataclasses.fields(cls):
        annotation = str(field.type)
        if any(hint in annotation for hint in IMMUTABLE_HINTS):
            continue
        if any(hint in annotation for hint in MUTABLE_HINTS):
            out.append((field.name, annotation))
    return out


def copies_field(cls: type, field_name: str) -> bool:
    """True when `__post_init__` rebinds *field_name* via `object.__setattr__`.

    Source inspection rather than behaviour, deliberately: constructing an
    arbitrary dataclass to observe a copy needs valid values for every other
    field, which the sweep cannot invent. The cost is that a copy performed some
    other way reads as a `GAP` — a false positive a human triages, which is the
    safe direction for a worklist.
    """
    post_init = getattr(cls, "__post_init__", None)
    if post_init is None:
        return False
    try:
        source = inspect.getsource(post_init)
    except (OSError, TypeError):  # C-defined or source unavailable
        return False
    return f'object.__setattr__(self, "{field_name}"' in source


def discover_dataclasses(package: Any) -> dict[str, type]:
    """Every dataclass declared in *package* or a subpackage, keyed by path."""
    found: dict[str, type] = {}

    def walk(pkg: Any) -> None:
        for mod in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
            try:
                module = importlib.import_module(mod.name)
            except Exception:
                # An optional-extra module that cannot import is not a finding;
                # skipping it keeps the sweep runnable on a base install.
                continue
            if mod.ispkg:
                walk(module)
            for name, obj in vars(module).items():
                # `obj.__module__ == module.__name__` keeps a re-exported class
                # from being counted once per module that imports it.
                if (
                    inspect.isclass(obj)
                    and dataclasses.is_dataclass(obj)
                    and obj.__module__ == module.__name__
                ):
                    found[f"{module.__name__}.{name}"] = obj

    walk(package)
    return found


def sweep(import_name: str) -> list[tuple[str, str, str, bool]]:
    """`(qualified_name, field, annotation, is_copied)` for every candidate."""
    package = importlib.import_module(import_name)
    rows: list[tuple[str, str, str, bool]] = []
    for name, cls in sorted(discover_dataclasses(package).items()):
        params = getattr(cls, "__dataclass_params__", None)
        if params is None or not params.frozen:
            continue
        for field_name, annotation in mutable_fields(cls):
            rows.append((name, field_name, annotation, copies_field(cls, field_name)))
    return rows


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print(f"usage: {argv[0]} <import-name> [<import-name> ...]", file=sys.stderr)
        return 2
    gaps = 0
    for import_name in argv[1:]:
        print(f"=== {import_name}")
        for name, field_name, annotation, is_copied in sweep(import_name):
            if not is_copied:
                gaps += 1
            print(
                f"  {'OK  ' if is_copied else 'GAP '} {name}.{field_name}: {annotation}"
            )
    print(f"\n{gaps} gap(s). A GAP is a candidate, not a bug — triage reachability.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
