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

import ast
import dataclasses
import importlib
import inspect
import pkgutil
import sys
from typing import Any

#: Outer types that cannot hold a mutable object at the field level, whatever
#: their element types, so `tuple[dict, ...]` is not reported (#113: matched on
#: the OUTERMOST type, not anywhere in the annotation text).
IMMUTABLE_HINTS: frozenset[str] = frozenset({"tuple", "Tuple", "frozenset", "FrozenSet"})

#: Outer types that can. `Any` is the load-bearing entry (#71's sweep omitted
#: it): an unconstrained field is precisely where a mutable value hides, and it
#: is where the one confirmed defect in this class was found. Removing it makes
#: the whole sweep under-count, silently and portfolio-wide.
#:
#: Until #113 this was a tuple of substrings tested against the whole
#: annotation, after an "immutable" substring test. `dict[str, tuple[...]]`
#: mentions `tuple`, so it was skipped, and that is how
#: `eval_harness.runs.StoredRun.rows` never appeared. The match was also
#: case-sensitive with only `"set["`, so `List[str]`, `Set[str]` and a bare
#: `set` were never reported.
MUTABLE_HINTS: frozenset[str] = frozenset(
    {
        "dict",
        "list",
        "set",
        "bytearray",
        "defaultdict",
        "deque",
        "Dict",
        "List",
        "Set",
        "DefaultDict",
        "OrderedDict",
        "Counter",
        "Deque",
        "Mapping",
        "MutableMapping",
        "MutableSequence",
        "MutableSet",
        "Any",
    }
)

#: Wrappers whose arguments ARE the field's type: a union is mutable when any
#: arm is, and `Annotated[X, meta]` / `Final[X]` are `X`.
_UNION_HEADS = frozenset({"Optional", "Union"})
_TRANSPARENT_HEADS = frozenset({"Annotated", "Final", "InitVar"})

#: Substrings for an annotation `ast` cannot parse. This is the pre-#113 rule,
#: kept only as the fallback, so that an odd annotation never drops out of the
#: worklist.
_FALLBACK_SUBSTRINGS: tuple[str, ...] = (
    "dict",
    "list",
    "set[",
    "Mapping",
    "MutableMapping",
    "bytearray",
    "Any",
)


def _annotation_text(tp: Any) -> str:
    """The annotation as source text. A class annotation such as bare `set`
    stringifies as `<class 'set'>`, so its name is used instead."""
    if isinstance(tp, str):
        return tp
    if inspect.isclass(tp) and not getattr(tp, "__args__", None):
        return tp.__name__
    return str(tp)


def _head(node: ast.expr) -> str | None:
    """`typing.List` -> `List`, `dict` -> `dict`; anything else -> None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_mutable(node: ast.expr) -> bool:
    """Classify one annotation node by its outermost type (#113)."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):  # a quoted forward reference
            return _text_is_mutable(node.value)
        return False  # `None`
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):  # X | Y
        return _is_mutable(node.left) or _is_mutable(node.right)
    if isinstance(node, ast.Subscript):
        head = _head(node.value)
        args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        if head in _UNION_HEADS:
            return any(_is_mutable(arg) for arg in args)
        if head in _TRANSPARENT_HEADS:
            return _is_mutable(args[0])
        if head in IMMUTABLE_HINTS:
            return False  # `tuple[dict, ...]`: the element type is not the field's
        return head in MUTABLE_HINTS
    head = _head(node)
    return head is not None and head in MUTABLE_HINTS


def _text_is_mutable(text: str) -> bool:
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except SyntaxError:
        return any(hint in text for hint in _FALLBACK_SUBSTRINGS)
    return _is_mutable(node)


def mutable_fields(cls: type) -> list[tuple[str, str]]:
    """`(field_name, annotation)` for each field that could hold a mutable."""
    out: list[tuple[str, str]] = []
    for field in dataclasses.fields(cls):
        annotation = _annotation_text(field.type)
        if _text_is_mutable(annotation):
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
