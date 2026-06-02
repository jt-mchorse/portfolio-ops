#!/usr/bin/env python3
"""Resolve append-only MEMORY/ rebase conflicts by keeping both blocks.

The append-only convention in `MEMORY/full_history_ai.md` (YAML blocks) and
`MEMORY/full_history_human.md` (prose sections) means parallel session
branches almost always conflict when rebased: each branch added its own
entry at the file tail. Manual resolution is mechanical — keep both blocks
in chronological order — but easy to get wrong on the YAML trailer.

This tool performs the resolution in one call per repo. It was prototyped
across multiple sessions as `/tmp/resolve_memory_conflict.py`; this is the
in-tree promotion.

Conflict shapes handled:

  YAML (full_history_ai.md):
    <<<<<<< HEAD
    <block_a_body>
    =======
    <block_b_body>
    >>>>>>> <commit>
    decisions_made: []
    followups: []
    ---

    The shared trailer (`decisions_made`, `followups`, `---`) belongs to
    block_b. Resolution re-attaches the trailer to block_a and re-opens
    block_b with its own `---` opener so each block round-trips as a valid
    YAML frontmatter.

  Markdown (full_history_human.md):
    <<<<<<< HEAD
    <block_a_body>
    =======
    <block_b_body>
    >>>>>>> <commit>

    Resolution: concatenate with a blank line. No trailer munging needed.

Usage:
  python scripts/resolve_memory_conflict.py <repo-path>
  python scripts/resolve_memory_conflict.py <repo-path> --dry-run

Exit codes:
  0   ran successfully (may have resolved zero files; that's a valid outcome)
  1   missing repo path, missing MEMORY/ files, or conflict markers remain
      after resolution (the shape did not match expectations)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CONFLICT = re.compile(
    r"<<<<<<< HEAD\n(.*?)\n=======\n(.*?)\n>>>>>>> [^\n]*\n",
    re.DOTALL,
)


def resolve_yaml(text: str) -> str:
    """Resolve YAML conflicts in MEMORY/full_history_ai.md.

    The shared trailer (`decisions_made`, `followups`, `---`) sits after the
    conflict markers and belongs to block_b. We restore it onto block_a and
    re-open block_b with `---` so each session entry remains a self-contained
    YAML frontmatter block.
    """

    def repl(m: re.Match[str]) -> str:
        a = m.group(1)
        b = m.group(2)
        return f"{a}\ndecisions_made: []\nfollowups: []\n---\n\n---\n{b}\n"

    return CONFLICT.sub(repl, text)


def resolve_md(text: str) -> str:
    """Resolve Markdown conflicts in MEMORY/full_history_human.md.

    Simple concatenation with a blank line between blocks. No trailer.
    """

    def repl(m: re.Match[str]) -> str:
        a = m.group(1)
        b = m.group(2)
        return f"{a}\n\n{b}\n"

    return CONFLICT.sub(repl, text)


def _process(path: Path, resolver, dry_run: bool) -> bool:
    """Resolve conflicts in `path` using `resolver`. Returns True if changed."""
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    if "<<<<<<<" not in original:
        return False
    resolved = resolver(original)
    if "<<<<<<<" in resolved:
        raise RuntimeError(
            f"Conflict markers remain in {path} after resolution; shape did "
            "not match the expected append-only pattern. Inspect manually."
        )
    if dry_run:
        print(f"would resolve: {path}")
    else:
        path.write_text(resolved, encoding="utf-8")
        print(f"resolved: {path}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else None,
    )
    parser.add_argument(
        "repo_path",
        help="Path to repo root (containing MEMORY/full_history_*.md).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be resolved without writing.",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo_path).resolve()
    if repo.is_file():
        print(
            f"error: '{args.repo_path}' is a file; pass the repo root "
            "containing MEMORY/ instead",
            file=sys.stderr,
        )
        return 1
    if not (repo / "MEMORY").is_dir():
        print(f"error: {repo}/MEMORY/ not found", file=sys.stderr)
        return 1

    yaml_path = repo / "MEMORY" / "full_history_ai.md"
    md_path = repo / "MEMORY" / "full_history_human.md"

    changed_any = False
    try:
        changed_any |= _process(yaml_path, resolve_yaml, args.dry_run)
        changed_any |= _process(md_path, resolve_md, args.dry_run)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not changed_any:
        print("no conflicts found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
