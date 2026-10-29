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

**The same mechanism in the decisions file (#75, D-013).** ``#`` opening an
item of *any* flow sequence does it, and ``MEMORY/core_decisions_ai.md`` writes
``related_issues: [#188, #106]`` in every repo. That file is one YAML sequence,
so ``yaml.safe_load`` stops at the first bad line and a consumer reads zero
decisions, not "all but a few" -- 12 of 12 code repos and this one were in that
state when #75 measured it, with ``memory-check`` green on all of them because
it only asks ``test -f`` and ``grep -q "id: D-001"``. ``--kind decisions``
ratchets that file the same way: the unit is one ``- id:`` entry, parsed on its
own, so one bad line costs one entry and the count can move in both directions
as entries are added or repaired. D-013 extends D-010's rule to it: quote every
list item, ``related_issues: ["#75"]``.

Exit codes match the portfolio convention `audit_phase_a.py` uses:
``0`` within baseline, ``1`` a repo regressed, ``2`` a usage or I/O error.
A repo that cannot be read (a missing clone, ref, or file) is reported and
skipped, and every other repo is still checked (#118). Exit ``1`` outranks
``2``: a run with a regression and an I/O error exits ``1``, so an unreadable
repo can never hide a regression in another one. ``--write-baseline`` writes
nothing when any repo could not be read.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
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
    for i, block in enumerate(_FENCE.split(text)):
        if not _is_block(block, header=i == 0):
            continue
        total += 1
        try:
            loaded = yaml.safe_load(block)
        except Exception as e:  # noqa: BLE001 - any loader failure counts
            unparseable += 1
            reasons.append(str(e).splitlines()[0].strip())
            continue
        if not (isinstance(loaded, dict) and "session" in loaded):
            # Loads, but is not a session entry: an orphaned tail such as the
            # ones #95's per-hunk resolution left behind.
            unparseable += 1
            first = next(ln for ln in block.splitlines() if _is_content(ln))
            reasons.append(f"fenced fragment with no session key: {first.strip()[:60]}")
            continue
        dups = _duplicate_top_level_keys(block)
        if dups:
            # Loads, but as one mapping where the last copy of each key won
            # (#107). Two entries glued without their `---` fence, the shape a
            # clean `merge=union` rebase produced, read as the second entry
            # alone, so the first one is gone without a parse error.
            unparseable += 1
            reasons.append(f"duplicate top-level key(s): {', '.join(dups)}")
    return unparseable, total, reasons


def _duplicate_top_level_keys(block: str) -> list[str]:
    """Top-level keys a block repeats, in first-seen order (#107).

    ``yaml.safe_load`` keeps the last value of a repeated key and says
    nothing, so the loaded mapping cannot show the loss. The composed node
    still holds every key as written. Only the top level is checked: that is
    where a glued pair repeats ``session:``, and where a hand edit repeating
    ``decisions_made:`` silently drops the first list.
    """
    import yaml

    return _duplicate_keys(yaml.compose(block, Loader=yaml.SafeLoader))


def _duplicate_keys(node: Any) -> list[str]:
    """Keys a composed mapping node repeats, in first-seen order."""
    import yaml

    if not isinstance(node, yaml.MappingNode):
        return []
    seen: set[str] = set()
    dups: list[str] = []
    for key, _value in node.value:
        if not isinstance(key, yaml.ScalarNode):
            continue
        if key.value in seen and key.value not in dups:
            dups.append(key.value)
        seen.add(key.value)
    return dups


def _is_content(line: str) -> bool:
    return bool(line.strip()) and not line.lstrip().startswith("#")


def _is_block(chunk: str, *, header: bool) -> bool:
    """Is this fenced chunk an entry the ratchet must account for? (#97)

    Until #97 a chunk counted only if the substring ``session:`` appeared
    anywhere in it, so an orphaned fragment was invisible unless it happened
    to carry ``context_for_next_session:``. Now every chunk with a
    non-comment line counts, except the file's own prose header before the
    first fence -- which counts only if it is itself a session entry, the
    shape a fence-less file (or fixture) has.
    """
    if header:
        return re.search(r"^session:", chunk, re.M) is not None
    return any(_is_content(ln) for ln in chunk.splitlines())


# The id a decision entry opens with, as written on its `- id:` line. Read
# from the text rather than the loaded entry, so an entry that fails to load
# still claims its id and a later copy of it is still seen.
_DECISION_ID = re.compile(r"""^- id:[ \t]*["']?([^\s"'#]+)""")

# A decision entry opens with `- id:` at column 0. Anything before the first
# one is the file's comment header, and a `# D-002 superseded` comment between
# entries rides along with the entry above it, where it is harmless.
_DECISION = re.compile(r"^(?=- id:)", re.M)


def count_unparseable_decisions(text: str) -> tuple[int, int, list[str]]:
    """Return ``(unparseable, total, reasons)`` for one core_decisions_ai.md.

    Each ``- id:`` entry is loaded on its own (#75). Loading the whole file
    would report one failure for a file with ten bad entries, and zero entries
    readable either way, so it could not tell a repo that added a bad entry
    from one that repaired three.

    An entry that loads still counts if its mapping repeats a key, or if its
    id repeats an earlier entry's (#117). Both are what a clean ``merge=union``
    merge of two appends leaves, and both load without an error.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover - exercised by the operator path
        raise SystemExit(
            "check_memory_yaml requires pyyaml: pip install -r scripts/requirements.txt"
        ) from None

    unparseable = 0
    total = 0
    reasons: list[str] = []
    ids: set[str] = set()
    for entry in _DECISION.split(text):
        if not entry.startswith("- id:"):
            continue
        total += 1
        m = _DECISION_ID.match(entry)
        if m:
            if m.group(1) in ids:
                # Two entries claiming one id (#117): a consumer looking a
                # decision up by id reads whichever it finds first. Only the
                # later copy is counted, so one repeat costs one entry.
                unparseable += 1
                reasons.append(f"{entry.splitlines()[0].strip()}: duplicate id")
                continue
            ids.add(m.group(1))
        try:
            loaded = yaml.safe_load(entry)
        except Exception as e:  # noqa: BLE001 - any loader failure counts
            unparseable += 1
            first = entry.splitlines()[0].strip()
            reasons.append(f"{first}: {str(e).splitlines()[0].strip()}")
            continue
        # An entry that loads, but not as the one-mapping list it is written
        # as, is not a decision a consumer can read either.
        if not (
            isinstance(loaded, list)
            and len(loaded) == 1
            and isinstance(loaded[0], dict)
        ):
            unparseable += 1
            reasons.append(f"{entry.splitlines()[0].strip()}: not a single mapping")
            continue
        # Loads, but with a key the entry's mapping repeats (#117), the #107
        # check one level down. Two appends of the same `- id:` glued by a
        # clean `merge=union` merge share the id line and keep every other
        # line, so the entry reads as the later decision alone.
        node = yaml.compose(entry, Loader=yaml.SafeLoader)
        dups = _duplicate_keys(node.value[0])
        if dups:
            unparseable += 1
            reasons.append(
                f"{entry.splitlines()[0].strip()}: duplicate key(s): {', '.join(dups)}"
            )
    return unparseable, total, reasons


# One entry per --kind: the file it reads, how it counts, and the baseline key
# it ratchets against. `history` keeps the key #66 shipped, so the committed
# baseline and every existing invocation mean what they meant.
KINDS: dict[str, dict[str, Any]] = {
    "history": {
        "file": "full_history_ai.md",
        "count": count_unparseable,
        "key": "unparseable_by_repo",
        "unit": "session blocks",
        "hint": 'Per D-010, write followups as quoted strings: followups: ["#107"].',
    },
    "decisions": {
        "file": "core_decisions_ai.md",
        "count": count_unparseable_decisions,
        "key": "unparseable_decisions_by_repo",
        "unit": "decision entries",
        "hint": 'Per D-013, quote every list item: related_issues: ["#75"].',
    },
}


def _read_baseline_file() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        return {}
    data: Any = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_baseline(kind: str = "history") -> dict[str, int]:
    data = _read_baseline_file()
    return {str(k): int(v) for k, v in data.get(KINDS[kind]["key"], {}).items()}


def memory_file(root: Path, repo: str, kind: str = "history") -> Path:
    """Resolve a repo's MEMORY file of one kind under a checkout root.

    `portfolio-ops` is cloned beside `repos/` rather than inside it, which is
    the layout the session prompt's Phase A assumes.
    """
    name = KINDS[kind]["file"]
    if repo == "portfolio-ops":
        return root / "portfolio-ops" / "MEMORY" / name
    return root / "repos" / repo / "MEMORY" / name


def read_at_ref(root: Path, repo: str, ref: str, kind: str = "history") -> str:
    """Read a repo's MEMORY file of one kind as committed at ``ref`` (#112).

    The working tree of a local clone is whatever branch the last session left
    it on. On 2026-10-26, 12 of the 13 clones were on old ``session/*``
    branches or a detached HEAD, and a working-tree ``--root`` run reported 7
    repos REGRESSED on damage that #109 had already repaired on main. Phase A
    asks about main, so it reads ``origin/main`` through ``git show``, which
    sees exactly what the last ``git fetch`` saw and never touches the
    checkout. Raises ``FileNotFoundError`` when the clone, the ref, or the file
    at that ref is missing, which the caller reports and skips (#118).
    """
    path = memory_file(root, repo, kind)
    clone = path.parent.parent
    if not clone.is_dir():
        raise FileNotFoundError(f"{clone} not found")
    spec = f"{ref}:MEMORY/{KINDS[kind]['file']}"
    try:
        proc = subprocess.run(
            ["git", "-C", str(clone), "show", spec],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise FileNotFoundError(f"{clone}: git show {spec}: {e}") from None
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise FileNotFoundError(
            f"{clone}: git show {spec}: {err[0] if err else 'failed'}"
        )
    return proc.stdout.decode("utf-8")


def repo_name_for(path: Path) -> str:
    """Name the repo a ``--file`` MEMORY file belongs to (#102).

    The name keys the baseline, so it must be the repo's name, not its
    checkout's. Until #102 it was ``path.resolve().parents[1].name`` alone,
    and a worktree such as ``/tmp/w/hunt2-ops`` became repo ``hunt2-ops``:
    no baseline, an allowance of 0, and a false REGRESSED on a green main.
    The origin URL names the repo in every checkout of it -- clone, worktree,
    or a ``repos/leh-266`` beside the canonical one -- so it is asked first.
    The directory name is the fallback for a file outside any git checkout.
    """
    parent = path.resolve().parent
    try:
        proc = subprocess.run(
            ["git", "-C", str(parent), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        proc = None
    if proc is not None and proc.returncode == 0:
        # https://host/o/name.git, git@host:o/name.git and a local path all
        # end in the repo name, after the last `/` or `:`.
        url = proc.stdout.strip().rstrip("/")
        name = re.split(r"[/:]", url)[-1].removesuffix(".git")
        if name:
            return name
    return path.resolve().parents[1].name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_memory_yaml",
        description=(
            "Fail if any repo's count of unparseable MEMORY/full_history_ai.md "
            "session blocks (#66), or with --kind decisions its unparseable "
            "MEMORY/core_decisions_ai.md entries (#75), exceeds its committed baseline."
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
        "--kind",
        choices=sorted(KINDS),
        default="history",
        help="Which MEMORY file to ratchet (default: history, i.e. full_history_ai.md).",
    )
    parser.add_argument(
        "--file",
        help=(
            "Check a single MEMORY file of --kind directly; implies --repo of its "
            "repo name, from the origin URL, else the checkout directory (#102)."
        ),
    )
    parser.add_argument(
        "--ref",
        help=(
            "With --root, read each MEMORY file as committed at this git ref "
            "(e.g. origin/main) instead of the clone's working tree (#112). "
            "Fetch first: a remote-tracking ref is as fresh as the last fetch."
        ),
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Rewrite the baseline from the current counts. For a deliberate retro-fix only.",
    )
    args = parser.parse_args(argv)
    if args.ref and args.file:
        parser.error("--ref reads clones under --root; it cannot be combined with --file")

    kind = KINDS[args.kind]
    baseline = load_baseline(args.kind)
    root = Path(args.root)

    if args.file:
        path = Path(args.file)
        repos = [args.repo[0] if args.repo else repo_name_for(path)]
        paths = {repos[0]: path}
    else:
        repos = args.repo or sorted(baseline)
        if not repos:
            print(
                "::error::no baseline and no --repo given; nothing to check",
                file=sys.stderr,
            )
            return 2
        paths = {r: memory_file(root, r, args.kind) for r in repos}

    counts: dict[str, int] = {}
    regressions: list[str] = []
    # Repos that could not be read (#118). Until #118 the first one returned 2
    # from inside this loop, so every repo after it was never checked and a
    # regression there went unreported for the run. Each is reported and
    # skipped instead; the exit code is decided after the loop.
    unreadable: list[str] = []
    for repo in repos:
        path = paths[repo]
        if args.ref:
            try:
                text = read_at_ref(root, repo, args.ref, args.kind)
            except FileNotFoundError as e:
                print(f"::error::{e}", file=sys.stderr)
                unreadable.append(repo)
                continue
        elif not path.exists():
            print(f"::error::{path} not found", file=sys.stderr)
            unreadable.append(repo)
            continue
        else:
            text = path.read_text(encoding="utf-8")
        bad, total, reasons = kind["count"](text)
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
        if unreadable:
            # A re-freeze is a deliberate act over a known set of repos. One
            # that could not read some of them is not that act, so nothing is
            # written rather than a baseline that silently skips them.
            print(
                f"::error::not writing the baseline: could not read {', '.join(unreadable)}",
                file=sys.stderr,
            )
            return 2
        # Rewrite only this kind's key. The other kind's frozen counts are
        # someone else's ratchet and must survive a regeneration of this one.
        data = _read_baseline_file()
        data["_comment"] = (
            "Unparseable MEMORY entries per repo: session blocks in full_history_ai.md "
            "(frozen by #66) and decision entries in core_decisions_ai.md (frozen by "
            "#75). This is a RATCHET: check_memory_yaml.py fails when a count grows, "
            "never demanding zero, so the retro-fix decision (#66, #75) stays JT's. "
            "Regenerate with --write-baseline only as part of a deliberate retro-fix."
        )
        # Merge into this kind's map rather than replacing it (#111). A run
        # limited by --repo or --file counted only those repos, and a default
        # run takes its repo list from the baseline, so a repo dropped here is
        # silently never checked again. A one-repo re-freeze must change that
        # repo's count and nothing else.
        merged = {**data.get(kind["key"], {}), **counts}
        data[kind["key"]] = dict(sorted(merged.items()))
        ordered = {"_comment": data.pop("_comment"), **data}
        BASELINE_PATH.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {BASELINE_PATH}")
        return 0

    if regressions:
        print(
            f"::error::unparseable MEMORY {kind['unit']} increased in: "
            f"{', '.join(regressions)}. {kind['hint']}",
            file=sys.stderr,
        )
        return 1
    if unreadable:
        # Only after the regression check: a repo that regressed is reported
        # as exit 1 even when another repo could not be read, so an I/O error
        # can never hide a regression (#118).
        print(
            f"::error::could not read MEMORY {kind['unit']} for: {', '.join(unreadable)}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
