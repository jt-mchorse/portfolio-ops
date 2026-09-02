"""The cron must report a *changed* finding set even while an issue is open (#72).

`audit-cron.yml` de-duplicated on presence — "is any `audit-cron` issue open?"
— not on content. Issue #56 has held that slot since 2026-06-29 and cannot be
closed by a session (its finding is blocked on a secret only JT can set, #17),
so every weekly run since has audited 13 repos, found something, and thrown it
away. Measured on the 2026-08-31 run: `findings: 1 across 13 repo(s)` followed
immediately by `An open [audit-cron] issue already exists; skipping new file.`

The two assertions that matter face each other here, and neither is meaningful
without the other:

  * a set whose ONLY delta is the weekly `consecutive_failures` increment must
    produce SILENCE — otherwise the fix is a spam generator and #24's anti-spam
    property is lost;
  * a set with one genuinely new finding must produce a COMMENT — otherwise the
    fix changes nothing and this file is decoration.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from audit_issue_sync import (  # noqa: E402
    IDENTITY_FIELDS,
    UnknownFindingKind,
    decide,
    extract_recorded_set,
    finding_identity,
    fingerprint_set,
    parse_findings,
    render_state_block,
)

SCRIPT = REPO_ROOT / "scripts" / "audit_issue_sync.py"
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_phase_a.py"


def _stale_schedule(consecutive_failures: int, name: str = "trending-daily") -> dict:
    """The finding that has actually been holding the slot, verbatim in shape."""
    return {
        "kind": "stale-schedule",
        "repo": "portfolio-ops",
        "name": name,
        "workflow_path": f".github/workflows/{name}.yml",
        "consecutive_failures": consecutive_failures,
    }


# ---------------------------------------------------------------------------
# The two arms.
# ---------------------------------------------------------------------------


def test_only_the_weekly_counter_moved_stays_silent() -> None:
    """#56 was filed at 7 consecutive failures and the audit now reports 8.

    If that counts as a change, this fix posts a comment every single week
    forever — which is exactly the spam the presence-check was avoiding. The
    identity must exclude `consecutive_failures`.
    """
    week_one = fingerprint_set([_stale_schedule(7)])
    week_ten = fingerprint_set([_stale_schedule(8)])

    assert week_one == week_ten
    assert decide(week_ten, week_one, has_open_issue=True) == "silent"


def test_one_genuinely_new_finding_is_reported() -> None:
    """The gap this closes: a second, unrelated problem while #56 is open."""
    before = fingerprint_set([_stale_schedule(7)])
    after = fingerprint_set(
        [
            _stale_schedule(8),
            {
                "kind": "main-branch-red",
                "repo": "llm-eval-harness",
                "branch": "main",
                "workflow_path": ".github/workflows/ci.yml",
                "workflow_name": "CI",
                "workflow_id": 1,
                "conclusion": "failure",
                "sha": "deadbeef",
                "run_url": "https://example.invalid/1",
            },
        ]
    )

    assert after != before
    assert decide(after, before, has_open_issue=True) == "comment"


# ---------------------------------------------------------------------------
# Identity: what each kind treats as volatile.
# ---------------------------------------------------------------------------


VOLATILE_CASES = [
    (
        "main-branch-red re-runs on a new sha",
        {
            "kind": "main-branch-red",
            "repo": "r",
            "branch": "main",
            "workflow_path": "w.yml",
            "workflow_name": "CI",
            "workflow_id": 1,
        },
        {"conclusion": "failure", "sha": "aaa", "run_url": "u1"},
        {"conclusion": "cancelled", "sha": "bbb", "run_url": "u2"},
    ),
    (
        "paired-failure lands on a different sha",
        {"kind": "paired-failure", "repo": "r"},
        {"sha": "aaa", "runs": [{"name": "a", "conclusion": "failure"}]},
        {"sha": "bbb", "runs": [{"name": "a", "conclusion": "failure"}]},
    ),
    (
        "phantom-ci samples different shas",
        {"kind": "phantom-ci", "repo": "r", "workflow_id": 7},
        {"phantom_count": 3, "sample_shas": ["a"], "window": 30},
        {"phantom_count": 9, "sample_shas": ["b", "c"], "window": 30},
    ),
    (
        "missing-timeout's job list shifts as the workflow is edited",
        {"kind": "missing-timeout", "repo": "r", "workflow_path": "w.yml", "workflow_name": "CI"},
        {"jobs_missing": ["build"]},
        {"jobs_missing": ["build", "test"]},
    ),
    (
        "stale-schedule counts up",
        {"kind": "stale-schedule", "repo": "r", "workflow_path": "w.yml", "name": "n"},
        {"consecutive_failures": 3},
        {"consecutive_failures": 40},
    ),
]


