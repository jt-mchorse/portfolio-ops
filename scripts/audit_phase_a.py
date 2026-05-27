#!/usr/bin/env python3
"""Phase A operational-health audit.

Catches three silent-rot fingerprints across the 13 portfolio repos:

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

Stdlib-only (urllib.request + json). Optional `GH_TOKEN` env for higher rate
limit; unauth works for public repos with lower quota.

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
    "portfolio-audit-phase-a/1.0 "
    "(+https://github.com/jt-mchorse/portfolio-ops)"
)


def _gh_get(path: str, token: str | None) -> Any:
    """Fetch JSON from GitHub API. Raises on non-200."""
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
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


def check_stale_schedule(repo: str, token: str | None, threshold: int = 3) -> list[dict]:
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


def audit_repo(repo: str, token: str | None) -> list[dict]:
    findings: list[dict] = []
    findings.extend(check_paired_failure(repo, token))
    findings.extend(check_stuck_registration(repo, token))
    findings.extend(check_stale_schedule(repo, token))
    return findings


def format_finding(f: dict) -> str:
    kind = f["kind"]
    repo = f["repo"]
    if kind == "paired-failure":
        run_summaries = ", ".join(
            f"{r['name']}={r['conclusion']}" for r in f["runs"]
        )
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
            print(f"error: HTTP {exc.code} fetching for {repo}: {exc.reason}", file=sys.stderr)
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
