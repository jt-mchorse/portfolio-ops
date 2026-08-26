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


#: Trailer lines git may hoist out of the conflict region, followed by the
#: block's `---` closer. Captured so the ACTUAL hoisted text is reattached to
#: block_a rather than a hardcoded guess (#65).
HOISTED_TRAILER = re.compile(
    r"\A((?:(?:decisions_made|followups):[^\n]*\n)+)---\n",
)

#: A session block must carry exactly one of each. Used by the shape guard.
TRAILER_KEYS = ("decisions_made:", "followups:")


def resolve_yaml(text: str) -> str:
    """Resolve YAML conflicts in MEMORY/full_history_ai.md.

    Git hoists the two blocks' **common suffix** out of the conflict region, so
    whatever trailer lines both sides happened to share sit after the markers
    and belong to block_b. Block_a needs a copy of exactly those lines, plus its
    own `---` closer.

    The hoist is line-by-line, which is the subtlety this function got wrong
    until #65. The trailer was hardcoded as `decisions_made: []` +
    `followups: []`, which is right only when BOTH sessions recorded nothing --
    the one case where the whole trailer is common. When a session recorded a
    decision, only `followups: []` is common; `decisions_made:` differs and
    stays *inside* the region, still attached to block_a. Appending a hardcoded
    pair on top of it produced a duplicate key::

        session: A
        decisions_made: [D-015]      <- what the session recorded
        decisions_made: []           <- fabricated here
        followups: []

    and `yaml.safe_load` keeps the LAST duplicate, so the recorded decision
    silently vanished while the tool printed `resolved:` and exited 0. Measured
    across four real `git rebase` conflicts, three were malformed; the sound one
    was the both-empty control. Of the ten session entries written the night
    this was found, seven had a non-empty trailer -- the tool failed precisely
    on the entries that were worth writing down.

    Reattaching the *actual* hoisted lines is the whole fix: in the both-empty
    case they are `decisions_made: []` + `followups: []` and the output is
    byte-identical to before.
    """

    def repl(m: re.Match[str]) -> str:
        a = m.group(1)
        b = m.group(2)
        hoisted = HOISTED_TRAILER.match(m.string[m.end() :])
        if hoisted is None:
            # Nothing was hoisted: the two trailers differed entirely, so each
            # block already carries its own and only the separators are needed.
            return f"{a}\n---\n\n---\n{b}\n"
        return f"{a}\n{hoisted.group(1)}---\n\n---\n{b}\n"

    return CONFLICT.sub(repl, text)


def count_duplicated_trailers(text: str) -> int:
    """How many session blocks carry a duplicated trailer key."""
    n_bad = 0
    for block in text.split("\n---\n"):
        if "session:" not in block:
            continue
        for key in TRAILER_KEYS:
            n = block.count(f"\n{key}") + (1 if block.startswith(key) else 0)
            if n > 1:
                n_bad += 1
                break
    return n_bad


def check_block_shape(text: str, path: Path, *, before: int = 0) -> None:
    """Raise if any session block carries a DUPLICATED trailer key.

    `_process` already refuses to write a file with conflict markers left in it.
    A file that *looks* well-formed but carries a duplicated `decisions_made:`
    is the same class of failure -- worse, actually, because it is invisible --
    so it gets the same treatment (#65).

    This guard, not the resolution logic, is what would have caught the original
    defect: the resolver's output parsed fine, read plausibly, and lost data.

    Duplication only, deliberately -- an *absent* trailer is tolerated. The first
    version of this asserted "exactly one" and immediately refused to write a
    real file, because a session block from 2026-08-19 in
    `agent-orchestration-platform` (and one in this repo) simply has no
    `decisions_made:` line. That is a pre-existing shape this tool never created
    and has no business refusing to resolve around. Only `> 1` is the failure
    mode that loses data, because YAML resolves a duplicate key in favour of the
    last one.

    And it compares against `before` rather than checking absolutely, so
    PRE-EXISTING damage elsewhere in the file does not block a new resolution.
    Both narrowings were found by running the guard against the portfolio's real
    history instead of fixtures: the "exactly one" version refused a live file
    because two historical blocks have no `decisions_made:` at all, and the
    absolute version then refused because two OTHER blocks -- this repo's
    2026-05-27T15:25Z and `prompt-regression-suite`'s 2026-08-07T07:25Z -- are
    each two session entries fused into one with no `---` between them. Those are
    already-committed instances of this very class, from before the tool was
    fixed, and refusing to resolve around them would make the tool unusable on
    exactly the files that need it.
    """
    after = count_duplicated_trailers(text)
    if after <= before:
        return
    for block in text.split("\n---\n"):
        if "session:" not in block:
            continue
        for key in TRAILER_KEYS:
            n = block.count(f"\n{key}") + (1 if block.startswith(key) else 0)
            if n > 1:
                first = next(
                    (ln for ln in block.splitlines() if ln.startswith("session:")),
                    "<unknown>",
                )
                raise RuntimeError(
                    f"{path}: resolution introduced a duplicated trailer key -- block "
                    f"'{first}' has {n} `{key}` lines (was {before} bad block(s) before, "
                    f"{after} after). Refusing to write: a duplicated key is silently "
                    f"resolved by YAML in favour of the LAST one, which would discard "
                    f"what the session recorded. Inspect manually."
                )


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
    # Use the full CONFLICT regex (not a substring check) so prose mentions of
    # the marker token in MEMORY/ files don't trigger false positives. The
    # substring shortcut was the source of issue #25 — portfolio-ops' own
    # MEMORY/full_history_human.md documents the marker shape in prose.
    if not CONFLICT.search(original):
        return False
    resolved = resolver(original)
    if CONFLICT.search(resolved):
        raise RuntimeError(
            f"Conflict markers remain in {path} after resolution; shape did "
            "not match the expected append-only pattern. Inspect manually."
        )
    if resolver is resolve_yaml:
        check_block_shape(resolved, path, before=count_duplicated_trailers(original))
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