@pytest.mark.parametrize(
    ("label", "stable", "before", "after"),
    VOLATILE_CASES,
    ids=[c[0] for c in VOLATILE_CASES],
)
def test_volatile_fields_do_not_change_identity(
    label: str, stable: dict, before: dict, after: dict
) -> None:
    assert finding_identity({**stable, **before}) == finding_identity({**stable, **after}), label


@pytest.mark.parametrize(
    ("field", "other"),
    [("repo", "different-repo"), ("workflow_path", "other.yml")],
)
def test_identity_fields_do_change_identity(field: str, other: str) -> None:
    """The mirror. Without this, an identity of `()` would pass every test above
    while collapsing every finding in the portfolio into one."""
    base = _stale_schedule(3)
    assert finding_identity(base) != finding_identity({**base, field: other})


def test_every_fingerprint_kind_in_the_audit_has_a_declared_identity() -> None:
    """Discovered from the audit script, not hand-listed.

    A hand-written list cannot see a ninth fingerprint. This reads the kinds
    `audit_phase_a.py` can actually emit, so adding one without declaring its
    identity fails here rather than silently becoming weekly spam or becoming
    invisible.
    """
    source = AUDIT_SCRIPT.read_text(encoding="utf-8")
    emitted = set(re.findall(r'"kind":\s*"([a-z-]+)"', source))

    # Anti-vacuous: a regex that matched nothing would satisfy the subset check
    # below while checking nothing at all.
    assert len(emitted) >= 8, f"expected the audit's eight+ fingerprints, found {emitted}"

    missing = emitted - set(IDENTITY_FIELDS)
    assert not missing, (
        f"fingerprint kinds with no identity in audit_issue_sync.IDENTITY_FIELDS: "
        f"{sorted(missing)}. Declare the fields that name WHICH thing is wrong."
    )


def test_an_undeclared_kind_raises_rather_than_guessing() -> None:
    """Neither silent-compare-equal nor compare-everything is an acceptable
    default: one makes a new fingerprint invisible, the other makes it spam."""
    with pytest.raises(UnknownFindingKind):
        finding_identity({"kind": "brand-new-fingerprint", "repo": "r"})


# ---------------------------------------------------------------------------
# Recorded state round trip.
# ---------------------------------------------------------------------------


def test_state_block_round_trips() -> None:
    fps = fingerprint_set([_stale_schedule(8)])
    assert extract_recorded_set(f"prose\n\n{render_state_block(fps)}\n\nmore prose") == fps


def test_the_newest_comment_supersedes_the_body() -> None:
    old = fingerprint_set([_stale_schedule(7)])
    new = fingerprint_set(
        [_stale_schedule(7), {"kind": "unpinned-lint-config", "repo": "r", "path": "p.toml"}]
    )
    body = render_state_block(old)
    comments = f"{render_state_block(old)}\n---\n{render_state_block(new)}"

    assert extract_recorded_set(body, comments) == new


def test_an_issue_with_no_recorded_block_is_unknown_not_empty() -> None:
    """#56 was filed before this mechanism existed.

    Treating "no block" as "an empty set" would compare unequal and comment —
    which is right — but for the wrong reason, and would flip to silence the
    moment the real set was also empty. `None` says "nobody confirmed this",
    and `decide` chooses to speak. Being noisy once on the first run after this
    ships is the correct trade against staying silent forever.
    """
    assert extract_recorded_set("no fenced block here") is None
    assert decide(["anything"], None, has_open_issue=True) == "comment"


def test_no_open_issue_still_files() -> None:
    """The unchanged path. Without this the fix could regress the normal case."""
    assert decide(fingerprint_set([_stale_schedule(3)]), None, has_open_issue=False) == "file"


# ---------------------------------------------------------------------------
# The CLI the workflow actually calls.
# ---------------------------------------------------------------------------


def test_cli_end_to_end(tmp_path: Path) -> None:
    findings = tmp_path / "findings.json"
    findings.write_text(
        json.dumps(_stale_schedule(8)) + "\n", encoding="utf-8"
    )
    body = tmp_path / "body.md"
    body.write_text(render_state_block(fingerprint_set([_stale_schedule(7)])), encoding="utf-8")
    state = tmp_path / "state.md"

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--findings-json",
            str(findings),
            "--issue-body",
            str(body),
            "--has-open-issue",
            "--out-state",
            str(state),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    # Same problem, one week later: silent.
    assert proc.stdout.strip() == "silent"
    assert extract_recorded_set(state.read_text(encoding="utf-8")) == fingerprint_set(
        [_stale_schedule(8)]
    )


def test_parse_findings_ignores_blank_lines() -> None:
    assert parse_findings("\n" + json.dumps(_stale_schedule(1)) + "\n\n") == [_stale_schedule(1)]
