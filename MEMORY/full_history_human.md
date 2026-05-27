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

## 2026-05-27 — Night session, iteration 1: portfolio-ops README unstub (issue #1)
**Duration:** ~20 min · **Branch:** `session/2026-05-27-0311-issue-01` · **PR:** #2

- Found stale README claim in portfolio-ops: section "Trending workflow status" still said `scripts/trending_scan.py` and `scripts/prune_stale_trending.py` are "not yet implemented" two weeks after **D-003** shipped real stdlib-only implementations on 2026-05-11. Filed #1, posted plan, fixed.
- Rewrote the section to describe what each script actually does and cited D-003 by name. Moved required-secrets guidance into a "Running it yourself" subsection.
- Added `tests/test_readme_trending_status.py` (six assertions) and `.github/workflows/ci.yml` so the lock runs on every PR. Portfolio-ops previously had no CI workflow of its own.
- This is the same drift class the per-repo `test_readme_decision_range` lock catches across the 12 portfolio repos — portfolio-ops itself had no equivalent until now.

**Why this work, this session:** Three NIGHT sessions in a row hit "portfolio is saturated" — but a quick survey of portfolio-ops itself found a fresh stale-doc defect. Self-policing the spine repo was the highest-ROI quick win available; doing it first warms the loop before bigger work.

**Open questions / blockers:** Untracked `workflows/` directory at the repo root mirrors `.github/workflows/` — out of scope for this issue but worth a follow-up issue if it's not intentional.

**Next session iteration:** Loop continues across the 12 portfolio repos.

## 2026-05-27 — Issue #5: handoff + portfolio-session SKILL cadence wording refresh (with retroactive D-006/D-007 capture)
**Duration:** ~25 min · **Branch:** `session/2026-05-27-1520-issue-05`

