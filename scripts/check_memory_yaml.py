#!/usr/bin/env python3
"""Ratchet on unparseable ``MEMORY/full_history_ai.md`` session blocks (#66).

``#`` begins a comment in YAML, so ``followups: [#107]`` is ``followups: [``
followed by a comment -- an unterminated flow sequence, and the *whole* session
block fails to load::

    >>> yaml.safe_load("followups: [#107]")
    yaml.parser.ParserError: while parsing a flow node
    expected the node content, but found '<stream end>'

Measured across all thirteen repos (2026-08-26): **74 of 953 blocks** fail
``yaml.safe_load``, and **71 of the 74 are this one spelling**, present in every
repo across the whole history. ``COWORK_HANDOFF.md`` §3 calls this file "Same
content, AI-optimized ... for fast machine parsing", so 8% of the corpus being
unloadable defeats the field's reason for existing -- the first time anything
actually parses it.

**A ratchet, not a gate.** This does not demand zero. It compares each repo's
count against a committed baseline and fails only when the count *grows*. That
shape is deliberate, and it is the lesson ``#65``'s follow-up recorded: a guard
that refuses to operate on files that already carry the damage is useless on
exactly the files that need it. It also keeps the retro-fix decision open --
``MEMORY/`` is append-only by rule (§10), and whether a mechanical
quote-insertion counts as rewriting history is JT's call, not a session's
(#66). Freezing the count is how that call stays unforced.

The convention for *new* blocks is D-010: quote every item,
``followups: ["#107"]``.

The precise rule is narrower than "``#`` breaks YAML": a comment starts at ``#``
only when it follows whitespace or begins the token, so ``[leh#212]`` and
``[csl#165, aiapp#102]`` **parse fine today** -- the cross-repo spelling was
never at risk, and ``#66``'s option analysis was wrong about that (corrected on
the issue). Only a bare ``[#107]``, or a mixed ``[leh#212, #66]``, breaks.

D-010 still quotes *everything* rather than only the bare-``#`` items, because
the alternative rule -- "quote a followup only when it starts with ``#``" -- is
correct and unmemorable. One rule with no exceptions is a superset of the
narrow one, so a session applying it cannot be wrong whichever spelling it
reaches for.

Exit codes match the portfolio convention `audit_phase_a.py` uses:
``0`` within baseline, ``1`` a repo regressed, ``2`` a usage or I/O error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BASELINE_PATH = Path(__file__).resolve().parent / "memory_yaml_baseline.json"

# A session block is delimited by a `---` fence line and identified by its
# `session:` key. Splitting on the fence rather than parsing the whole file is
# what the file's own format implies -- it is a sequence of frontmatter blocks,
# not one document.
_FENCE = re.compile(r"^---\s*$", re.M)


def count_unparseable(text: str) -> tuple[int, int, list[str]]:
    """Return ``(unparseable, total, reasons)`` for one full_history_ai.md."""
    try:
        import yaml
    except ImportError:  # pragma: no cover - exercised by the operator path
        raise SystemExit(
            "check_memory_yaml requires pyyaml: pip install -r scripts/requirements.txt"
        ) from None

    unparseable = 0
    total = 0
    reasons: list[str] = []
    for block in _FENCE.split(text):
        if "session:" not in block:
            continue
        total += 1
        try:
            yaml.safe_load(block)
        except Exception as e:  # noqa: BLE001 - any loader failure counts
            unparseable += 1
            reasons.append(str(e).splitlines()[0].strip())
    return unparseable, total, reasons


def load_baseline() -> dict[str, int]:
    if not BASELINE_PATH.exists():
        return {}
    data: Any = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in data.get("unparseable_by_repo", {}).items()}


def memory_file(root: Path, repo: str) -> Path:
    """Resolve a repo's history file under a checkout root.

    `portfolio-ops` is cloned beside `repos/` rather than inside it, which is
    the layout the session prompt's Phase A assumes.
    """
    if repo == "portfolio-ops":
        return root / "portfolio-ops" / "MEMORY" / "full_history_ai.md"
    return root / "repos" / repo / "MEMORY" / "full_history_ai.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_memory_yaml",
        description=(
            "Fail if any repo's count of unparseable MEMORY/full_history_ai.md "
            "session blocks exceeds its committed baseline (#66)."
        ),
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Checkout root containing portfolio-ops/ and repos/ (default: cwd).",
    )
    parser.add_argument(
        "--repo",
        action="append",
        help="Limit to one repo (repeatable). Default: every repo in the baseline.",
    )
    parser.add_argument(
        "--file",
        help="Check a single full_history_ai.md directly; implies --repo of its repo name.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Rewrite the baseline from the current counts. For a deliberate retro-fix only.",
    )
    args = parser.parse_args(argv)

    baseline = load_baseline()
    root = Path(args.root)

    if args.file:
        path = Path(args.file)
        repos = [args.repo[0] if args.repo else path.resolve().parents[1].name]
        paths = {repos[0]: path}
    else:
        repos = args.repo or sorted(baseline)
        if not repos:
            print("::error::no baseline and no --repo given; nothing to check", file=sys.stderr)
            return 2
        paths = {r: memory_file(root, r) for r in repos}

    counts: dict[str, int] = {}
    regressions: list[str] = []
    for repo in repos:
        path = paths[repo]
        if not path.exists():
            print(f"::error::{path} not found", file=sys.stderr)
            return 2
        bad, total, reasons = count_unparseable(path.read_text(encoding="utf-8"))
        counts[repo] = bad
        allowed = baseline.get(repo)
        if allowed is None:
            # An unknown repo has no allowance; anything but zero is a regression.
            allowed = 0
        status = "ok" if bad <= allowed else "REGRESSED"
        print(f"{repo:<32} {bad:>3} / {total:<4} (baseline {allowed}) {status}")
        if bad > allowed:
            regressions.append(repo)
            for reason in reasons[-(bad - allowed) :]:
                print(f"    {reason}", file=sys.stderr)

    if args.write_baseline:
        BASELINE_PATH.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Unparseable session blocks per repo, frozen by #66. This is a "
                        "RATCHET: check_memory_yaml.py fails when a count grows, never "
                        "demanding zero, so the retro-fix decision (#66) stays JT's. "
                        "Regenerate with --write-baseline only as part of a deliberate "
                        "retro-fix."
                    ),
                    "unparseable_by_repo": dict(sorted(counts.items())),
                },
                indent=2,
                sort_keys=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {BASELINE_PATH}")
        return 0

    if regressions:
        print(
            f"::error::unparseable MEMORY blocks increased in: {', '.join(regressions)}. "
            'Per D-010, write followups as quoted strings: followups: ["#107"].',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
