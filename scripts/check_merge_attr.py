#!/usr/bin/env python3
"""Report local clones whose MEMORY files carry a ``merge`` attribute (#107, #117).

On 2026-10-21 three branches whose MEMORY entry was appended beside a sibling
entry on main rebased with **no conflict** and came out interleaved: two
entries glued into one block, the ``followups: [] / ---`` tail between them
gone. Git's default merge does not do that. It conflicts on two appends at
EOF, and ``resolve_memory_conflict.py`` resolves the conflict. The cause was
one line in every code-repo clone's ``.git/info/attributes``::

    MEMORY/*.md merge=union

An Oct 8 orchestrator script appended it and never removed it. ``union``
keeps both sides of every conflict hunk and hoists the shared trailer out
once, so a conflict that the resolver would have handled became a clean,
glued merge. Every ``git worktree`` made from those clones shares their
``info/`` dir, so every fix agent inherited it.

The line is local machine state: nothing committed shows it, and
``.git/info/attributes`` overrides a committed ``.gitattributes``, so no
in-repo fix can cancel it. This script is the check that would have shown it.
It asks git rather than reading files, because ``git check-attr`` is the
answer after every attributes source (``info/attributes``, ``.gitattributes``
at any depth, ``core.attributesFile``) has been applied.

It is not an ``audit_phase_a.py`` fingerprint because that script reads the
GitHub API and also runs as ``audit-cron`` on a runner that has no local
clones, where this check could only ever report clean.

Exit codes follow ``audit_phase_a.py``: ``0`` every checkout reports
``unspecified``, ``1`` at least one does not, ``2`` a usage error (no
checkouts under ``--root``, or git could not answer). A checkout git cannot
answer for is reported and skipped, and every other one is still asked
(#118). Exit ``1`` outranks ``2``, so a git error never hides a finding.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# The two files resolve_memory_conflict.py merges. A union or other driver on
# either one replaces the conflict it expects with a clean merge it never sees.
# The decisions files are appended the same way (#117): a union merge of two
# `- id: D-002` appends glues them into one entry that loads as the later
# decision alone, where git's default merge would have stopped on a conflict.
MEMORY_FILES = (
    "MEMORY/full_history_ai.md",
    "MEMORY/full_history_human.md",
    "MEMORY/core_decisions_ai.md",
    "MEMORY/core_decisions_human.md",
)


def checkouts(root: Path) -> list[Path]:
    """Every git checkout in the Phase A layout: ``portfolio-ops/`` and ``repos/*``.

    All of ``repos/*`` is walked, not only the 12 canonical names, because a
    worktree beside them (``repos/leh-266``) is a checkout an agent rebases in.
    """
    found = (
        [root / "portfolio-ops"] if (root / "portfolio-ops" / ".git").exists() else []
    )
    repos = root / "repos"
    if repos.is_dir():
        found += sorted(p for p in repos.iterdir() if (p / ".git").exists())
    return found


def merge_attrs(checkout: Path) -> dict[str, str]:
    """``{path: value}`` of the ``merge`` attribute git applies in ``checkout``."""
    proc = subprocess.run(
        ["git", "-C", str(checkout), "check-attr", "merge", "--", *MEMORY_FILES],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.strip() or f"git check-attr exited {proc.returncode}"
        )
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        # `<path>: merge: <value>`; the path cannot contain ": merge: ".
        path, _, value = line.rpartition(": merge: ")
        if path:
            out[path] = value.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_merge_attr",
        description=(
            "Report every local checkout whose MEMORY history or decisions files "
            "carry a git merge attribute other than unspecified (#107, #117)."
        ),
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Checkout root containing portfolio-ops/ and repos/ (default: cwd).",
    )
    args = parser.parse_args(argv)

    found = checkouts(Path(args.root))
    if not found:
        print(f"::error::no git checkouts under {args.root}", file=sys.stderr)
        return 2

    bad = 0
    # Checkouts git could not answer for (#118). Returning 2 from inside the
    # loop left every later checkout unasked, so a merge attribute on one of
    # them went unreported; each is reported and skipped instead.
    failed: list[str] = []
    for checkout in found:
        try:
            attrs = merge_attrs(checkout)
        except (OSError, subprocess.SubprocessError, RuntimeError) as e:
            print(f"::error::{checkout}: {e}", file=sys.stderr)
            failed.append(checkout.name)
            continue
        set_attrs = {p: v for p, v in attrs.items() if v != "unspecified"}
        if set_attrs:
            bad += 1
            for path, value in set_attrs.items():
                print(f"{checkout.name:<36} {path}: merge={value}")
        else:
            print(f"{checkout.name:<36} ok")

    if bad:
        print(
            f"::error::{bad} checkout(s) set a merge attribute on MEMORY files; "
            "remove it (usually a line in .git/info/attributes) so a sibling "
            "append conflicts and resolve_memory_conflict.py sees it (#107).",
            file=sys.stderr,
        )
        return 1
    if failed:
        # After the finding check, so a git error cannot hide a finding (#118).
        print(
            f"::error::git check-attr failed in: {', '.join(failed)}", file=sys.stderr
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
