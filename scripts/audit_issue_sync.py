#!/usr/bin/env python3
"""Decide what the audit cron should do with a findings set (portfolio-ops#72).

`audit-cron.yml` used to de-duplicate by asking *"is any `audit-cron` issue
open?"*::

    existing=$(gh issue list --state open --label audit-cron --json number --jq 'length')
    if [ "$existing" -gt 0 ]; then ... exit 0; fi

That is a check on **presence**, not on **content**. Issue #56 has held the slot
since 2026-06-29 and cannot be closed by a session — its only finding is blocked
on a secret only JT can configure (#17) — so every weekly run since has audited
13 repos, found something, and discarded it. Measured on the 2026-08-31 run:
``findings: 1 across 13 repo(s)`` immediately followed by ``An open [audit-cron]
issue already exists; skipping new file.``

Nothing has been lost yet only because the finding set has not changed. The day
a genuinely new one appears, the cron finds it and stays silent. A silent
failure in a silent-rot detector is the most expensive kind there is.

This module narrows the predicate without giving up the anti-spam property that
#24 asked for:

  * no open issue                  -> ``file``    (unchanged behaviour)
  * open issue, same finding set   -> ``silent``  (unchanged behaviour)
  * open issue, different set      -> ``comment`` (the gap this closes)

**Identity, not text.** The rendered finding line carries fields that change on
every run — ``stale-schedule`` counts up ``consecutive_failures`` weekly,
``paired-failure`` and ``main-branch-red`` carry a ``sha``, ``phantom-ci``
carries ``sample_shas``. Comparing rendered text would post a comment every
week, which is the spam #24 was avoiding. So each kind declares a stable
identity of the fields that name *which* thing is wrong, and the volatile
fields describing *how much* are excluded.

A kind with no declared identity raises. That is deliberate: an unknown kind
falling back to "compare everything" would make a brand-new fingerprint spam
weekly, and falling back to "compare nothing" would make it invisible. Both
failure modes are worse than a loud error, and a ninth fingerprint is exactly
the moment this file must be edited.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Iterable

#: The fields that name *which* thing is wrong, per fingerprint kind.
#:
#: Excluded on purpose, because they describe *how much* / *when* and move
#: between runs without the underlying problem changing:
#:   stale-schedule   consecutive_failures  (increments every weekly run)
#:   main-branch-red  sha, run_url, conclusion
#:   paired-failure   sha, runs
#:   phantom-ci       phantom_count, sample_shas, window
#:   missing-timeout  jobs_missing          (a job list that shifts as a
#:                                           workflow is edited, while the
#:                                           workflow is still the finding)
IDENTITY_FIELDS: dict[str, tuple[str, ...]] = {
    "main-branch-red": ("repo", "branch", "workflow_path"),
    "missing-concurrency": ("repo", "workflow_path"),
    "missing-timeout": ("repo", "workflow_path"),
    "paired-failure": ("repo",),
    "phantom-ci": ("repo", "workflow_id"),
    "stale-schedule": ("repo", "workflow_path"),
    "stuck-registration": ("repo", "workflow_id", "path"),
    "unpinned-lint-config": ("repo", "path"),
}

#: Fenced block on the issue recording what was last reported. Machine-readable
#: so the next run reads what the last run actually said, rather than
#: re-deriving it from the prose around it.
STATE_FENCE_LANG = "audit-fingerprints"
_STATE_RE = re.compile(
    rf"```{STATE_FENCE_LANG}\n(.*?)```",
    re.DOTALL,
)


class UnknownFindingKind(ValueError):
    """A finding whose kind has no declared identity.

    Raised rather than guessed. A new fingerprint added to
    ``audit_phase_a.py`` must also declare how two of its findings are
    "the same finding", or the cron will either spam it weekly or never
    report it — and which one you get would be an accident of whichever
    volatile field it happens to carry.
    """


def finding_identity(finding: dict[str, Any]) -> str:
    """A stable, sortable identity for *finding*.

    Two findings with the same identity are "the same problem", however much
    their counters have moved.
    """
    kind = finding.get("kind")
    if kind not in IDENTITY_FIELDS:
        raise UnknownFindingKind(
            f"no identity declared for finding kind {kind!r}. Add it to "
            "IDENTITY_FIELDS in scripts/audit_issue_sync.py, listing the "
            "fields that name WHICH thing is wrong and omitting the ones "
            "that describe how much (counts, shas, run urls)."
        )
    parts = [str(kind)]
    for field in IDENTITY_FIELDS[kind]:
        parts.append(f"{field}={finding.get(field, '')}")
    return "|".join(parts)


def fingerprint_set(findings: Iterable[dict[str, Any]]) -> list[str]:
    """The sorted, de-duplicated identity set for *findings*."""
    return sorted({finding_identity(f) for f in findings})


def parse_findings(text: str) -> list[dict[str, Any]]:
    """Parse `audit_phase_a.py --json` output: one JSON object per line."""
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def extract_recorded_set(*documents: str) -> list[str] | None:
    """The most recently recorded fingerprint set across *documents*.

    Pass the issue body first and then its comments oldest-to-newest; the last
    block found wins, so an update comment supersedes the body. Returns
    ``None`` when no block is present at all — an issue filed before this
    mechanism existed, which must be treated as "unknown", never as "empty".
    """
    recorded: list[str] | None = None
    for doc in documents:
        for match in _STATE_RE.finditer(doc or ""):
            recorded = sorted(
                line.strip() for line in match.group(1).splitlines() if line.strip()
            )
    return recorded


def render_state_block(fingerprints: Iterable[str]) -> str:
    """The machine-readable block to embed in an issue body or comment."""
    body = "\n".join(fingerprints)
    return f"```{STATE_FENCE_LANG}\n{body}\n```"


def decide(current: list[str], recorded: list[str] | None, has_open_issue: bool) -> str:
    """``file`` / ``comment`` / ``silent``.

    ``recorded is None`` with an open issue means the issue predates this
    mechanism. Comment: the whole point is that a set nobody has confirmed must
    not be assumed to match. Being noisy once, on the first run after this
    ships, is the correct trade against staying silent forever.
    """
    if not has_open_issue:
        return "file"
    if recorded is None:
        return "comment"
    return "silent" if current == recorded else "comment"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--findings-json",
        required=True,
        help="Path to `audit_phase_a.py --json` output (one object per line).",
    )
    parser.add_argument(
        "--issue-body",
        default="",
        help="Path to the open audit-cron issue's body, or empty when none is open.",
    )
    parser.add_argument(
        "--issue-comments",
        default="",
        help="Path to the open issue's comment bodies, oldest first, NUL-free.",
    )
    parser.add_argument(
        "--has-open-issue",
        action="store_true",
        help="Whether an audit-cron issue is currently open.",
    )
    parser.add_argument(
        "--out-state",
        help="Write the machine-readable fingerprint block here.",
    )
    args = parser.parse_args(argv)

    with open(args.findings_json, encoding="utf-8") as fh:
        findings = parse_findings(fh.read())

    current = fingerprint_set(findings)

    docs: list[str] = []
    for path in (args.issue_body, args.issue_comments):
        if path:
            with open(path, encoding="utf-8") as fh:
                docs.append(fh.read())
    recorded = extract_recorded_set(*docs) if args.has_open_issue else None

    action = decide(current, recorded, args.has_open_issue)

    if args.out_state:
        with open(args.out_state, "w", encoding="utf-8") as fh:
            fh.write(render_state_block(current) + "\n")

    print(action)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
