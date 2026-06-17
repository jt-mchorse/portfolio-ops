---
name: portfolio-session
description: Use this skill at the start and end of every Cowork session that works on any portfolio repo (jt-mchorse/rag-production-kit, agent-orchestration-platform, llm-eval-harness, prompt-regression-suite, ai-app-integration-tests, nextjs-streaming-ai-patterns, python-async-llm-pipelines, embedding-model-shootout, chunking-strategies-lab, llm-cost-optimizer, vector-search-at-scale, mcp-server-cookbook, portfolio-ops). It enforces the four-phase session structure (start, plan, execute, close), the D-008 time-of-day cap (180 min DAY / 360 min NIGHT, multi-issue loop) with a D-006 15-min minimum per issue, and the discipline of issue-driven work. The runner prepends a `RUNTIME OVERRIDE` header with the active cap; obey that over any number quoted here. Pair with portfolio-memory skill for a complete session.
---

# Portfolio Session Protocol

Every session for every portfolio repo follows the same four phases. Per **D-008 (2026-05-14)** the time budget is time-of-day-aware with a multi-issue loop: **180 min (DAY) / 360 min (NIGHT)**. Per **D-006 (2026-05-14)** each issue gets a **15-min minimum** — short sessions that ship only a 5-line tweak are a failure mode. Stop ≥15 min before the cap to land a clean checkpoint, then end. The runner prepends a `RUNTIME OVERRIDE` header with the active cap for each invocation; obey the override over any number quoted in this skill. Bootstrap sessions are exempt and must be tagged `bootstrap` in memory.

## Phase 1 — Start (5 min)

```bash
cd <repo>
git fetch && git checkout main && git pull
git checkout -b session/$(date -u +%Y-%m-%d)-issue-NN
```

Then in this exact order:
1. Load `portfolio-memory` skill, perform the read step (last 5 session entries, full decisions file).
2. List open issues: `gh issue list --state open --label priority:high`.
3. Pick the target issue. Read its full body and comments.
4. Verify alignment: does this issue contradict any non-superseded core decision? If yes, comment on the issue (`This conflicts with D-NNN; recommend revisit before action`) and stop. Pick a different issue or end the session.

## Phase 2 — Plan (5 min)

Post a comment on the target issue with this exact structure:

```markdown
**Session plan** (~50 min)

**Will do:**
- <bullet>
- <bullet>

**Will defer:**
- <bullet> — reason

**Decisions in flight:** <none, or brief list referencing existing D-NNN if relevant>
```

Do not start coding until the plan comment is posted. The plan is the contract for the session.

## Phase 3 — Execute (45 min)

Work the plan. Discipline rules:

- **Stay on the issue.** If a new improvement opportunity is spotted, file it as a fresh issue with a one-line body and label `priority:low`. Do not start working it.
- **Decision triage.** If a decision emerges:
  - *Reversible & small:* make it, note in session log at close.
  - *Expensive or one-way:* stop. Write up the tradeoff in the issue. Assign to JT (or `@`-mention). Pick a different issue or end the session.
- **Test as you go.** No "I'll add tests later" commits. If a change is testable, it ships with a test.
- **Commit small.** Multiple commits per session is fine. One commit per session is fine. Zero commits is a failed session (write up why in memory).

## Phase 4 — Close (5 min)

```bash
git add .
git commit -m "<conventional commit message>"
git push -u origin session/$(date -u +%Y-%m-%d)-issue-NN
gh pr create --draft --title "..." --body "..."   # or update existing
```

Then:
1. **Comment on the issue** with progress:
   ```markdown
   **Session close** (~<N> min)

   **Shipped:**
   - <bullet>

   **Remaining for this issue:**
   - <bullet>

   **Branch:** `session/...` · **PR:** #NN

   **% complete:** <N>%
   ```

2. **Update memory** (use `portfolio-memory` skill's session-end protocol).

3. **Memory commit** (separate from code commit):
   ```bash
   git add MEMORY/
   git commit -m "memory: session $(date -u +%Y-%m-%d) <repo>"
   git push
   ```

4. If the PR is ready for review (issue is fully complete), mark it as ready: `gh pr ready <number>`. Otherwise leave as draft for the next session.

## Hard rules

- **Never push to main.** Feature branches and PRs only.
- **Never merge without JT review.** Exception: memory-only commits and obvious docs typos.
- **Never close an issue** without either a merged PR or a written explanation comment.
- **Never exceed the runner's `RUNTIME OVERRIDE` cap** (per D-008: 180 min DAY / 360 min NIGHT baseline, multi-issue loop). Stop ≥15 min before the cap to land a clean checkpoint. The next session resumes.
- **Never plan from memory you didn't read.** If you skipped Phase 1's memory read, you are not in a valid session.

## Selecting which repo to work this session

**Priority tier (D-009).** Five repos are worked *more often* than the rest — `llm-cost-optimizer`, `llm-eval-harness`, `rag-production-kit`, `chunking-strategies-lab`, `nextjs-streaming-ai-patterns`. They get a tighter freshness floor and win every tie-break. The other 8 repos are deprioritized, not dropped — they still get worked on the normal cadence. The canonical, authoritative selection rules with exact hour thresholds live in `session-runner/SESSION_PROMPT.md` Phase A step 5; the list below is the summary.

When Cowork runs on a schedule and needs to pick a repo:

1. Check `portfolio-ops/MEMORY/full_history_ai.md` for last-touched timestamps per repo.
2. Find any **priority-tier** repo not touched in 18+ hours. Pick the earliest in build sequence among those.
3. Else find any repo not touched in 7+ days. Pick it. (Enforces the weekly-touch floor.) If a priority-tier repo also qualifies, take it first.
4. If all repos are fresh, pick the one with the most `priority:high` open issues.
5. If still tied, prefer a priority-tier repo, then the earlier repo in the build sequence (handoff §8).

## Multi-repo session days

Per D-008 a single session already runs a multi-issue, multi-repo loop within its 180/360-min cap — looping back to repo/issue selection after each Phase C close, until within 15 min of the cap. Across days, scheduled DAY and NIGHT sessions chain through this pattern; each session start re-reads memory and does not carry transient state from the prior one.

## Failure modes to avoid

- Starting code before posting the plan comment.
- Skipping memory because "the session was short."
- Bundling memory updates into code commits.
- Letting one session sprawl past the `RUNTIME OVERRIDE` cap "to finish this last thing" — per D-008 stop ≥15 min before the cap, checkpoint cleanly, and end.
- Closing issues without linked PRs.
- Working an issue that conflicts with a core decision without flagging it first.
