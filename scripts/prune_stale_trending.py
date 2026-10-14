#!/usr/bin/env python3
"""Prune stale `trending`-labeled issues across the 12 portfolio repos.

Rules (from skills/portfolio-trending/SKILL.md):
- No engagement in 30 days → close with label `wontfix-stale`.
- "Engagement" = any comment, or any label change in the past 30 days,
  or any commit referencing the issue (#NNN in commit message — checked
  best-effort via the timeline API).
- Don't touch issues where someone (other than the bot/PR template) has
  commented in the last 30 days.

Required env:
  GH_TOKEN              fine-scoped PAT with issues:write on the 12 repos.

Exit codes:
  0   ran cleanly
  1   missing env, or any repo's listing or any issue's close was refused
      (every other repo and issue is still attempted first)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from typing import Any

REPO_OWNER = "jt-mchorse"
STALE_DAYS = 30
USER_AGENT = "portfolio-trending-prune/1.0"

ALL_REPOS = [
    "rag-production-kit", "agent-orchestration-platform", "llm-eval-harness",
    "prompt-regression-suite", "ai-app-integration-tests", "nextjs-streaming-ai-patterns",
    "python-async-llm-pipelines", "embedding-model-shootout", "chunking-strategies-lab",
    "llm-cost-optimizer", "vector-search-at-scale", "mcp-server-cookbook",
]


def gh(method: str, path: str, body: Any = None) -> tuple[int, Any]:
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN not set")
    url = f"https://api.github.com{path}" if not path.startswith("http") else path
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    })
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode() or "null"
            return resp.status, json.loads(payload)
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()
        try:
            return e.code, json.loads(body_txt)
        except Exception:
            return e.code, {"raw": body_txt}


class GitHubCallFailed(RuntimeError):
    """`gh()` reports a status rather than raising, so every caller must check
    it. A 401/403 that is not checked reads as "nothing to do" (#92)."""


def list_trending_issues(repo: str) -> list[dict]:
    issues = []
    page = 1
    while True:
        c, b = gh("GET", f"/repos/{REPO_OWNER}/{repo}/issues?state=open&labels=trending&per_page=100&page={page}")
        if c != 200 or not isinstance(b, list):
            raise GitHubCallFailed(f"listing {repo} page {page} returned {c}: {b}")
        if not b:
            break
        for issue in b:
            if "pull_request" not in issue:
                issues.append(issue)
        if len(b) < 100:
            break
        page += 1
    return issues


def is_stale(issue: dict) -> bool:
    updated = dt.datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))
    age_days = (dt.datetime.now(dt.timezone.utc) - updated).days
    return age_days >= STALE_DAYS


def close_stale(repo: str, issue: dict) -> None:
    """Close first: if the close is refused, nothing else has been written, so
    the issue is not left open under a `wontfix-stale` label and an
    "Auto-closed" comment (#92). Raises `GitHubCallFailed` on a refused close."""
    n = issue["number"]
    c, b = gh("PATCH", f"/repos/{REPO_OWNER}/{repo}/issues/{n}", {
        "state": "closed",
        "state_reason": "not_planned",
    })
    if c != 200:
        raise GitHubCallFailed(f"close returned {c}: {b}")
    print(f"[closed] {repo}#{n}: {issue['title'][:80]}")
    # The issue is closed; a refused label or comment is worth a warning, not a failure.
    c, b = gh("POST", f"/repos/{REPO_OWNER}/{repo}/issues/{n}/labels", {"labels": ["wontfix-stale"]})
    if c != 200:
        print(f"[warn] {repo}#{n} label returned {c}: {b}", file=sys.stderr)
    c, b = gh("POST", f"/repos/{REPO_OWNER}/{repo}/issues/{n}/comments", {
        "body": f"Auto-closed by `prune_stale_trending.py`: no engagement in {STALE_DAYS} days. Reopen if still relevant.",
    })
    if c != 201:
        print(f"[warn] {repo}#{n} comment returned {c}: {b}", file=sys.stderr)


def main() -> int:
    if not os.environ.get("GH_TOKEN"):
        print("GH_TOKEN not set; exiting 1", file=sys.stderr)
        return 1

    closed_total = 0
    failures = 0
    for repo in ALL_REPOS:
        try:
            issues = list_trending_issues(repo)
        except GitHubCallFailed as e:
            print(f"[error] {e}", file=sys.stderr)
            failures += 1
            continue
        stale = [i for i in issues if is_stale(i)]
        if not stale:
            continue
        print(f"[{repo}] {len(stale)} stale of {len(issues)} open trending")
        for issue in stale:
            try:
                close_stale(repo, issue)
                closed_total += 1
            except Exception as e:
                print(f"[error] {repo}#{issue['number']} close failed: {e}", file=sys.stderr)
                failures += 1

    print(f"done — closed {closed_total} stale trending issues")
    if failures:
        print(f"{failures} listing/close call(s) failed; exiting 1", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
