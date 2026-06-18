#!/usr/bin/env python3
"""Phase A operational-health audit.

Catches six silent-rot fingerprints across the 13 portfolio repos:

1. paired-failure  — a single push-event SHA produces multiple workflow runs
                     with conflicting conclusions (one success + one failure).
                     This is the shape that hid ci-template.yml's 17 days of
                     red runs in portfolio-ops (#13).
2. stuck-registration — a workflow whose registered `name` starts with
                        `.github/workflows/` (path-as-name fallback). This is
                        the shape of corrupted-by-historical-collision
                        workflows that don't honor `workflow_dispatch:` or
                        re-parse YAML edits (#15).
3. stale-schedule  — a workflow with `>= N` consecutive failed scheduled
                     runs and no successes between them. This is the shape
                     of secret-missing or upstream-broken cron jobs that
                     pile up unnoticed (#17).
4. phantom-ci      — a workflow with `>= N` of the last `M` push runs on main
                     completing with `latest_check_runs_count == 0` and
                     `conclusion in {failure, null}`. The actions runner
                     started, failed, did no work. This is the shape of a
                     YAML parse error that GitHub Actions silently absorbs
                     (#27 / #28: 21 days of phantom failures, statusCheckRollup
                     empty so PR auto-merge couldn't see them).
5. missing-timeout — a workflow with `>= 1` job whose `timeout-minutes` is
                     not set. GitHub Actions defaults to 360 min/job in
                     that case, so a hung job burns the full 6-hour ceiling
                     before being killed (#35; canonical per-repo lock at
                     llm-eval-harness#62 etc.).
6. missing-concurrency — a workflow with no top-level `concurrency:` group.
                         Without one, a rapid push-on-push (rebased session
                         branch force-pushed, PR chain merged in quick
                         succession) burns one full CI run per push even
                         though the in-flight run is immediately superseded.
                         A `cancel-in-progress: true` group cuts wall time
                         by 30-60s per superseded run (#40).

Mostly stdlib (urllib.request + json). The missing-timeout and
missing-concurrency fingerprints are the two exceptions — both
lazy-import `yaml` (pyyaml) and degrade to "no findings" plus a stderr
note when pyyaml is unavailable. The other four checks remain
stdlib-only and run regardless.

Dependencies:
  - Stdlib only is enough to run paired-failure, stuck-registration,
    stale-schedule, and phantom-ci.
  - `pyyaml` is required for `missing-timeout` and `missing-concurrency`
    to do real work. Install it with `pip install pyyaml` (or `pip
    install -r scripts/requirements.txt`). Without it, the two yaml-
    dependent checks no-op silently — they return zero findings and
    write a one-line "skipping <check>: pyyaml not installed" to stderr.
    The lazy import + graceful degradation pattern is intentional: the
    script remains usable on a minimal venv for the four stdlib checks,
    and a missing pyyaml never crashes the surrounding session-runner
    Phase A bash wrapper that branches on exit code only.

Where pyyaml is guaranteed:
  - `audit-cron.yml`'s `audit` job (installed via `pip install pytest
    pyyaml` in the lock-test step; the same job runs the audit so both
    yaml checks function in scheduled cron). The pyyaml install is
    locked by `tests/test_audit_cron_workflow.py::test_pyyaml_installed`
    so it can't be dropped silently in a future workflow tweak.
  - The Phase A wrapper in `session-runner/SESSION_PROMPT.md` runs on
    the operator's local venv — see `scripts/README.md` for the
    operator setup note.

Optional `GH_TOKEN` env for higher rate limit; unauth works for public
repos with lower quota.

Exit codes:
  0  no findings (clean)
  1  one or more findings (operator should investigate)
  2  fetch or runtime error (rate-limit hit, network failure, etc.)

Spec / origin: portfolio-ops#19. Intended to run at the top of Phase A in
session-runner/SESSION_PROMPT.md as a non-blocking pre-check.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Any

REPO_OWNER = "jt-mchorse"
PORTFOLIO_REPOS = (
    "rag-production-kit",
    "agent-orchestration-platform",
    "llm-eval-harness",
    "prompt-regression-suite",
    "ai-app-integration-tests",
    "nextjs-streaming-ai-patterns",
    "python-async-llm-pipelines",
    "embedding-model-shootout",
    "chunking-strategies-lab",
    "llm-cost-optimizer",
    "vector-search-at-scale",
    "mcp-server-cookbook",
)
OPS_REPO = "portfolio-ops"
ALL_REPOS = PORTFOLIO_REPOS + (OPS_REPO,)

USER_AGENT = (
    "portfolio-audit-phase-a/1.0 (+https://github.com/jt-mchorse/portfolio-ops)"
)


def _gh_get(path: str, token: str | None) -> Any:
    """Fetch JSON from GitHub API. Raises on non-200."""
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_paired_failure(repo: str, token: str | None) -> list[dict]:
    """Flag any SHA on main that produced both success and failure runs."""
    data = _gh_get(
        f"/repos/{REPO_OWNER}/{repo}/actions/runs?event=push&branch=main&per_page=10",
        token,
    )
    runs = data.get("workflow_runs", [])
    by_sha: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        by_sha[run["head_sha"]].append(run)
    findings = []
    for sha, sha_runs in by_sha.items():
        if len(sha_runs) < 2:
            continue
        conclusions = {r["conclusion"] for r in sha_runs}
        if "success" in conclusions and "failure" in conclusions:
            findings.append(
                {
                    "kind": "paired-failure",
                    "repo": repo,
                    "sha": sha[:8],
                    "runs": [
                        {
                            "name": r["name"],
                            "path": r["path"],
                            "conclusion": r["conclusion"],
                        }
                        for r in sha_runs
                    ],
                }
            )
    return findings


def check_stuck_registration(repo: str, token: str | None) -> list[dict]:
    """Flag active workflows whose registered name is the path (parser fallback)."""
    data = _gh_get(f"/repos/{REPO_OWNER}/{repo}/actions/workflows", token)
    findings = []
    for wf in data.get("workflows", []):
        if wf.get("state") != "active":
            continue
        name = wf.get("name", "")
        path = wf.get("path", "")
        if name.startswith(".github/workflows/") or name == path:
            findings.append(
                {
                    "kind": "stuck-registration",
                    "repo": repo,
                    "workflow_id": wf["id"],
                    "registered_name": name,
                    "path": path,
                }
            )
    return findings


def check_stale_schedule(
    repo: str, token: str | None, threshold: int = 3
) -> list[dict]:
    """Flag scheduled workflows with >= threshold consecutive failures and no successes."""
    data = _gh_get(
        f"/repos/{REPO_OWNER}/{repo}/actions/runs?event=schedule&per_page=10",
        token,
    )
    runs = data.get("workflow_runs", [])
    # Group by workflow path.
    by_path: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        by_path[run["path"]].append(run)
    findings = []
    for path, path_runs in by_path.items():
        # Runs are in descending chronological order from the API.
        consecutive_failures = 0
        for run in path_runs:
            if run["conclusion"] == "failure":
                consecutive_failures += 1
            else:
                break
        if consecutive_failures >= threshold:
            findings.append(
                {
                    "kind": "stale-schedule",
                    "repo": repo,
                    "workflow_path": path,
                    "consecutive_failures": consecutive_failures,
                    "name": path_runs[0]["name"],
                }
            )
    return findings


def check_phantom_ci(
    repo: str,
    token: str | None,
    threshold: int = 3,
    window: int = 5,
) -> list[dict]:
    """Flag workflows whose last `window` push runs on main are `>= threshold` phantom.

    A "phantom" run is one with `latest_check_runs_count == 0` (no jobs were
    actually scheduled) AND `conclusion in {failure, null}`. That's the actions
    runner reporting "I started, I failed, I did no work" — pathological by
    definition, and the exact shape that hid #27's 21-day YAML parse outage.

    A single phantom run is not enough signal (transient cancels can look the
    same). The pattern signal is `>= threshold` phantoms among the most recent
    `window` push runs to main for a given workflow.
    """
    # Pull active workflow ids so post-fix historical phantom runs from
    # disabled/deleted workflows don't keep crying wolf after the bug is gone.
    workflows_data = _gh_get(f"/repos/{REPO_OWNER}/{repo}/actions/workflows", token)
    active_ids = {
        wf["id"]
        for wf in workflows_data.get("workflows", [])
        if wf.get("state") == "active"
    }
    data = _gh_get(
        f"/repos/{REPO_OWNER}/{repo}/actions/runs?event=push&branch=main&per_page=20",
        token,
    )
    runs = data.get("workflow_runs", [])
    # Group by workflow id, take the last `window` per workflow.
    by_wf: dict[int, list[dict]] = defaultdict(list)
    for run in runs:
        wf_id = run.get("workflow_id")
        if wf_id is None or wf_id not in active_ids:
            continue
        if len(by_wf[wf_id]) < window:
            by_wf[wf_id].append(run)
    findings = []
    for wf_id, wf_runs in by_wf.items():
        phantoms = [
            r
            for r in wf_runs
            if r.get("conclusion") in (None, "failure") and _phantom_run(r, token, repo)
        ]
        if len(phantoms) >= threshold:
            findings.append(
                {
                    "kind": "phantom-ci",
                    "repo": repo,
                    "workflow_id": wf_id,
                    "workflow_name": wf_runs[0].get("name", ""),
                    "phantom_count": len(phantoms),
                    "window": len(wf_runs),
                    "sample_shas": [r["head_sha"][:8] for r in phantoms[:3]],
                }
            )
    return findings


def _phantom_run(run: dict, token: str | None, repo: str) -> bool:
    """Return True if this run has no jobs (zero-job phantom failure).

    Uses the run-attached `latest_check_runs_count` when the API surfaces it;
    falls back to a single `/jobs` call when the field is missing (older
    list-runs payloads omit it).
    """
    count = run.get("latest_check_runs_count")
    if count is not None:
        return count == 0
    try:
        jobs_data = _gh_get(
            f"/repos/{REPO_OWNER}/{repo}/actions/runs/{run['id']}/jobs",
            token,
        )
    except urllib.error.HTTPError:
        # If we cannot read jobs, assume not phantom (avoid false positives).
        return False
    return jobs_data.get("total_count", 0) == 0


def check_missing_timeout(repo: str, token: str | None) -> list[dict]:
    """Flag active workflows with one or more jobs missing `timeout-minutes`.

    GitHub Actions defaults to 360 min/job when `timeout-minutes` is unset.
    A hung job (network stall, infinite test loop, stuck API call) burns the
    full 6-hour ceiling before the runner kills it — quota the operator pays
    for regardless of output.

    Per-repo lock tests (e.g., `tests/test_workflows_timeout_minutes.py`
    seeded by llm-eval-harness#62) catch this on a PR-test basis once the
    lock has been propagated. This fingerprint is the cross-repo post-deploy
    net: every repo whose workflows lack the guard gets surfaced until the
    lock lands.

    pyyaml is lazy-imported here and the check returns an empty findings
    list (plus a stderr note) when pyyaml is unavailable, so the other four
    checks remain stdlib-only and the script never hard-fails on a missing
    import.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        print(
            f"skipping missing-timeout for {repo}: pyyaml not installed",
            file=sys.stderr,
        )
        return []

    workflows_data = _gh_get(f"/repos/{REPO_OWNER}/{repo}/actions/workflows", token)
    findings: list[dict] = []
    for wf in workflows_data.get("workflows", []):
        if wf.get("state") != "active":
            continue
        wf_path = wf.get("path", "")
        wf_name = wf.get("name", "")
        try:
            content_data = _gh_get(
                f"/repos/{REPO_OWNER}/{repo}/contents/{wf_path}",
                token,
            )
        except urllib.error.HTTPError:
            # If we can't read the file, skip rather than false-positive.
            continue
        encoded = content_data.get("content", "")
        if not encoded:
            continue
        import base64

        try:
            text = base64.b64decode(encoded).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            # Unparseable YAML is the phantom-ci/parseability fingerprint's job.
            continue
        if not isinstance(parsed, dict):
            continue
        jobs = parsed.get("jobs")
        if not isinstance(jobs, dict):
            continue
        missing: list[str] = []
        for job_id, body in jobs.items():
            if not isinstance(body, dict):
                continue
            if "timeout-minutes" not in body:
                missing.append(str(job_id))
        if missing:
            findings.append(
                {
                    "kind": "missing-timeout",
                    "repo": repo,
                    "workflow_name": wf_name,
                    "workflow_path": wf_path,
                    "jobs_missing": sorted(missing),
                }
            )
    return findings


def check_missing_concurrency(repo: str, token: str | None) -> list[dict]:
    """Flag active workflows with no top-level `concurrency:` group.

    Without a concurrency group, a rapid push-on-push (operator force-pushing
    a session branch after a rebase, or merging a PR chain in quick
    succession) burns one full CI run per push — even though the in-flight
    run is immediately superseded. A `concurrency: { group: ..., cancel-in-progress: true }`
    block saves 30-60s per superseded run and prevents wasted CI minutes.

    Per-repo lock tests (`tests/test_workflows_concurrency.py`, future
    propagation) catch this on a PR-test basis once each repo's lock has
    been added. This fingerprint is the cross-repo post-deploy net:
    every workflow whose top level lacks `concurrency:` gets surfaced
    until the lock lands.

    pyyaml is lazy-imported here and the check returns an empty findings
    list (plus a stderr note) when pyyaml is unavailable, matching the
    same degradation pattern as `check_missing_timeout`.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        print(
            f"skipping missing-concurrency for {repo}: pyyaml not installed",
            file=sys.stderr,
        )
        return []

    workflows_data = _gh_get(f"/repos/{REPO_OWNER}/{repo}/actions/workflows", token)
    findings: list[dict] = []
    for wf in workflows_data.get("workflows", []):
        if wf.get("state") != "active":
            continue
        wf_path = wf.get("path", "")
        wf_name = wf.get("name", "")
        try:
            content_data = _gh_get(
                f"/repos/{REPO_OWNER}/{repo}/contents/{wf_path}",
                token,
            )
        except urllib.error.HTTPError:
            # If we can't read the file, skip rather than false-positive.
            continue
        encoded = content_data.get("content", "")
        if not encoded:
            continue
        import base64

        try:
            text = base64.b64decode(encoded).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            # Unparseable YAML is the phantom-ci/parseability fingerprint's job.
            continue
        if not isinstance(parsed, dict):
            continue
        if "concurrency" not in parsed:
            findings.append(
                {
                    "kind": "missing-concurrency",
                    "repo": repo,
                    "workflow_name": wf_name,
                    "workflow_path": wf_path,
                }
            )
    return findings


def audit_repo(repo: str, token: str | None) -> list[dict]:
    findings: list[dict] = []
    findings.extend(check_paired_failure(repo, token))
    findings.extend(check_stuck_registration(repo, token))
    findings.extend(check_stale_schedule(repo, token))
    findings.extend(check_phantom_ci(repo, token))
    findings.extend(check_missing_timeout(repo, token))
    findings.extend(check_missing_concurrency(repo, token))
    return findings


def format_finding(f: dict) -> str:
    kind = f["kind"]
    repo = f["repo"]
    if kind == "paired-failure":
        run_summaries = ", ".join(f"{r['name']}={r['conclusion']}" for r in f["runs"])
        return f"  [{kind}] {repo}@{f['sha']}: {run_summaries}"
    if kind == "stuck-registration":
        return (
            f"  [{kind}] {repo}: workflow id {f['workflow_id']} "
            f"registered as {f['registered_name']!r} (path: {f['path']})"
        )
    if kind == "stale-schedule":
        return (
            f"  [{kind}] {repo}: {f['name']} ({f['workflow_path']}) "
            f"has {f['consecutive_failures']} consecutive failures"
        )
    if kind == "phantom-ci":
        samples = ", ".join(f["sample_shas"])
        return (
            f"  [{kind}] {repo}: workflow {f['workflow_name']!r} (id {f['workflow_id']}) "
            f"has {f['phantom_count']}/{f['window']} zero-job push runs on main "
            f"(sample SHAs: {samples})"
        )
    if kind == "missing-timeout":
        jobs = ", ".join(f["jobs_missing"])
        return (
            f"  [{kind}] {repo}: workflow {f['workflow_name']!r} "
            f"({f['workflow_path']}) has {len(f['jobs_missing'])} job(s) without "
            f"`timeout-minutes`: {jobs}"
        )
    if kind == "missing-concurrency":
        return (
            f"  [{kind}] {repo}: workflow {f['workflow_name']!r} "
            f"({f['workflow_path']}) has no top-level `concurrency:` group"
        )
    return f"  [{kind}] {repo}: {f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        action="append",
        help="Limit to a specific repo. Repeat for multiple. Default: all 13.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Consecutive scheduled failures to flag as stale (default: 3).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit findings as JSON to stdout (one object per line).",
    )
    args = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repos = tuple(args.repo) if args.repo else ALL_REPOS

    all_findings: list[dict] = []
    for repo in repos:
        try:
            all_findings.extend(audit_repo(repo, token))
        except urllib.error.HTTPError as exc:
            print(
                f"error: HTTP {exc.code} fetching for {repo}: {exc.reason}",
                file=sys.stderr,
            )
            return 2
        except urllib.error.URLError as exc:
            print(f"error: network failure for {repo}: {exc.reason}", file=sys.stderr)
            return 2

    if not all_findings:
        print(f"clean: no findings across {len(repos)} repo(s)")
        return 0

    if args.json:
        for f in all_findings:
            print(json.dumps(f, sort_keys=True))
    else:
        kind_counts: dict[str, int] = defaultdict(int)
        for f in all_findings:
            kind_counts[f["kind"]] += 1
        print(f"findings: {len(all_findings)} across {len(repos)} repo(s)")
        for kind, count in sorted(kind_counts.items()):
            print(f"  - {kind}: {count}")
        print()
        for f in all_findings:
            print(format_finding(f))
    return 1


if __name__ == "__main__":
    sys.exit(main())
