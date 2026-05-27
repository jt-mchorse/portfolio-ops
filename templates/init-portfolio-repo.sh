#!/usr/bin/env bash
# init-portfolio-repo.sh — scaffold a new repo under jt-mchorse/ with all conventions in place.
#
# Usage: ./init-portfolio-repo.sh <repo-name> "<one-sentence-purpose>"
# Example: ./init-portfolio-repo.sh llm-eval-harness "Reusable LLM eval framework with CI integration"
#
# Requires: gh CLI authenticated as jt-mchorse, git configured with jmchorse.tech@gmail.com.

set -euo pipefail

REPO="${1:?repo name required}"
PURPOSE="${2:?one-sentence purpose required}"
OWNER="jt-mchorse"
DATE="$(date -u +%Y-%m-%d)"

echo ">>> Verifying git identity"
GIT_NAME="$(git config --global user.name || echo '')"
GIT_EMAIL="$(git config --global user.email || echo '')"
if [[ "$GIT_NAME" != "jt-mchorse" || "$GIT_EMAIL" != "jmchorse.tech@gmail.com" ]]; then
  echo "ERROR: git identity must be jt-mchorse / jmchorse.tech@gmail.com"
  echo "Run: git config --global user.name 'jt-mchorse' && git config --global user.email 'jmchorse.tech@gmail.com'"
  exit 1
fi

echo ">>> Creating repo $OWNER/$REPO"
gh repo create "$OWNER/$REPO" --public --description "$PURPOSE" --confirm

mkdir -p "$REPO" && cd "$REPO"
git init -b main
git remote add origin "https://github.com/$OWNER/$REPO.git"

echo ">>> Writing scaffold"

mkdir -p .github/ISSUE_TEMPLATE .github/workflows .skills/portfolio-memory .skills/portfolio-session MEMORY docs

# Skills (copied from portfolio-ops/skills)
cp -r ../portfolio-ops/skills/portfolio-memory/SKILL.md .skills/portfolio-memory/
cp -r ../portfolio-ops/skills/portfolio-session/SKILL.md .skills/portfolio-session/

# Issue templates
cp ../portfolio-ops/issue_templates/*.yml .github/ISSUE_TEMPLATE/

# CI template
cp ../portfolio-ops/workflows/ci-template.yml .github/workflows/ci.yml

# License (MIT)
cat > LICENSE <<EOF
MIT License

Copyright (c) $(date +%Y) JT McHorse

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
EOF

# README skeleton
cat > README.md <<EOF
# $REPO
> $PURPOSE

![CI](https://github.com/$OWNER/$REPO/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## What this is
*[2–3 paragraphs framing the problem and the approach. Filled by repo's first feature work.]*

## Architecture
*See [docs/architecture.md](docs/architecture.md). Diagram pending issue #1.*

## Quickstart
*Pending — see open issues.*

## Benchmarks / Results
*Pending — see [docs/benchmarks.md](docs/benchmarks.md).*

## Demo
*60-second demo pending.*

## Why these decisions
See [MEMORY/core_decisions_human.md](MEMORY/core_decisions_human.md).

## License
MIT
EOF

# CONTRIBUTING
cat > CONTRIBUTING.md <<EOF
# Contributing

This repo is part of JT McHorse's AI/ML engineering portfolio. It follows the protocol in the [portfolio handoff](https://github.com/$OWNER/portfolio-ops/blob/main/COWORK_HANDOFF.md).

- Sessions are issue-driven; no work without a tracking issue.
- Session caps per D-008: **180 min DAY / 360 min NIGHT** with a multi-issue loop. Mandatory memory updates every session (see \`.skills/portfolio-session/\`).
- All changes via PR. Per D-004, non-draft PRs with green CI are auto-merged in Phase A of the next scheduled session; drafts are never auto-merged.
EOF

# .gitignore
cat > .gitignore <<EOF
.env
.env.local
*.pyc
__pycache__/
node_modules/
.next/
dist/
build/
.DS_Store
.venv/
*.log
logs/
.pytest_cache/
EOF

# MEMORY scaffolding
cat > MEMORY/full_history_ai.md <<EOF
# Session History (AI-readable, append-only)

Schema: see .skills/portfolio-memory/SKILL.md
EOF

cat > MEMORY/full_history_human.md <<EOF
# Session History (human-readable)

Chronological log of work sessions. Most recent first below the divider.

---
EOF

cat > MEMORY/core_decisions_ai.md <<EOF
# Core Decisions (AI-readable, YAML, append-only)
# Schema: see .skills/portfolio-memory/SKILL.md

- id: D-001
  date: $DATE
  decision: scope_per_portfolio_handoff_section_2
  rationale: locked_scope_prevents_drift
  alternatives_rejected: []
  reversibility: expensive
  related_issues: []
  superseded_by: null
EOF

cat > MEMORY/core_decisions_human.md <<EOF
# Core Decisions

Strategic decisions for this repo, with reasoning. Append-only — superseded decisions are marked, not removed.

## D-001 — Scope locked to portfolio handoff §2 ($DATE)
**Decision:** Scope of this repo is fixed by the portfolio handoff document, section 2.

**Why:** The handoff spec was deliberated; ad-hoc scope expansion within a session is the failure mode this prevents.

**Alternatives considered:** None — this is a baseline.

**Reversibility:** Expensive. Scope changes require a deliberate revisit and a new decision entry.

**Related issues:** —
EOF

# docs
cat > docs/architecture.md <<EOF
# Architecture

*Pending issue #1. Diagram + 2-page write-up of components and data flow.*
EOF

cat > docs/benchmarks.md <<EOF
# Benchmarks

*Pending. All numbers in this file are real measurements with reproducible scripts. Never fabricated.*
EOF

# Initial commit
git add .
git commit -m "chore: initial scaffold per portfolio handoff"
git push -u origin main

# Apply standard labels
echo ">>> Applying standard labels"
LABELS=(
  "trending:#0E8A16"
  "decision-revisit:#D93F0B"
  "wontfix-stale:#CCCCCC"
  "phase:building:#FBCA04"
  "phase:shipped:#0E8A16"
  "phase:improving:#1D76DB"
  "category:rag:#5319E7"
  "category:agents:#5319E7"
  "category:evals:#5319E7"
  "category:ml-ops:#5319E7"
  "category:full-stack:#5319E7"
  "category:performance:#5319E7"
  "category:research:#5319E7"
  "priority:high:#B60205"
  "priority:med:#FBCA04"
  "priority:low:#0E8A16"
)
for entry in "${LABELS[@]}"; do
  name="${entry%%:*}"
  color="${entry##*:#}"
  gh label create "$name" --color "$color" --repo "$OWNER/$REPO" --force
done

echo ">>> Setting branch protection on main"
gh api -X PUT "repos/$OWNER/$REPO/branches/main/protection" \
  -F required_status_checks='{"strict":true,"contexts":[]}' \
  -F enforce_admins=false \
  -F required_pull_request_reviews='{"required_approving_review_count":0}' \
  -F restrictions=null \
  || echo "(branch protection skipped — may require Pro/Org)"

echo ">>> Done. Repo ready: https://github.com/$OWNER/$REPO"
echo ">>> Next: file initial issues from portfolio handoff §2 spec for $REPO."
