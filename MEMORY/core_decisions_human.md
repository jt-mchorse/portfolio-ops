# Core Decisions

Strategic decisions for this repo, with reasoning. Append-only — superseded decisions are marked, not removed.

## D-001 — Scope locked to portfolio handoff §2 (2026-05-10)
**Decision:** Scope of this repo is fixed by the portfolio handoff document, section 2.

**Why:** The handoff spec was deliberated; ad-hoc scope expansion within a session is the failure mode this prevents.

**Alternatives considered:** None — this is a baseline.

**Reversibility:** Expensive. Scope changes require a deliberate revisit and a new decision entry.

**Related issues:** —

## D-002 — Trending scripts stubbed at bootstrap [SUPERSEDED BY D-003], implemented in session one (2026-05-10)
**Decision:** `scripts/trending_scan.py` and `scripts/prune_stale_trending.py` are committed as stubs that exit 1; the real implementation is filed as portfolio-ops issue #1 and #2.

**Why:** Handoff §10 is explicit — "do not invent benchmark numbers" and the same principle applies to plumbing. A workflow that silently no-ops would imply the trending system works when it doesn't. A stub that exits 1 + a README note is honest. Bootstrap exists to make the system reviewable, not pretend it's done.

**Alternatives considered:**
- Implement the full scanner during bootstrap — rejected because it's real engineering work that violates the bootstrap-vs-session boundary; would also lock in design choices without thinking.
- Omit the workflows entirely — rejected because the workflow YAML is part of the spec the system was reviewed on; presence + honest stub is better than silent absence.

**Reversibility:** Cheap. The first two issues replace the stubs.

**Related issues:** —

## D-003 — Real trending scripts using stdlib only (2026-05-11)
**Decision:** `scripts/trending_scan.py` and `scripts/prune_stale_trending.py` are committed with real implementations using only the Python standard library. Supersedes D-002 (which left them as stubs).

**Why:** Following bootstrap, JT explicitly asked to complete the setup. The choice between adding external deps (anthropic SDK, feedparser, beautifulsoup4) and using stdlib came down to dependency hygiene — for a script that runs in GitHub Actions on a schedule, fewer moving parts means fewer failure modes from upstream package changes. The Anthropic Messages API is a simple HTTPS endpoint; urllib calls it directly with the same response shape.

**Alternatives considered:**
- Keep the D-002 stubs — rejected because the user request was to complete, not defer further.
- Use the official Anthropic Python SDK + feedparser + bs4 — rejected because we don't need them for this fidelity. A future session can swap in if regex parsing proves brittle.

**Reversibility:** Cheap. Either component can be swapped to SDKs in a follow-up session without API surface changes for callers.

**Related issues:** —

*D-002 is marked superseded by D-003 in `core_decisions_ai.md`.*

## D-004 — Scheduled sessions review and merge ready PRs (2026-05-13)
**Decision:** Each scheduled session begins with a Phase A pass that lists every non-draft PR across the 12 repos and merges any with green CI, no merge conflicts, and a sensible diff. Drafts remain protected; only `isDraft=false` PRs are eligible. Overrides handoff §10's blanket no-auto-merge.

**Why:** JT explicitly requested it for velocity. The original §10 rule made every PR JT's bottleneck. The compromise: drafts (mid-flight session work) still require manual ready-marking before they can be merged; turning a draft into ready remains a deliberate signal from the session that finished it.

**Alternatives considered:**
- Keep full human-in-loop — rejected at JT's direction.
- Auto-merge ALL PRs including drafts — rejected because drafts represent unfinished work; that protection is worth keeping.

**Reversibility:** Cheap. Remove the Phase A merge step from SESSION_PROMPT.md.

**Related issues:** —

## D-005 — Execution via Claude Code on local Mac, not Cowork sandbox (2026-05-13)
**Decision:** The scheduled portfolio session no longer runs in Cowork's sandboxed bash. The Cowork task uses osascript to open Terminal.app on JT's Mac, which runs `run-session.sh`, which invokes `claude --print --dangerously-skip-permissions` with the canonical SESSION_PROMPT.md. Cowork remains the scheduler; Claude Code is the executor.

**Why:** Cowork's bash is a Linux sandbox VM with no access to JT's gh CLI auth, env vars, or installed tools. JT explicitly asked for use of granted Mac permissions. Running via Claude Code on the host gets us: native gh auth, real shell, full filesystem, all of JT's installed tooling.

**Alternatives considered:**
- Stay in Cowork sandbox with a PAT baked into the task config — rejected as a worse security and ergonomics trade than just using the Mac directly.
- Move scheduling to Claude Code too — rejected because Claude Code has no scheduler primitive; we'd need cron / launchd, which adds machine-state coupling.

