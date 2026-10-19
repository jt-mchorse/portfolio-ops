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

  diff3 / zdiff3 (`merge.conflictStyle`), either file:
    <<<<<<< HEAD
    <block_a_body>
    ||||||| <base label>
    <base_body>
    =======
    <block_b_body>
    >>>>>>> <commit>

    The base section is what both sides started from. For an append-only file
    that is empty, so it is dropped; a NON-empty base means a side edited
    existing history, which is not this tool's shape -- refused (#90). diff3
    also does no common-line hoisting, so each side is already a complete
    `---`...`---` block and is concatenated as-is.

  Several hunks for one appended entry (#95), either file:
    git's default merge aligns lines the two appended entries SHARE (`delta:`,
    `  files_changed: 2`, a repeated prose line) and leaves them between two
    hunks. The shapes above are therefore not resolved hunk by hunk: both whole
    sides are rebuilt from the conflict text and written as "all of ours, then
    theirs from the last section break they share". The YAML trailer handling
    and the diff3 base handling fall out of that without special cases.

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
    r"<<<<<<< HEAD\n(.*?)\n(?:\|\|\|\|\|\|\|[^\n]*\n(.*?))?=======\n(.*?)\n>>>>>>> [^\n]*\n",
    re.DOTALL,
)

#: A line that is one of git's conflict markers. Before #90 the regex above
#: had no base section, so under diff3/zdiff3 it matched anyway -- with the
#: `|||||||` line swallowed into block_a -- and wrote that line back out while
#: printing `resolved:` and exiting 0. Counting marker lines before and after
#: is what makes any shape this module does not know fail loudly instead.
MARKER_LINE = re.compile(r"^(?:<{7}|\|{7}|={7}|>{7})(?: |$)", re.MULTILINE)


def _sides(m: re.Match[str]) -> tuple[str, str]:
    """Return (block_a, block_b), refusing a conflict that edited history.

    An append-only conflict has an empty base: both sides only added lines
    after the same point. diff3's base section is therefore empty or blank; if
    it carries text, one side changed an existing entry, and keeping both
    sides would silently keep the old and the new version of it.
    """
    base = m.group(2)
    if base is not None and base.strip():
        raise RuntimeError(
            "conflict has a non-empty base section, so a side edited existing "
            "history; that is not the append-only shape. Inspect manually."
        )
    return m.group(1), m.group(3)


#: A session block must carry exactly one of each. Used by the shape guard.
TRAILER_KEYS = ("decisions_made:", "followups:")


def _two_sides(text: str) -> tuple[str, str]:
    """Rebuild the two whole files git merged: (ours, theirs).

    *Ours* takes side A of every conflict hunk, *theirs* side B, and both keep
    every line git left outside the markers. Done for the whole file at once,
    because git's hunks are not blocks (#95): the default merge aligns any line
    the two appended blocks happen to share -- `phase: shipped`, `delta:`,
    `  files_changed: 2` -- and leaves it BETWEEN two hunks, so one appended
    block arrives as two hunks with common lines in the middle. Resolving each
    hunk as if it were a whole block split block A after its header, glued A's
    tail onto B's header, and orphaned B's tail, with rc 0 (lco#309, and six
    other repos the same week).
    """
    ours: list[str] = []
    theirs: list[str] = []
    pos = 0
    for m in CONFLICT.finditer(text):
        a, b = _sides(m)
        common = text[pos : m.start()]
        ours += [common, a, "\n"]
        theirs += [common, b, "\n"]
        pos = m.end()
    tail = text[pos:]
    return "".join(ours) + tail, "".join(theirs) + tail


def _yaml_break(lines: list[str], k: int) -> bool:
    """A blank line followed by a `---` opener: where a session block begins."""
    return k + 1 < len(lines) and lines[k] == "\n" and lines[k + 1] == "---\n"


def _md_break(lines: list[str], k: int) -> bool:
    """A blank line followed by a `## ` heading: where a prose section begins."""
    return k + 1 < len(lines) and lines[k] == "\n" and lines[k + 1].startswith("## ")


def _paragraph_break(lines: list[str], k: int) -> bool:
    """A blank line followed by text: the prose file's fallback section start,
    for a file (or a hand-rolled fixture) whose entries carry no heading."""
    return k + 1 < len(lines) and lines[k] == "\n" and lines[k + 1].strip() != ""