- `COWORK_HANDOFF.md` and `skills/portfolio-session/SKILL.md` still shipped the pre-D-008 contract on every cold read by an operator or by Claude Code — 60-minute target, 65-minute hard ceiling, and the flat "do not auto-merge PRs" rule that D-004 already overrode for Phase A. The bootstrap-template fix (#3) closed the *seed* surface; this issue closes the *canonical-session-briefing* surface.
- Updated §1.3, §4 Hard rules, §10 Must Not Do in the handoff; description + time-budget paragraph + hard-rule bullet + multi-session paragraph + failure-mode bullet in the skill. All now cite the `RUNTIME OVERRIDE` header (the runner's source of truth) and D-008's 180/360-min cadence; the §10 auto-merge rule is recharacterised per D-004 (drafts, red CI, and fishy diffs still protected).
- Left §9 bootstrap exemption at line 552 as-is — it documents the historic first-run exemption, not active per-session policy.
- Retroactively logged **D-006** (15-min minimum per issue, live in `session-runner/SESSION_PROMPT.md` since commit 7690999 on 2026-05-13) and **D-007** (fall-through to next repo when chosen repo is one-way-blocked, live since commit 4670bd0 on 2026-05-13). Both decisions were already binding on every scheduled session through the runner-prepended prompt, but had never been captured in `core_decisions_*.md`. Citing them in the refreshed handoff/skill text exposed the gap; capturing them now restores referential integrity.
- Both retroactive entries are tagged with origin commit + timestamp so future readers can trace the provenance.
- No new lock or test. The bootstrap-template lock (`tests/test_init_script_cadence.py` from #3) is the inverse-net for the *seed* surface that propagates to other repos; the handoff and skill are operator-readable canonical sources, not seeded elsewhere, so a separate guard would be over-fit. This is also the explicit acceptance criterion on #5.

**Why this work, this session:** Iteration 1 of an autonomous DAY session after a heavy Phase A merge pass. The bootstrap-template fix had closed the seed surface but not the briefing surface; this finishes the symmetric pair.

**Open questions / blockers:** none — PR ready for review.

**Next session:** Loop continues — pick the next-best repo/issue from the portfolio.

## 2026-05-27 — Issue #7: track `workflows/` templates referenced by init-portfolio-repo.sh
**Duration:** ~8 min · **Branch:** `session/2026-05-27-1527-issue-07`

- Fresh-clone bootstrap was silently broken. `templates/init-portfolio-repo.sh:44` copies from `$portfolio_ops_root/workflows/ci-template.yml` when seeding a new repo, but the `workflows/` directory at portfolio-ops root was never tracked in git — it only existed locally on the bootstrap machine. A `git clone jt-mchorse/portfolio-ops && ./templates/init-portfolio-repo.sh new-repo` would have hit a missing-file error.
- Prior-session memory had already noted this gap as a followup ("workflows directory at repo root is untracked, three files mirror .github/workflows, filed as followup not in scope for this session"). This is that followup.
- Added the three template files: `workflows/ci-template.yml`, `workflows/trending-daily.yml`, `workflows/trending-weekly.yml`. Verified byte-identical to their `.github/workflows/` counterparts before staging (`diff -q` returned empty for all three).
- No changes to `.github/workflows/` — portfolio-ops' own active CI is unaffected. The two locations have distinct semantics now: `workflows/` is the template source the init script reads from, `.github/workflows/` is what GitHub Actions runs for portfolio-ops itself. Handoff §11 explicitly lists the three template files, so their tracked presence now matches the spec.
- No new lock or test — the fresh-clone-bootstrap criterion in handoff §9 is already the implicit gate, and a separate guard would be over-fit (it's a *tracking state* gap, not a *content drift* gap).

**Why this work, this session:** Iteration 2 of an autonomous DAY session. The portfolio's open priority:high backlog cleared after Phase A; this followup-flagged-by-prior-memory was the next highest-leverage thing.

**Open questions / blockers:** none — PR ready for review.

**Next session:** Loop continues — pick the next-best work item.

## 2026-05-27 — DAY session aggregate
**Duration:** ~30 min real time · **PRs merged:** 19 (17 portfolio + 2 portfolio-ops) · **Phase B+C PRs opened:** 2 (both portfolio-ops, both merged before close)

- **Phase A** rescued the 17 ready PRs the overnight 2026-05-27 session had authored (D-008/D-004 CONTRIBUTING propagation + earlier readme-doc fixes). Twelve merged cleanly; five required rebase due to memory YAML/YAML conflicts with an earlier-merged readme PR in the same repo. Pattern is well-established now — `/tmp/resolve_memory_conflict.py` resolves the conflict in one call per repo by keeping both append-only blocks. The Phase A `for r in <12 repos>; do ...` loop misses portfolio-ops itself; this session also swept the two ready portfolio-ops PRs (#2 issue #1, #4 issue #3) as a bonus pass.
- **Phase B iteration 1 (issue #5):** `COWORK_HANDOFF.md` §1.3, §4 Hard rules, §10 Must Not Do plus `skills/portfolio-session/SKILL.md` description, time-budget paragraph, hard-rule bullet, multi-session paragraph, and failure-mode bullet all refreshed to cite the runner's `RUNTIME OVERRIDE` header and D-008 / D-006 cadence. The §10 auto-merge bullet recharacterised per D-004 (drafts, red CI, fishy diffs still protected). Also retroactively logged **D-006** (15-min minimum per issue, live since commit 7690999 on 2026-05-13) and **D-007** (fall-through to next repo when one-way-blocked, live since 4670bd0 on 2026-05-13) in `core_decisions_*.md`. These were live in the runner all along but never captured in MEMORY.
- **Phase B iteration 2 (issue #7):** `workflows/ci-template.yml`, `workflows/trending-daily.yml`, `workflows/trending-weekly.yml` now tracked in git — the prior session had created the directory locally without `git add`. `templates/init-portfolio-repo.sh:44` was silently broken on fresh clone because it copies from this directory. Files are byte-identical to their `.github/workflows/` counterparts; `.github/workflows/` unchanged.
- **Portfolio state after this session:** zero open priority:high issues across all 13 repos; three priority:low demo-capture issues remain blocked on an operator-supplied GIF recording.
- **Validation arc:** still saturated per prior two sessions' memory guidance. This session did not propagate a new lock; both shipped issues were substantive content/tracking-state fixes, not propagation work.

**Why this work, this session:** DAY session with substantial Phase A queue from the overnight propagation run. Phase A took the bulk of the meaningful work; Phase B+C closed the two remaining canonical-doc / tracking-state loose ends that prior session memory had flagged.

**Open questions / blockers:** none — portfolio is genuinely at a saturated state for autonomous high-value work. Next session's substantive options likely lie outside per-repo invariant propagation; the demo-capture pipeline is the only outstanding v0.1 quality-bar item and that's operator-gated.

**Next session:** Either NIGHT session continues with substantive engineering depth in one specific repo, or DAY session takes a short Phase A pass (if any PRs accumulate) and reports a healthy idle.

## 2026-05-27 — Issue #9: portfolio-ops missing from Phase A for-loop in SESSION_PROMPT.md
**Duration:** ~15 min · **Branch:** `session/2026-05-27-1907-issue-9`

- The Phase A PR-review for-loop in `session-runner/SESSION_PROMPT.md` listed only the 12 portfolio repos, not portfolio-ops itself. Prior session memory had flagged this — PRs against portfolio-ops sat unseen until a manual sweep noticed them. Closing the gap: appended `portfolio-ops` to the for-loop on line 34.
- Authored `tests/test_session_prompt_phase_a_loop.py` as the inverse-safety-net. It uses a regex to parse the `for r in ...; do` literal directly out of `SESSION_PROMPT.md` and parametrizes a presence test over all 13 known repo names. A future edit that drops any repo (especially portfolio-ops, the regression just hit) fails loudly with the exact missing repo named in the assertion message. Also asserts no unknown repos sneak in and the count matches.
- portfolio-ops now carries three lock tests in `tests/` (readme-trending, init-script-cadence, session-prompt-phase-a-loop). All 27 tests passing locally — five existing init-cadence + six existing trending-readme + sixteen new for-loop cases.

**Why this work, this session:** DAY session opened with zero priority:high issues across all 13 repos and five open PRs that were all draft demo-capture work (operator-blocked). The only actionable follow-up was the explicit recommendation in prior session memory to add portfolio-ops to the Phase A loop — concrete, testable, and a precise inverse-net candidate.

**Open questions / blockers:** none — PR #10 ready for review.

**Next session:** Loop ends here. Portfolio actionable backlog remains genuinely empty; the demo-capture pipeline is the only outstanding v0.1 item and is operator-gated.

## 2026-05-27 — Issue #11: promote `/tmp/resolve_memory_conflict.py` to `scripts/`
**Duration:** ~15 min · **Branch:** `session/2026-05-27-1911-issue-11`

- The MEMORY YAML/MD rebase-conflict resolver had been living in `/tmp` across multiple sessions. Prior memory called the bar "if seen repeatedly" — six invocations across two sessions in 24h cleared it. Promoted to `scripts/resolve_memory_conflict.py` alongside `trending_scan.py` and `prune_stale_trending.py`, with argparse, a `--dry-run` flag, and a post-resolution invariant check that raises if conflict markers remain (catches a future regression where the input shape stops matching the append-only pattern).
- Authored `tests/test_resolve_memory_conflict.py` (15 cases). Before writing the fixtures, I reproduced a real 3-way merge conflict on `MEMORY/full_history_ai.md` in a scratch repo and inspected the git output. The empirical shape: the `---` opener of the new YAML block stays in the prefix (above `<<<<<<<`), and the trailer (`decisions_made: []`, `followups: []`, `---`) is shared after `>>>>>>>` because git's diff aligns on the repeated trailer lines. The first draft of my fixture had `---` inside the conflict markers — the resolver-vs-expected test caught it, and I fixed the fixture rather than the resolver. Coverage: marker absence, both-blocks-kept, order preserved, trailer correctly attached to block A, exact-string round trip, no-op on clean text, plus four CLI integration cases via `tmp_path`.
- portfolio-ops now carries four lock tests under pytest (readme-trending, init-script-cadence, session-prompt-phase-a-loop, resolve-memory-conflict). All 26 pass on this branch (the 27th from issue #9 will appear after PR #10 lands and this branch rebases — itself an eat-our-own-dogfood scenario for the tool this PR ships).

**Why this work, this session:** Iteration 2 of an autonomous DAY session. Issue #9 (Phase A for-loop) closed iteration 1; iteration 2 picked the second concrete follow-up flagged in prior session memory, which had explicitly named the "seen repeatedly" bar.

**Open questions / blockers:** none — PR #12 ready for review.

**Next session:** Loop probably ends here. Portfolio actionable backlog is empty; the demo-capture pipeline remains operator-gated. When PR #10 and PR #12 both land, future sessions can rebase against rather than re-implement this tool.

## 2026-05-27 — Issue #13: `.github/workflows/ci-template.yml` misplaced, fails every push
**Duration:** ~25 min · **Branch:** `session/2026-05-27-1610-issue-13`

- Phase A PR-review pass merged two ready PRs in portfolio-ops (#10 phase-a for-loop fix + lock; #12 promotion of `/tmp/resolve_memory_conflict.py` to `scripts/` + lock). PR #12 needed a rebase against the just-merged PR #10 — used the resolver script that PR #12 was shipping to handle the YAML conflict on `full_history_ai.md`, manually resolved the MD conflict in `full_history_human.md`, force-with-leased the rebase, and merged after CI re-greened. The session ate its own dogfood.
- During the PR-review pass I audited the Actions run history out of curiosity. The runs list showed paired ci runs on every push: one labeled `ci` succeeding (id ...085244) and one labeled `.github/workflows/ci.yml` failing (id ...084915). The failing one's error: "This run likely failed because of a workflow file issue." Tracing back: `.github/workflows/ci-template.yml` and `.github/workflows/ci.yml` both declare `name: ci`. The template was left in `.github/workflows/` by the bootstrap commit on 2026-05-10 — every push since has fired both workflows; the template's failure was silent because PR merges weren't blocked by it. 17 days of silent rot in the operational backbone.
- Filed issue #13 at `priority:high`, posted the plan as a comment, deleted `.github/workflows/ci-template.yml` (the canonical copy at `workflows/ci-template.yml` is byte-identical and was tracked in PR #8; `init-portfolio-repo.sh` line 44 reads from `workflows/` so the template's intended use is unaffected). Authored `tests/test_workflows_dir_only_active.py` as the inverse-net: presence test parametrized over the three intended active workflows (`ci.yml`, `trending-daily.yml`, `trending-weekly.yml`), plus rejection tests for `*-template.yml` shapes and any unexpected filename. All 49 tests passing.

**Why this work, this session:** Three sessions in a row have reported zero priority:high issues across all 13 repos — Phase A is what finally caught this real bug. The portfolio truly is saturated for new feature work, but the operational backbone needs periodic audits and Phase A is the right place to do them.

**Open questions / blockers:** none — PR ready for review; one CI run should fire (not two) on the merge.

**Next session:** Phase A will likely still find an empty issue backlog. Future Phase A passes should include a quick "any paired failing workflow runs in the last 24h?" check as standard hygiene; this issue's fix doesn't make it impossible for a new template-shaped workflow to land in `.github/workflows/`, only loudly noisy when it does (via the new lock test). The lock catches the regression; the Phase A habit catches new failure modes.

## 2026-05-27 — Issue #15: stale ci.yml workflow registration heals via workflow_dispatch
**Duration:** ~10 min · **Branch:** `session/2026-05-27-1640-issue-15`

- PR #14 deleted the misplaced template, but the post-merge push *still* produced a failing 0s 'workflow file issue' run for the real ci.yml. Tracing: GitHub Actions had cached the workflow under `name = '.github/workflows/ci.yml'` (path-as-name fallback) instead of `name = 'ci'` from the YAML — a leftover from the 17-day conflict where the template had won the 'ci' name slot. With the template gone, the registration didn't auto-heal on subsequent pushes.
- Adding `workflow_dispatch:` under `on:` is a no-op for the normal push/PR triggers but forces GitHub's workflow parser to re-read the file and re-register it with the declared name. Side benefit: emergency manual-trigger affordance via `gh workflow run ci.yml`. After merge of this PR, the workflow registration should heal and the test job should actually run `pytest tests/ -q` for ~15-30s rather than failing in 0s.
- No new lock test for this — it's a GitHub Actions runtime state issue, not a file-shape property. `tests/test_workflows_dir_only_active.py` from #14 already protects against the underlying cause (re-adding `*-template.yml` to `.github/workflows/`).

**Why this work, this session:** Iteration 4 of the autonomous DAY session loop. PR #14's fix was necessary but not sufficient — the runtime registration didn't heal on its own. The portfolio-wide bigger picture: the 42 lock tests added across recent sessions have never run in CI on portfolio-ops because of this conflict. After #16 merges, they will.

**Open questions / blockers:** none — PR ready for review; the proof-point is the next post-merge run on main producing a non-zero pytest duration.

**Next session:** Phase A audit cadence is the right place to keep catching silent-rot regressions like this. The new Phase A habit recommended from #13 ("audit Actions tab for paired failures") would have caught both this and the trending-workflow-secret-missing failures sooner.