**Reversibility:** Cheap. Rewrite the Cowork task prompt to run in the sandbox again.

**Related issues:** —

## D-006 — 15-min minimum per issue (2026-05-13)
**Decision:** A session must spend at least 15 minutes per issue it touches. Sessions that ship only a 5-line tweak and end early are a failure mode; when planned work finishes inside 15 minutes the session picks the next-highest-priority unblocked issue in the same repo and keeps going. Live since `session-runner/SESSION_PROMPT.md` commit 7690999 (2026-05-13); retroactively captured here 2026-05-27 via issue #5.

**Why:** A handful of early sessions burned an entire turn loading context (handoff + MEMORY + PR pass) and then shipped a 5-line edit. The per-session fixed cost is too high to amortize over that little work. A minimum floor forces the session to either commit to a substantive issue or keep going to the next one.

**Alternatives considered:**
- No minimum, let short sessions ship — rejected because the cost asymmetry stayed broken.
- Longer minimum (30 min) — rejected as too coarse; some genuinely small but valuable polish work would be precluded.

**Reversibility:** Cheap — edit the floor number in SESSION_PROMPT.md.

**Related issues:** #5 (retroactive capture).

## D-007 — Fall-through to next repo when chosen repo is one-way-blocked (2026-05-13)
**Decision:** When the chosen repo's top unblocked priority:high issues are all one-way decisions needing JT input, the session does not bail. Instead it leaves a one-line breadcrumb on the blocking issue and falls through to the next-best repo per the selection rules. Up to 3 fall-throughs per session before giving up. Live since `session-runner/SESSION_PROMPT.md` commit 4670bd0 (2026-05-13); retroactively captured here 2026-05-27 via issue #5.

**Why:** Three consecutive scheduled runs (05-11/12/13) bailed on `agent-orchestration-platform` because its issue #1 was a one-way decision blocking everything else. JT was losing a full session every time. The fix lets the session do productive work elsewhere while still surfacing the blocker for JT's review.

**Alternatives considered:**
- End the session when blocked — rejected; wastes the scheduled run.
- Require JT intervention every time — rejected; defeats the autonomous-session premise.

**Reversibility:** Cheap — remove the fall-through clause from SESSION_PROMPT.md selection rules.

**Related issues:** #5 (retroactive capture).

## D-008 — Time-of-day session caps + multi-issue loop (2026-05-14)
**Decision:** Day sessions (runner starts 06:00-18:00 local) cap at 180 min; night sessions cap at 360 min. The runner detects the window and prepends a RUNTIME OVERRIDE header to the prompt. A run is now an explicit multi-issue, multi-repo loop — after closing one issue the session re-runs selection and picks the next.

**Why:** JT observed each session was using ~27% of the available limit — far below expected utilization. Rather than just bump a uniform cap, day/night split lets night sessions (cheaper attention, JT asleep) run 4x and day sessions 2x.

**Alternatives considered:**
- Uniform longer cap — rejected; night has more headroom than day, no reason to treat them the same.
- More frequent short sessions — rejected; per-session context-load overhead (reading handoff + MEMORY + PR pass) is fixed cost, so longer sessions amortize it better than more short ones.

**Reversibility:** Cheap — edit the cap arithmetic in run-session.sh.

**Related issues:** —

## D-009 — Priority tier of 5 repos worked more often (2026-06-17)
**Decision:** Five repos form a priority tier and are worked *more often* than the other eight: `llm-cost-optimizer`, `llm-eval-harness`, `rag-production-kit`, `chunking-strategies-lab`, `nextjs-streaming-ai-patterns`. Mechanism (see `session-runner/SESSION_PROMPT.md` Phase A step 5): a tighter freshness floor (18h, vs 36h for the rest) so they become eligible for "stale" selection sooner, they win every selection tie-break, and within a multi-issue run the loop is biased to keep working priority-tier repos while they have actionable unblocked issues. The other eight repos are **deprioritized, not dropped** — they continue to be worked on the normal cadence whenever no priority-tier repo needs attention.

**Why:** JT asked for these five to be updated more often than the others, while keeping the rest in rotation.

**Alternatives considered:**
- Work only these five exclusively — rejected; JT explicitly said the other repos still need updating, just less often.
- Keep equal cadence for all thirteen — rejected; that's the status quo JT asked to change.

**Reversibility:** Cheap — remove the priority-tier block from SESSION_PROMPT.md step 5 and the portfolio-session SKILL selection section.

**Related issues:** —

*Note: JT referred to the fifth repo as "next-js-streaming-ai-patterns"; the canonical repo name is `nextjs-streaming-ai-patterns`.*
