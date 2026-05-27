# Session History (human-readable)

Chronological log of work sessions. Most recent first below the divider.

---

## 2026-05-10 — Bootstrap
**Duration:** bootstrap (exempt from 60-min cap per §9) · **Branch:** main (initial commits only)

- Created jt-mchorse/portfolio-ops with the handoff doc, three skills, two trending workflows, CI template, init script, issue templates, PR template, and stub scripts.
- Created the 12 portfolio repos with full scaffolding (18 files each: README, LICENSE, CONTRIBUTING, .gitignore, .github/{ISSUE_TEMPLATE, workflows/ci, pull_request_template}, .skills/{portfolio-memory, portfolio-session}, MEMORY/{four files with D-001}, docs/{architecture, benchmarks}).
- Applied the 16-label canonical set to each of the 13 repos.
- Filed 67 feature issues across the 12 demo repos, one per §2 core deliverable, with scope/acceptance/estimate per the feature.yml schema.

**Why this work, this session:** Bootstrap is the only session permitted to exceed 60 minutes per handoff §9. Single-shot setup beats incremental setup-then-work confusion.

**Open questions / blockers:**
- `scripts/trending_scan.py` and `scripts/prune_stale_trending.py` are stubs that exit 1. The workflows installed reference them but will fail until issue #1 / #2 land. This is documented honestly in the README rather than papered over with a fake green check.
- portfolio-ops needs `ANTHROPIC_API_KEY` and `PORTFOLIO_PAT` secrets configured (manual step by JT) before the workflows can pass.
- `chunking-strategies-lab` was filed with 4 initial issues, one short of the §12 "first 5" target — §2 only enumerates 4 deliverables; rather than fabricate, this is left for JT to fill.
- Branch protection on each repo is left to JT (requires GH Pro for free private repos; these are public, but the script's PR-required policy is a JT preference call).

**Next session:** Implement `scripts/trending_scan.py` per `skills/portfolio-trending/SKILL.md` as portfolio-ops issue #1. Estimated ~75 min.

## 2026-05-11 — Implement real trending scripts
**Duration:** ~45 min · **Branch:** main (direct commit to portfolio-ops, per protocol for memory + bootstrap follow-up)

- Wrote `scripts/trending_scan.py` implementing the SKILL spec: tiered daily/weekly source scan (Anthropic news + docs changelog, OpenAI blog, HF papers daily; Simon Willison, Eugene Yan, Lilian Weng, Latent Space, GitHub trending, HN for weekly), per-finding Claude eval with strict-JSON output and a system prompt that explicitly refuses to follow instructions in scraped content, 30-issue portfolio-wide cap, dedupe by title within target repo.
- Wrote `scripts/prune_stale_trending.py` to close `trending`-labeled issues with no engagement in 30 days.
- Both scripts use Python stdlib only (urllib for HTTP, re for naive XML/HTML parsing). Updated `requirements.txt` to reflect honestly that no pip deps are needed at this stage.

**Why this work, this session:** User explicitly asked to "complete the setup" after the bootstrap. Real scripts are now committed so the GitHub Actions cron actually has work to do when secrets are configured.

**Open questions / blockers:**
- `ANTHROPIC_API_KEY` and `PORTFOLIO_PAT` secrets are still pending JT's manual configuration in portfolio-ops settings. Without them, scheduled workflow runs will exit 1 cleanly with a clear error.
- Smoke test (handoff §9 step 10) is blocked on those secrets.
- Real parsing fidelity (HTML, RSS edge cases) is best-effort with regex. If signal quality suffers, a future session can introduce feedparser / beautifulsoup4. Documented honestly in requirements.txt.

**Next session:** After JT sets secrets, run the smoke test (dispatch trending-daily with --max-issues 1). Then start the first feature session on a portfolio repo per build sequence (llm-eval-harness issue #1).

## 2026-05-13 — Session-runner + cadence + PR auto-merge override
**Duration:** ~35 min · **Branch:** main (direct commit on follow-up to JT feedback)

- Added `session-runner/SESSION_PROMPT.md` — the canonical, version-controlled prompt every scheduled session uses. Edits propagate next run via run-session.sh's git pull.
- Added `session-runner/run-session.sh` — bash driver that validates env, refreshes portfolio-ops, and invokes `claude --print --dangerously-skip-permissions` with the prompt. Logs to `~/projects/portfolio/logs/`.
- Added `session-runner/SETUP.md` — one-time Mac install steps for Claude Code.
- Updated Cowork scheduled task `portfolio-daily-session`: cron changed from `30 8 * * 1-5` to `0 8,12,16,20 * * *` (every day, 4×/day). Prompt rewritten to drive osascript → Terminal.app → run-session.sh instead of running in the Cowork sandbox.
- The session prompt now enforces a strict Phase A (plan + PR review-and-merge) before Phase B (execute). D-004 overrides §10's no-auto-merge for non-draft PRs with green CI.

**Why this work, this session:** JT pushed back on three things: (1) cron too quiet, (2) sandboxed shell not using granted Mac permissions, (3) handoff §10's no-auto-merge bottlenecking velocity. All three are addressed.

**Open questions / blockers:**
- Claude Code must be installed on the Mac before the first scheduled run fires. JT should run the steps in SETUP.md.
- Manual smoke test recommended: `~/projects/portfolio/portfolio-ops/session-runner/run-session.sh` once before relying on the scheduler.
- ANTHROPIC_API_KEY and PORTFOLIO_PAT for the trending workflow are still pending JT action — unchanged.

**Next session:** First autonomous scheduled run (08:00 local tomorrow). Will pick `llm-eval-harness` issue #1 per Phase 1 selection rules.

## 2026-05-16 — Multi-issue DAY session: six PRs across five repos
**Duration:** ~65 min real time (DAY cap = 180 min) · **Branches:** six `session/2026-05-16-*` branches

Six PRs opened in one DAY session (target was 2–4; over-delivered because the Protocol+dep-free-default+lazy-Anthropic-extra pattern is now load-bearing in seven modules across four repos, so each new "feature behind a seam" reuses the same shape):

1. **rag-production-kit PR #14** — `Rewriter` Protocol with `TemplateRewriter` (dep-free, rule-based decomposition for compare/then/multi-question-and patterns) + `AnthropicRewriter` (lazy-imported via existing `[rag-anthropic]` extra). Wired into `Retriever.search(rewriter=...)`. D-014. Real bench: recall@3 on synthetic 18-chunk multi-hop fixture rises 0.625 → 0.812.
2. **mcp-server-cookbook PR #9** — third cookbook server `github-gists` (API wrapper + token auth pattern). D-007 records the redaction posture: bearer token never appears in tool results, error messages, or logs; request body dropped from error context. CI job added. 28 hermetic tests using injected fetch.
3. **rag-production-kit PR #15** — `CostRecord` + `PriceTable` (operator-supplied, no defaults, D-015) + `TelemetryStore` (stdlib `sqlite3`) + `aggregate` (p50/p95/p99) + a stdlib HTTP dashboard with inline-SVG charts. Branched off main so it's independent of PR #14; the two only collide on `__init__.py` exports.
4. **llm-eval-harness PR #14** — `eval_harness/drift.py` three-axis drift detection (length / embedding-cluster / judge). Each axis scored by Jensen-Shannon divergence (D-014, bounded `[0, 1]`, generalizes to categorical clusters where KS doesn't). Inline-SVG HTML report. `eval-harness drift` CLI subcommand. Smoke fixtures + tests assert default-threshold posture.
5. **llm-cost-optimizer PR #10** — `cost_optimizer/batch.py`: `BatchBackend` Protocol, `InMemoryBatchBackend` for hermetic CI, `AnthropicBatchBackend` duck-typed per D-002. Idempotency = caller key + content hash, conflict raises (D-010). `compare_realtime_vs_batch` with `BATCH_DISCOUNT_FACTOR = 0.5`. 28 hermetic tests.
6. **prompt-regression-suite PR #9** — `prompt-snap` console script (`run`/`update`/`diff` subcommands). Pure glue, no new decisions. `update --force` defends against accidental re-baselining. 25 hermetic tests.

Five of six PRs record a new core decision; the sixth (the CLI) is intentionally just glue.

**Why this work, this session:** Filling out the v0.1 surface of multiple repos simultaneously while the cross-repo pattern (`Protocol` + dep-free default + lazy production binding) is fresh. Five repos move toward v0.1: rag-production-kit's `Retriever.search` now exposes both pre-retrieval rewriting and per-request cost telemetry; the cookbook adds its API-with-auth entry; the eval harness's drift detection axis lands; the cost optimizer adds the batch axis; prompt-regression-suite gets its CLI.

**Open questions / blockers:**
- The two rag-production-kit PRs (#14 rewriter, #15 telemetry) collide only on `rag_kit/__init__.py` exports — whichever lands second needs a one-line rebase merging the new export lists.
- One follow-up issue filed: `mcp-server-cookbook#10` (filesystem-sandbox CI job missing). Priority:low so it doesn't crowd the queue.
- No PR-review pass at session start (zero open non-draft PRs across the portfolio), so the review-and-merge step (D-004) was a no-op.

**Next session:** Sweep the six PRs for CI signal and merge per D-004. The next code-writing target depends on what merges first — the safe choices are `embedding-model-shootout`, `chunking-strategies-lab`, or `vector-search-at-scale` (all untouched this run, all still have open priority:med work).

## 2026-05-23 — Night session: two portfolio-wide invariants to 12-of-12

**Duration:** ~60 min. **PRs merged (Phase A):** 4 — `llm-eval-harness` #30, `prompt-regression-suite` #25, `embedding-model-shootout` #20, `vector-search-at-scale` #22, all the day-session architecture-doc fix-and-lock work that had landed earlier. **PRs opened (Phase B+C):** 6 — `llm-cost-optimizer` #28, `rag-production-kit` #30, `chunking-strategies-lab` #22 + #24, `python-async-llm-pipelines` #25, `agent-orchestration-platform` #24.

Two portfolio-wide invariants reached **12-of-12 coverage** in this session:

1. **Architecture-doc lock.** Five repos had no lock at session start (`llm-cost-optimizer`, `rag-production-kit`, `chunking-strategies-lab`, `python-async-llm-pipelines`, `agent-orchestration-platform`). Authoring caught real drift in two of them: `agent-orchestration-platform` had six section headers + two paragraphs carrying pre-shipping `this PR — issue #N` / `deliberately not in this PR` framing for surfaces that had since shipped, and the doc never cited D-003 or D-004; `chunking-strategies-lab` had never cited D-011 (added 2026-05-22). The other three were test-only locks. Each PR mirrors the schema flexibly: D-NNN-only (`llm-cost-optimizer`, `chunking-strategies-lab`), `#NN`-only (none this session), or dual-axis (`rag-production-kit`, `python-async-llm-pipelines`, `agent-orchestration-platform`).

2. **README snapshot/hygiene lock.** `chunking-strategies-lab` was the last repo without one. Authoring caught three real `this PR` drift sites plus an omission of D-011 from the README's architecture-doc-summary's `D-002…D-010` cite.

Two novel portfolio patterns landed this session:

- **`OPERATOR_SUPPLIED_PATHS` allow-list with inverse safety net.** Used in `llm-cost-optimizer` PR #28 to handle the `docs/savings_real.md` reference (the operator-committed real-workload artifact per D-012's no-fabricated-benchmarks posture). The safety net is a paired test that fires if a listed path ever lands on disk — at which point it has stopped being operator-supplied and should be dropped.

- **Active-decision-range upper-bound test.** Used in `chunking-strategies-lab` PR #24 to anchor the README's `D-002…D-NNN` citation to the highest non-superseded `D-NNN` in `MEMORY/core_decisions_ai.md`. A future D-012 landing without the README updating fails the test loud with a regen hint.

**Why this work, this session:** D-004 mandates the session begin with the PR review pass; that merged the four day-session architecture-doc fixes that had landed earlier. The night-sweep then completed the same pattern across the five remaining Python repos (plus the one TS repo, `agent-orchestration-platform`).

**Open questions / blockers:** Portfolio-wide, the only remaining blocker for v0.1 across all 12 repos is the operator-supplied 60-second demo GIF — each repo has the deterministic capture script + smoke test infrastructure shipped but the recording itself is out of autonomous scope. Quality bar across all 12: 5-of-6 items done; demo GIF is the universal last item.

**Next session:** PRs queue eight ready for the Phase A review pass: the six this session opened + any others that land between now and then. Beyond merging those, the portfolio is hygiene-complete for the autonomous patterns — improving from here means new feature work (decision-revisits, new core deliverables) or operator-side work (demo GIF capture).

## 2026-05-26 — Night session: portfolio-wide validation sweep saturation
**Duration:** ~50 min (well under the 360-min NIGHT cap) · 13 PRs / 13 issues closed across 10 repos.

### Phase A (PR review pass)
Four ready PRs at session start, all with `lint=FAILURE` due to `ruff format --check` failing on freshly-merged code from the prior day session:
- `rag-production-kit#43` (deferred validation gaps from #41)
- `llm-eval-harness#45` (max_tokens validation at AnthropicBackend)
- `llm-eval-harness#47` (calibration bounded-float thresholds)
- `embedding-model-shootout#36` (deferred validation gaps from #34)

For each, ran `ruff format`, committed/pushed the format-only diff, waited for CI to go green, merged via squash. `llm-eval-harness#47` required a rebase onto main after `#45` landed (MEMORY YAML append conflict, resolved by keeping both entries per the append-only protocol).

### Phase B+C × 9 (multi-issue loop)
Each issue followed the canonical Phase B+C loop: file discovery issue → create branch → post plan comment → implement validator + tests → open PR → separate MEMORY commit. Average ~6 min/issue.

| # | Repo | Issue | PR | What it closed |
|---|------|-------|-----|----------------|
| 1 | prompt-regression-suite | #37 | #38 | HashEmbedder.ngram + CanonicalResponse.embedding finiteness |
| 2 | chunking-strategies-lab | #31 | #32 | StructureAwareStrategy completes the #29 strategy sweep |
| 3 | vector-search-at-scale | #31 | #32 | HnswSimBackend.M/ef_construction/ef_search (recall collapse) |
| 4 | python-async-llm-pipelines | #34 | #35 | AsyncPipeline + BatchedAsyncPipeline constructors |
| 5 | agent-orchestration-platform | #31 | #32 | AgentRun.run validateOptions (budget unreachable on NaN) |
| 6 | mcp-server-cookbook | #34 | #35 | GistsClient.constructor cfg validation (setTimeout silent coerce) |
| 7 | nextjs-streaming-ai-patterns | #26 | #27 | Three mock-streamer validateOptions (closes #24 deferral) |
| 8 | ai-app-integration-tests | #26 | #27 | installRecorder/installReplayer hosts validation (install-layer pass-through) |
| 9 | llm-cost-optimizer | #40 | #41 | HashEmbedder.ngram (4/4 portfolio HashEmbedder symmetry) |

### Patterns established / closed
- **Portfolio HashEmbedder symmetry: 4/4 complete.** All four implementations (rag-kit, emb-shootout, prompt-regression, cost-optimizer) now share the `not isinstance(int) or isinstance(bool) or <= 0` contract.
- **TypeScript validation pattern**: `function entry validateOptions/validateConfig + Number.isInteger/Number.isFinite + RangeError`. Now in agent-orch, mcp-cookbook, nextjs-streaming, ai-app-integration.
- **Python validation pattern**: `__post_init__ isinstance + bool reject + sign check`. Comprehensive across all Python repos.
- **Cache hit-rate degradation**, **install-layer pass-through**, **executor budget unreachable**, **HNSW recall collapse** — four new harm-class names added to the portfolio vocabulary, each closed at one site this session.

**Why this work, this session:** Continuation of the night-shift validation sweep that's been running across the portfolio over the past 72 hours. With this session, every portfolio repo has either a Phase A merge or a Phase B+C PR tonight; the validation arc is comprehensively saturated.

**Open questions / blockers:** none — every PR is ready for JT review. No unresolved merge conflicts. No core decisions made (every fix mirrors an existing pattern).

**Next session:** The validation sweep has reached saturation. Future sessions should pivot away from validation per the prior session's memory guidance. Candidate directions: 60-second demo capture (operator-supplied), trending workflow audit, or a new improvement arc surfaced by JT's weekly review.

## 2026-05-26 — Day session: Phase A rescue (6 PRs) + README decision-range lock propagation (11 PRs)
**Duration:** ~50 min real time

**Phase A.** Rescued six atomic-write `io_utils` PRs (llm-eval-harness #51, embedding-model-shootout #38, agent-orchestration-platform #34, python-async-llm-pipelines #37, chunking-strategies-lab #34, vector-search-at-scale #34). All six failed the architecture-doc-lock because each had added a new D-NNN decision but hadn't cited it in `docs/architecture.md`. Pushed a one-line-ish doc fix per PR, then squash-merged after CI went green.

**Phase B+C.** Propagated the `test_decision_range_cites_latest_active` invariant authored in chunking-strategies-lab's 2026-05-26 night session to the other 11 portfolio repos. Each PR added a D-002…D-NNN citation to the README's architecture section + a focused test file that scans `MEMORY/core_decisions_ai.md` for non-superseded entries and enforces the upper bound matches.

Three template shapes emerged:
- **Python (7 repos):** focused `tests/test_readme_decision_range.py` file with module-scoped `_max_active_decision_id()` helper.
- **TypeScript (3 repos):** focused `test/readme-decision-range.test.ts` vitest file using the same parsing logic.
- **mcp-server-cookbook (1 repo):** extended the existing `tools/check-readme.mjs` dep-free Node script instead of adding a new file, because the existing `readme-check` CI job already runs it — zero workflow changes.

**Smoking gun.** `python-async-llm-pipelines` PR #39 caught the invariant doing real work: D-011 had landed in PR #36 (the `async_pipelines.io_utils` decision) but the README's range was stale at `D-002…D-010`. The new lock now traps this drift class portfolio-wide.

**Why this work, this session:** The night session had just authored the lock pattern in chunking-strategies-lab and caught actual drift; propagating it portfolio-wide is the natural extension that closes the same drift class everywhere.

**Open questions / blockers:** none. Portfolio invariants saturated again — next session should pivot.

**Next session:** Demo GIF capture work is still the only operator-blocked v0.1 gap across 12 repos. Substantive next work is either trending-issue-driven features or new portfolio-wide patterns.

## 2026-05-27 — Issue #3: init-portfolio-repo.sh CONTRIBUTING seed updated to D-008 cadence
**Duration:** ~10 min · **Branch:** `session/2026-05-27-0336-issue-03`

- `templates/init-portfolio-repo.sh:102` still seeded every new portfolio repo's `CONTRIBUTING.md` with the pre-D-008 "~60-minute session cap" line. D-008 (2026-05-14) updated session caps to 180 min DAY / 360 min NIGHT with a multi-issue loop; the template never propagated. All twelve portfolio repos have the stale contract in their `CONTRIBUTING.md` files (verified with a portfolio-wide grep).
- Rewrote the seeded bullets to reflect D-008 (cap numbers + multi-issue loop) and D-004 (Phase A PR auto-merge for non-draft green-CI PRs).
- New lock: `tests/test_init_script_cadence.py` with five tests — script exists, "60-minute session cap" substring forbidden, "D-008" referenced, both "180" and "360" minute numbers present (parametrized over the two caps). Same loud-failure shape as the readme_trending lock from #1.
- Portfolio-ops now has two locks under its `tests/` directory: `test_readme_trending_status.py` (from #1) and `test_init_script_cadence.py` (from this issue). Both run under the `pytest` step in `.github/workflows/ci.yml`.

**Why this work, this session:** Iteration 8 of an autonomous NIGHT session. The pattern of "scan all repos for shared drift, find the root cause in portfolio-ops, fix template + lock + propagate" is now compounding — this is the second portfolio-ops template defect this session.

**Open questions / blockers:** none — PR ready for review.

**Next session:** Per-repo CONTRIBUTING.md propagations. Each is a one-line edit per repo; aim to land them as 12 thin PRs across the rest of this NIGHT session.
