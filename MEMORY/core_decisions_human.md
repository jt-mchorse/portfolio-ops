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

## D-010 — `followups` items are quoted strings (2026-08-26)

**Decision.** In `MEMORY/full_history_ai.md`, every `followups` item is a quoted
string: `followups: ["#107"]`, `followups: ["leh#212", "csl#165"]`. This applies
to **new blocks only**. It deliberately does *not* decide whether the 74 existing
unparseable blocks are retro-fixed — that remains JT's call under handoff §10
(append-only), which is the question `#66` was filed to ask.

**Why.** `#` begins a comment in YAML when it follows whitespace or opens a
token, so an unquoted `followups: [#107]` is `followups: [` plus a comment — an
unterminated flow sequence that makes the **whole session block** fail
`yaml.safe_load`, not just that field. Measured across the portfolio on
2026-08-26: 74 of 953 blocks are already unloadable, and 72 of those are fixed by
quoting the followups items alone. Handoff §3 calls this file "AI-optimized …
for fast machine parsing", so an unloadable 8% defeats the field's purpose the
first time anything parses it.

**Quote every item, not only the bare-`#` ones.** The precise defect is narrower
than "`#` breaks YAML" — `[leh#212]` parses fine, because there the `#` follows
`h`, and `#66`'s option analysis was wrong to claim the cross-repo spelling was
at risk. But the narrow rule ("quote a followup only when it starts with `#`") is
correct and unmemorable, while "quote every item" is a superset with no
exceptions. A convention written down in a skill has to be one a tired session
can apply without thinking.

**Alternatives considered.** (1) Drop the `#` — `followups: [107]` — loses the
form the corpus actually uses and reads worse. (2) Leave it and delete the
"machine parsing" claim from the handoff — honest and cheapest, but gives up the
field's reason for existing. (3) Quote only the items that need it — see above.

**Reversibility.** Cheap. It is a writing convention plus a ratchet;
`scripts/check_memory_yaml.py --write-baseline` re-freezes the counts if the
retro-fix decision goes the other way.

## D-011 — A ninth audit fingerprint: timeout headroom (2026-09-28)

**Decision:** `scripts/audit_phase_a.py` gains `timeout-headroom`, which flags a
*runtime* job whose worst of the newest five completed push runs on the default
branch consumed at least 80% of the `timeout-minutes` its own YAML job declares.

**Why:** `missing-timeout` (D-005's fingerprint 5) asks whether a job *has* a
cap. It never asks whether the cap has any room left, so a job sitting at 99% of
it audits clean every session until the day it crosses — which is the silent-rot
shape this whole script exists for.

`llm-cost-optimizer`'s `test (3.12)` against its 15-minute cap, measured over the
ten newest push runs on `main` before any code was written:

| date | duration | ratio | result |
|---|---|---|---|
| 09-28 | 15m10s | 1.01 | **cancelled** |
| 09-23 | 10m48s | 0.72 | success |
| 09-22 | 15m05s | 1.00 | **cancelled** |
| 09-21 | 14m05s | 0.94 | success |
| 09-14 | 13m12s | 0.88 | success |
| 09-11 | 10m48s | 0.72 | success |
| 09-10 | 13m17s | 0.89 | success |
| 09-09 | 13m10s | 0.88 | success |
| 09-08 | 14m32s | 0.97 | success |
| 09-07 | 13m22s | 0.89 | success |

The ratio is at or above 0.88 in eight of ten, so the finding does not depend on
which run happens to land in the window. `main-branch-red` reports the two
cancellations after the fact; this one fires on the rows above them. The 09-28
cancellation was caused by this session's own Phase A merge.

**The unit is the runtime job, not the YAML job.** A matrix expands one block
into N runtime jobs, and a runtime job is what gets cancelled. `llm-cost-optimizer`
has one `test:` block at 15 minutes that becomes `test (3.11)` and `test (3.12)`,
and only one of the two is anywhere near the cap — 10m54s against 15m10s in the
same run. A rule keyed on the YAML job reports both.

**It is keyed on the ratio, not on the conclusion**, and that is what lets it
coexist with `missing-concurrency`. That fingerprint pushes every repo toward
`cancel-in-progress: true`, whose superseded runs are `cancelled` with a *short*
duration — so a conclusion-keyed rule would flag exactly the behaviour its
sibling asks for. The honest residue is that a superseded run cancelled at 14 of
15 minutes still trips, because from the outside it is indistinguishable from a
job that nearly timed out. That is written into the docstring rather than left to
read as a bug later.

**A runtime name that cannot be resolved is counted, not guessed.** A `name:`
interpolating matrix values renders to something the default suffix rule cannot
invert. A wrong label is worse than a missing one: it would attach a duration to
some other job's cap.

**The module docstring already said "seven" while `audit_repo` ran eight.**
`main-branch-red` was wired in for #69 without being added to the numbered list —
a prose count beside a literal that nobody compared, which is the
fingerprint-shaped defect this module exists to catch, in its own docstring. Both
are now listed, and a new test *derives* the two sets and compares them, so a
tenth landing the same way fails immediately.

**Alternatives considered:**
- *Flag on the conclusion* — rejected, built and run, 5 red.
- *Report the newest run rather than the worst* — rejected, built and run, 2 red.
  `llm-cost-optimizer` went 15m05s cancelled on 09-22 and 10m48s on 09-23, so the
  newest would have called it clean the day after.
- *Key on the YAML job* — rejected, built and run, 8 red.
- *Guess a label for an unresolvable matrix name* — rejected.
- *Raise `llm-cost-optimizer`'s cap in this PR* — deferred to that repo's own
  issue and PR, as the issue's own "Proposed" section splits it.

**On the 3.11 vs 3.12 divergence:** recorded as **unexplained with the
measurement attached**, which is the honest branch of #76's fourth criterion.
3.12 is slower in 6 of 6 paired runs — a sign test gives p ≈ 0.031, so the
direction is real — but the magnitude ranges from 5 seconds (09-23) to 8m45s
(09-21) on comparable trees. Runner variance dominates; a systematic component
cannot be sized from six points.

**Swept once across all 13 repos: one finding.** `llm-eval-harness` (a four-way
matrix) and `agent-orchestration-platform` (Postgres integration) were the
issue's named plausible neighbours and both came back clean.

**Reversibility:** Cheap.

**Related issues:** #76, #35, #40, #69

## D-012 — a workflow the headroom check cannot read is a finding (2026-10-02)

D-011's timeout-headroom check matches runtime job names to the timeouts
declared in YAML. When it can't match a name, it records the name and attaches
it to the workflow's other findings. A workflow where **nothing** matched had no
other findings, so the repo audited clean even with a job at 99% of its cap.
That workflow now gets its own `timeout-headroom-unresolved` finding, keyed on
`(repo, workflow_path)`, saying which jobs the audit can't watch and how to fix
it. It's a separate kind because "this job is near its cap" and "these jobs
can't be checked" are different claims. A workflow that already has a headroom
finding doesn't get a second line. Latent today: no workflow in the portfolio
names a job with an expression.