def _sections(lines: list[str], is_break) -> list[str]:
    """Split lines into sections at each break; used to compare two tails."""
    out: list[str] = []
    cur: list[str] = []
    for k, line in enumerate(lines):
        if is_break(lines, k) and cur:
            out.append("".join(cur))
            cur = []
        cur.append(line)
    if cur:
        out.append("".join(cur))
    return [sec for sec in out if sec.strip()]


def _keep_both(text: str, is_break, fallback=None, *, prose: bool = False) -> str:
    """Resolve every conflict in `text` as "all of ours, then theirs' new part".

    Append-only means each side is the shared history plus what that side
    appended. The two whole sides agree up to some line; backing off from there
    to the last section break BOTH share gives the point where the appended
    sections start, whatever lines git chose to align inside them. Writing ours
    in full and then theirs from that break keeps each appended section intact
    and in order -- upstream's first, then the rebased commit's -- which is what
    the hunk-by-hunk resolution meant to do and did only for a single hunk.

    Two shapes are refused rather than guessed. No shared break: the file is not
    a sequence of sections this tool knows. A section present in BOTH tails:
    the sides share history past the point where they diverge, which means one
    side edited an existing entry, and keeping both would keep it twice (the
    default-style blind spot #90 recorded and did not close).
    """
    if not CONFLICT.search(text):
        return text
    ours, theirs = _two_sides(text)
    if not ours.endswith("\n"):
        ours += "\n"
    o = ours.splitlines(keepends=True)
    t = theirs.splitlines(keepends=True)
    p = 0
    while p < min(len(o), len(t)) and o[p] == t[p]:
        p += 1
    k = None
    for brk in (is_break, fallback):
        if brk is None:
            continue
        k = next((i for i in range(p, -1, -1) if brk(o, i) and brk(t, i)), None)
        if k is not None:
            is_break = brk
            break
    if k is None and p == 0:
        # Nothing at all in common: the whole of each side is new.
        k = 0
    if k is None:
        raise RuntimeError(
            "no section break shared by both sides before they diverge, so the "
            "appended entries cannot be told apart. Inspect manually."
        )
    shared = set(_sections(o[k:], is_break)) & set(_sections(t[k:], is_break))
    if shared:
        raise RuntimeError(
            f"{len(shared)} entr{'y' if len(shared) == 1 else 'ies'} appear on both "
            "sides after they diverge, so a side edited existing history; that is "
            "not the append-only shape. Inspect manually."
        )
    if prose:
        # One blank line between sections, however each side ended.
        return ours.rstrip("\n") + "\n\n" + "".join(t[k:]).lstrip("\n")
    return ours + "".join(t[k:])


def resolve_yaml(text: str) -> str:
    """Resolve YAML conflicts in MEMORY/full_history_ai.md.

    Two earlier versions of this function resolved each conflict hunk as one
    whole block, re-attaching whatever trailer git hoisted after it. Both failed
    on a shape git really produces. #65: the hoist is line by line, so a
    hardcoded `decisions_made: []` + `followups: []` duplicated a recorded
    decision key and YAML kept the fabricated one. #95: git also aligns
    *interior* lines the two blocks share, so one block can arrive as several
    hunks, and a per-hunk resolution splits it. `_keep_both` never reads hunk
    boundaries as block boundaries, so neither the hoisted trailer nor the
    aligned interior needs a special case: both are common lines, present in
    both rebuilt sides.
    """
    return _keep_both(text, _yaml_break)


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

    Same whole-side resolution as the YAML file, with a `## ` heading as the
    section start: two prose sections that share a paragraph line split into
    hunks exactly the way two YAML blocks sharing `delta:` do (#95).
    """
    return _keep_both(text, _md_break, _paragraph_break, prose=True)


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
    try:
        resolved = resolver(original)
    except RuntimeError as exc:
        raise RuntimeError(f"{path}: {exc}") from None
    # Compared against the original with its conflicts removed, not against
    # zero, so a marker-shaped line already in the file's prose is tolerated.
    markers_before = len(MARKER_LINE.findall(CONFLICT.sub("", original)))
    if (
        CONFLICT.search(resolved)
        or len(MARKER_LINE.findall(resolved)) > markers_before
    ):
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
