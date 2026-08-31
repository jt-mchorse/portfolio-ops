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

## 2026-05-27 — Issue #19: Phase A operational-health audit script
**Duration:** ~25 min · **Branch:** `session/2026-05-27-1730-issue-19`

- Codified the three silent-rot fingerprints uncovered by this session into `scripts/audit_phase_a.py`. Each check hits one GitHub Actions REST endpoint per repo (`actions/runs?event=push&branch=main`, `actions/workflows`, `actions/runs?event=schedule`) and emits structured findings. Stdlib-only (urllib + json), honors `GH_TOKEN` / `GITHUB_TOKEN`, falls back to unauth reads for public repos. Exit 0 = clean, 1 = findings, 2 = fetch error.
- Live-tested against portfolio-ops: returns 7 findings exactly matching the open issues — 4 paired-failure runs (issue #13 shape, historical), 2 stuck-registration workflows (ci.yml + verify.yml from issue #15), 1 stale schedule (trending-daily, 9 consecutive failures from issue #17). Live-tested against llm-eval-harness: returns clean. Confirms no false positives on healthy repos.
- Authored 12 test cases via `unittest.mock.patch` of `urllib.request.urlopen` returning canned API fixtures. Coverage matrix per finding shape: positive path + negative paths (single run per SHA, uniform success, disabled workflow, success between failures, threshold parameter) + the no-finding clean case + end-to-end CLI shape (exit codes, summary, --json output).
- Deferred wiring the script into `session-runner/SESSION_PROMPT.md` to a separate doc-only follow-up. The script should prove itself across a few sessions of dry runs first; an invariant-failing test on a non-yet-deployed script would be over-fit.

**Why this work, this session:** Iteration 6. The three silent-rot fingerprints all currently exist in portfolio-ops *right now* (issues #15 and #17). The audit script will keep flagging them on every scheduled session even if the operator can't address them immediately — making the silence accountable.

**Open questions / blockers:** portfolio-ops CI is currently broken (issue #15) so this PR's CI badge won't go green until that's resolved. 61 pytest pass locally.

**Next session:** After the operator deals with #15 and #17, the audit script returns clean and the next session's Phase A can begin invoking it as a sanity check. SESSION_PROMPT.md wiring follow-up at that point.

## 2026-06-02 — Issue #21: Wire `audit_phase_a.py` into Phase A
**Duration:** ~35 min · **Branch:** `session/2026-06-02-1514-issue-21`

- Inserted a new step 4 "Silent-rot audit pass" in `session-runner/SESSION_PROMPT.md`, immediately after the PR-review pass. The loop iterates over the same 13 repos already enumerated in step 3, captures per-repo exit codes via `rc=$?` and a `case` statement (no `| head` swallow), and documents the 0/1/2 exit semantics inline. Marked observational and non-blocking with explicit do-not-auto-file framing. Subsequent steps 4→5, 5→6, 6→7, 7→8 renumbered.
- Added `tests/test_session_prompt_phase_a_audit.py` (22 cases) as the inverse-safety-net lock — mirrors the shape of `test_session_prompt_phase_a_loop.py` which locks the PR-review for-loop. Beyond per-repo presence, it asserts script-exists, --repo flag used, all three exit codes documented, observational framing present, and a lockstep invariant that the PR-review loop and the audit loop enumerate the same set in the same order.
- Dogfood: ran the documented invocation block against `llm-eval-harness` (clean) and `portfolio-ops` (six findings verbatim). Both rc=0 and rc=1 paths surface correctly.

**Why this work, this session:** PR #20's closing memory explicitly deferred wiring `audit_phase_a.py` into SESSION_PROMPT.md "until the script proves itself across a few sessions". Today's session ran the audit ad-hoc during Phase A and used the findings to confirm 12/12 portfolio repos clean plus six known portfolio-ops findings — two sessions in, the script earned its protocol slot.

**Open questions / blockers:** None for this issue. The audit re-confirmed three operator-blocked items already tracked elsewhere (#15 ci.yml registration, #17 ANTHROPIC_API_KEY, draft PR #18). No new issues filed from audit output this round; observational only per the wired-in protocol.

**Next session:** PR #22 will land via Phase A merge cadence. The next-session audit will be the first one to actually run from the protocol rather than ad-hoc, providing the first behavior-from-doc validation.

## 2026-06-17 — Issue #27: CI phantom failures since 2026-05-27 — actual root cause is one unquoted YAML colon
**Duration:** ~60 min · **Branch:** `session/2026-06-17-1519-issue-27`

- Phase A surfaced two ready PRs (#22, #26) blocked on phantom red CI (`statusCheckRollup=[]`, but workflow runs all completing with `conclusion=failure` and zero jobs). The pattern goes back to 2026-05-27, surviving PR #14 (delete misplaced template), PR #16 (add `workflow_dispatch`), and PR #18 (rename to `verify.yml`, never merged because it also produced 0-job runs). Initial hypothesis: stuck path-as-name workflow registration at the GitHub Actions layer. Filed #27, posted plan, opened PR #28 with a `ci.yml` → `tests.yml` rename + lock test update.
- First push on the new branch reproduced the same 0-job phantom. Working through diagnostics (workflow_dispatch rejected by both old and new workflow ids, check-suite `latest_check_runs_count=0`), I tried parsing `tests.yml` with PyYAML and got the actual answer:
  ```
  yaml.scanner.ScannerError: mapping values are not allowed here
    in tests.yml, line 37, column 25
  ```
  Line 37 was `run: grep -q "id: D-001" MEMORY/core_decisions_ai.md` — the colon-space inside the unquoted scalar is YAML mapping syntax. GitHub Actions' parser is lenient enough to *complete* the run (which is why prior fixes never crashed loudly), but emits zero jobs and `conclusion=failure`. PRs #14, #16, #18 all kept the broken line, so the parse failure (and the path-as-name registration that GitHub falls back to) persisted across every attempt.
- The fix is one character: single-quote the whole `run:` value. Pushed, watched run `27700728534` (pull_request event) go `conclusion=success` with both jobs (`test` and `memory-check`) all 12 steps green — first green CI in 21 days. The `Verify D-001 baseline decision exists` step itself now runs and passes. The rename to `tests.yml` stays in the PR as opportunistic cleanup (orphans stuck workflow id `283921465`); the YAML quote is the load-bearing fix.

**Why this work, this session:** Three sessions in a row reported "no priority:high open issues, portfolio is saturated." Phase A's CI hygiene check is what finally surfaced the bug. The portfolio-wide effect is large: every PR merged since 2026-05-27 was merged without real CI signal, because phantom-failure runs never populated `statusCheckRollup`.

**Open questions / blockers:** none for this PR — it's CI-green and ready for review. Follow-ups: disable phantom workflows `283921465` + `284535289` via API after merge; close PR #18; rebase PR #22 and #26 onto fresh main.

**Next session:** Once #28 merges, the next session's Phase A loop should re-evaluate PR #22 and #26 with their fresh CI runs. The audit_phase_a.py script could grow a new finding shape for "workflow runs completing with zero jobs across multiple SHAs" — phantom-YAML-failure is a fingerprint distinct from the three it currently checks.

## 2026-06-02 — Issue #23: `resolve_memory_conflict.py` clear error for file-path args
**Duration:** ~20 min · **Branch:** `session/2026-06-02-1524-issue-23`

- Added an `is_file()` guard at the top of `main()` in `scripts/resolve_memory_conflict.py`. When the positional arg resolves to a file (a session reaching for the script and passing `MEMORY/full_history_ai.md` instead of the repo root), the script exits 1 with `error: '<arg>' is a file; pass the repo root containing MEMORY/ instead`. The existing missing-MEMORY-dir branch is unchanged.
- Added a 16th case to `tests/test_resolve_memory_conflict.py` covering exit code, error-message content, and a negative assertion that the legacy confusing `/MEMORY/ not found` shape no longer surfaces for file paths.
- Refined the issue spec mid-flight: initial body proposed exit code 2 (matching the `audit_phase_a.py` convention) but `resolve_memory_conflict.py` documents 0/1 only. Kept internal consistency over cross-script alignment; left a comment on #23 explaining the deviation.
- Dogfood surfaced a separate false-positive bug in `_process()` — the substring check for `<<<<<<<` matches prose mentions of the marker in MEMORY files (only triggers on portfolio-ops' own MEMORY/, which documents the marker shape). Filed as issue #25 for a future session per Phase B "Stay on the issue" discipline rather than expanding scope.

**Why this work, this session:** With priority:high genuinely exhausted after #21 (only operator-blocked #17 left), the next-best work was a real-bug fix observed in-session per the established pattern. The legacy error shape was the failure mode this 20-min fix prevents.

**Open questions / blockers:** None for this issue. Issue #25 (substring false positive) noted but deliberately deferred.

**Next session:** PR #26 lands in Phase A. The next session's Phase A audit (now running from protocol post-#22) will validate the wired-in step works end-to-end.

## 2026-06-17 — Issue #25: resolve_memory_conflict prose-marker false positive
**Duration:** ~15 min · **Branch:** `session/2026-06-17-1543-issue-25`

- Replaced the two substring `<<<<<<<` checks in `_process()` (early bailout and post-resolve invariant) with `CONFLICT.search(...)` calls. The compiled regex was already the truth for the actual `sub()` pass; the substring shortcut was a cheap approximation that misclassified prose mentions as conflicts.
- Added `test_main_prose_mention_of_marker_is_no_op` covering the shape end-to-end via `tmp_path` — both markers present as Markdown code spans, no `=======` separator, asserted as a no-op exit 0 with the file unchanged. All 85 tests pass.
- Dogfood: `python3 scripts/resolve_memory_conflict.py .` on portfolio-ops now prints `no conflicts found` and exits 0, instead of the prior "Conflict markers remain… Inspect manually" raise.

**Why this work, this session:** Issue #25 was filed priority:low during issue #23 dogfooding but bit me twice during today's PR #22 and PR #26 rebases — the script bailed on `MEMORY/full_history_human.md` and I had to hand-edit the conflict markers each time. Fix shipped now so the next rebase that hits a memory conflict on this file completes hands-off.

**Open questions / blockers:** none.

**Next session:** Phantom workflows `283921465` (ci.yml orphan) and `284535289` (verify.yml orphan) — `283921465` is already auto-removed from the active list since main no longer has ci.yml; `284535289` is `disabled_manually`. No follow-up needed unless a new workflow inherits the path-as-name pattern (would surface via the YAML-parseability lock recommended in the next issue to file).

## 2026-06-17 — Issue #30: YAML-parseability lock for every workflow file
**Duration:** ~18 min · **Branch:** `session/2026-06-17-1548-issue-30`

- Added `tests/test_workflows_yaml_parseable.py` parametrized over `.github/workflows/*.yml` + `workflows/*.yml`. Each workflow file gets two assertions: `yaml.safe_load()` succeeds, and the parsed dict has a non-empty `jobs:` mapping. The first catches the exact bug from PR #28; the second catches the broader "valid YAML but no work" failure mode in case GitHub Actions silently absorbs another variant the same way.
- Inverse-net validated by feeding a scratch file with the historical bug shape (`run: grep -q "id: D-001" foo.md`) to `yaml.safe_load()` — raises `ScannerError: mapping values are not allowed here` in one line, zero call overhead. The parametrized test surfaces this exception with line/col and a failure message linking back to the silent-CI shape.
- Updated `.github/workflows/tests.yml` install step from `pytest` to `pytest pyyaml` so the new lock runs in CI. Local count: 85 → 98 passed (+13). CI run b05f1c7d: both jobs green, all steps including the new pyyaml install.

**Why this work, this session:** PR #28 closed the 21-day silent CI outage but didn't prevent the next workflow YAML drift. The lock is the next entry in the portfolio's silent-rot prevention arc, alongside the architecture-doc, README, and decision-range upper-bound locks. 30-min task that buys back permanent confidence in CI signal.

**Open questions / blockers:** none. Test suite green, CI green, all six current workflow files validate.

**Next session:** Propagate this lock pattern to the 12 portfolio repos as a follow-up sweep — they use the safer `run: |` block scalar form today, but the inverse-net should exist in every repo. Separate PR set; intentionally out of scope for this PR.

## 2026-06-17 — Issue #32: audit_phase_a.py phantom-CI fingerprint
**Duration:** ~20 min · **Branch:** `session/2026-06-17-1556-issue-32`

- Added `check_phantom_ci(repo, token, threshold=3, window=5)` to `scripts/audit_phase_a.py`. Groups the last 20 push runs on main by workflow_id, counts how many have `latest_check_runs_count == 0` AND `conclusion in {failure, null}`, flags any workflow above threshold. Wired into `audit_repo()` and `format_finding()` for both text + JSON output.
- Added an active-workflow filter: only considers workflow_ids currently `state: active` in `/actions/workflows`. Post-fix historical phantoms from disabled/deleted workflows do NOT cry wolf. Validated against portfolio-ops itself — the old `ci.yml` workflow id 283921465 (5/5 phantom runs on main history) correctly does NOT surface after PR #28 retired it.
- 8 new test cases (98 → 106 passed): positive 3/3 failures, negative jobs-present, negative below-threshold, positive threshold-boundary, negative empty-runs, positive null-conclusion, positive /jobs-fallback for old payloads, negative active-workflow-filter for disabled-history. Reuses the existing urllib.request.urlopen monkeypatch fixture.

**Why this work, this session:** PR #31's YAML lock catches the cause at PR-test time but only when a PR opens; direct-to-main commits (e.g., the `4e058f9` watchdog commit from 2026-06-01) bypass PR CI and would still be unaudited. The phantom-CI fingerprint is the post-deploy net for the same failure mode — surfacing the bug on the next Phase A pass instead of going unnoticed for weeks.

**Open questions / blockers:** none. portfolio-ops dogfood returns the known stale-schedule for trending-daily (operator-blocked #17) and nothing else; llm-eval-harness returns clean.

**Next session:** Phase A's audit run will surface phantom-CI if any portfolio repo regresses. The silent-rot prevention arc now covers all three layers: PR-test (test_workflows_yaml_parseable), post-deploy detection (phantom-CI fingerprint), and file-shape inverse (workflows-dir-only-active).

## 2026-06-17 — Issue #24: Weekly audit-cron workflow
**Duration:** ~50 min · **Branch:** `session/2026-06-17-2311-issue-24`

- Added `.github/workflows/audit-cron.yml`: Monday 14:00 UTC + manual dispatch. Runs `scripts/audit_phase_a.py` against all 13 portfolio repos, then branches on the script's exit code — clean exits silently, findings file a rolling `[audit-cron]` issue (skipped if one is already open, so the cron can't pile up duplicates), and fetch errors fail the workflow loudly so the Actions tab surfaces the problem.
- Added `tests/test_audit_cron_workflow.py` — 7 shape invariants: name, weekly cron `0 14 * * 1`, `workflow_dispatch` trigger, `issues: write` permission, script invocation, dedupe-label references appearing in both the `gh issue list` lookup and the `gh issue create` call, and a cross-lock check that `audit-cron.yml` is also in the sister `EXPECTED_ACTIVE_WORKFLOWS` tuple. Each assertion's failure message explains the silent-failure mode it protects against.
- Extended `tests/test_workflows_dir_only_active.py`'s `EXPECTED_ACTIVE_WORKFLOWS` with `"audit-cron.yml"` so the inverse lock keeps agreeing.
- Created the `audit-cron` GitHub label out-of-band so `gh issue create --label audit-cron` works the very first time the cron fires.

**Why this work, this session:** PR #22 wired `audit_phase_a.py` into Phase A of `SESSION_PROMPT.md` so every autonomous session runs the audit. But the script only catches silent rot at session cadence — a week-long gap (operator on vacation, runner offline) reverts to open-ended exposure. The weekly cron is the post-deploy net for that case.

**Design pivot from issue spec.** Issue #24 said to host the workflow in `llm-eval-harness` because portfolio-ops' own workflows were stuck-registered at filing. That premise broke this morning: PR #28 root-caused the YAML parse error (`grep -q "id: D-001" ...` had an unquoted colon-space) and got the first green CI run in 21 days; PR #31 added the YAML-parseability lock so the failure mode can't silently recur. Hosting the cron in portfolio-ops removes the cross-repo PAT requirement, lets the lock test read the workflow file directly, and avoids scope intrusion on `llm-eval-harness`. Reversible — moving the file later is one PR. Rationale documented in the session-plan comment on #24.

**Open questions / blockers:** none. Local pytest 109 → 116 (+7), all green. Post-merge plan: trigger `workflow_dispatch` once to confirm the end-to-end path. Expected first-run behavior: the cron finds the known operator-blocked stale-schedule on portfolio-ops `trending-daily` (issue #17) and files an `[audit-cron]` rolling issue referencing it. JT can close that issue tying it back to #17. Subsequent weeks no-op until something new rots.

**Next session:** If the rolling-issue cadence becomes noisy across a few weekly runs, add the deferred fingerprint-hash dedupe (compare normalized findings to the prior open issue's body; only file if the fingerprint differs). For now, the simpler one-at-a-time gate matches priority:low scope.

## 2026-06-17 — Issue #35: missing-timeout fingerprint in audit_phase_a.py
**Duration:** ~30 min · **Branch:** `session/2026-06-17-2329-issue-35`

- Added `check_missing_timeout(repo, token)` as the fifth silent-rot fingerprint. Lists active workflows via `/actions/workflows`, fetches each YAML via `/contents/<path>`, base64-decodes, `yaml.safe_load`s, walks `jobs:`, flags any without `timeout-minutes`.
- `yaml` is lazy-imported inside the new check; if pyyaml isn't installed the check returns `[]` plus a stderr note, so the other four fingerprints keep working stdlib-only. Docstring updated to call out the soft-constraint relaxation.
- Wired into `audit_repo` + `format_finding`. New finding shape: `{kind, repo, workflow_name, workflow_path, jobs_missing: [...]}`.
- 5 new tests: all-guarded (clean), one-unguarded, all-unguarded (sorted output), disabled-skipped, and pyyaml-missing (with capsys stderr assertion).
- Dogfood vs four live repos: llm-eval-harness (PR #63 pending) → 2 findings; rag-production-kit (unprotected) → 2 findings. Confirmed correct discrimination — once each session-PR merges, that repo drops out of the finding set automatically.

**Why this work, this session:** the per-repo lock propagation pattern works but takes one PR per repo. With 9 repos still unguarded after three propagations this session, the audit-side fingerprint is the cross-repo post-deploy net: the weekly audit-cron (PR #34) surfaces every remaining unguarded job until the lock is fully propagated. Higher leverage than any single per-repo PR.

**Open questions / blockers:** none. 106 → 111 pytest passes. PR #36 open. After PR #34 (audit-cron.yml) lands, a small follow-up adds `pip install pyyaml` to its install step — until then, the cron would log a "pyyaml not installed" stderr note for the missing-timeout check and continue cleanly with the other four.

**Next session:** propagate the timeout-minutes lock to the remaining 9 repos (rag-production-kit, embedding-model-shootout, chunking-strategies-lab, vector-search-at-scale, python-async-llm-pipelines, agent-orchestration-platform, mcp-server-cookbook, nextjs-streaming-ai-patterns, ai-app-integration-tests). The audit-cron will surface them weekly until they're done.

## 2026-06-18 — Issue #38: timeout-minutes guard + lock test (final hop)
**Duration:** ~25 min · **Branch:** `session/2026-06-18-0341-issue-38`

- Added `timeout-minutes: 15` to all 5 jobs across 4 workflow files:
  `audit-cron.yml::audit`, `tests.yml::test`, `tests.yml::memory-check`,
  `trending-daily.yml::scan`, `trending-weekly.yml::scan`.
- Added `tests/test_workflows_timeout_minutes.py` — 16 new tests
  (1 smoke + 5 jobs × 3 parametrized invariants: present, integer,
  in band `[1, 30]`).

**Why this work, this session:** eleventh and final hop in the
portfolio-wide `timeout-minutes` silent-rot propagation arc. This file
is the **inverse safety net** to the audit-side fingerprint shipped in
#36 (`audit_phase_a.py --check missing-timeout`) — both layers protect
the same invariant at two cadences. The audit catches portfolio-wide
drift post-deploy (weekly cron); this lock catches regressions at
PR-test time before merge, with a loud local failure that names the
offending job. The two-layer pattern is symmetric with the silent-CI
arc that landed earlier this year (`test_workflows_yaml_parseable.py`
#30/#31 pre-merge + `audit_phase_a.py --check phantom-ci` #32
post-deploy).

**Open questions / blockers:** none. Test count 121 → 137 (+16,
no regressions). Audit reads from GitHub API which still shows the
pre-merge workflow file shape; post-merge re-run will report clean for
`missing-timeout` (the existing `stale-schedule` on `trending-daily`
from operator-blocked #17 will remain).

**Next session:** the silent-rot arc now has two complete invariants
each protected by both a pre-merge lock and a post-deploy audit
fingerprint, across all 12 portfolio repos plus this audit-authority
repo. Future silent-rot work should follow this same two-layer shape.
The natural next invariant to add (after #28 closed the unquoted
colon-space outage) is a check that `statusCheckRollup` isn't empty
on a completed-failure run — the exact phantom-CI shape we already
catch in audit but don't yet have a pre-merge lock for.

## 2026-06-18 — Issue #40: missing-concurrency fingerprint
**Duration:** ~25 min · **Branch:** `session/2026-06-18-0346-issue-40`

- Added `check_missing_concurrency(repo, token)` to
  `scripts/audit_phase_a.py` — sixth silent-rot fingerprint, mirrors the
  `check_missing_timeout` shape (#35/#36). Flags workflows without a
  top-level `concurrency:` group.
- Wired into `audit_repo` + `format_finding`; updated the script
  docstring to enumerate 6 fingerprints (was 5).
- Added 6 unit tests via the existing `urlopen` monkeypatch fixture:
  clean / one-missing / two-independent / disabled-skipped /
  pyyaml-missing graceful / format-finding output shape.
- Dogfooded against live API: `portfolio-ops` reports 4
  `missing-concurrency` findings (one per workflow); `ai-app-integration-tests`
  reports 0 (it has the template `concurrency: { group: ..., cancel-in-progress: true }`).

**Why this work, this session:** the immediate next silent-rot
invariant after timeout-minutes. Without a concurrency group, a rapid
push-on-push burns one full CI run per push even though the in-flight
run is immediately superseded. **Audit-side only this PR** — per-repo
lock-test propagation is deferred to subsequent sessions to avoid
stacking 12 new PRs on top of the just-shipped 11-PR timeout-minutes
campaign (PRs #38–#44 + 5 more). Same architectural decision as #35:
audit fingerprint first as the cross-repo post-deploy net, per-repo
locks follow when there's bandwidth.

**Open questions / blockers:** none. Test count 121 → 127 (+6 new on
this branch; will integrate to ~143 once PR #38 also lands).

**Next session:** audit will now surface every unprotected workflow
weekly. Decide whether to start propagating the concurrency lock pattern
per-repo (same shape as timeout-minutes: 12 small PRs) or whether to
keep the audit-side fingerprint as sufficient for now.

## 2026-06-18 — Issue #42: concurrency guard + lock test (final hop)
**Duration:** ~12 min · **Branch:** `session/2026-06-18-1539-issue-42`

- Added top-level `concurrency:` to all 4 workflows here with distinct
  groups (`tests-${{ github.ref }}`, `audit-cron-${{ github.ref }}`,
  `trending-daily-${{ github.ref }}`, `trending-weekly-${{ github.ref }}`)
  so they don't cancel each other when triggers coincide.
- Copied lock test from llm-eval-harness; docstring origin updated.

**Why this work, this session:** twelfth and final per-repo hop in the
concurrency-lock propagation arc this session. portfolio-ops is the
audit source-of-truth — `scripts/audit_phase_a.py --check
missing-concurrency` from #41 (last night) surfaces every workflow
missing the lock. After this merges, the audit reports zero
`missing-concurrency` findings across all 13 repos. Arc closed.

**Open questions / blockers:** none. Test count 143 → 156.

**Next session:** address pyyaml install gap in `audit-cron.yml` (filed
as separate followup); audit-cron currently degrades gracefully with a
stderr note when pyyaml is unavailable, but should install it.

## 2026-06-18 — Issue #44: audit-cron pyyaml install gap closed
**Duration:** ~20 min · **Branch:** session/2026-06-18-1910-issue-44

- Added an explicit `python -m pip install --quiet pyyaml` step to
  `.github/workflows/audit-cron.yml`'s `audit` job before the audit
  step. The `missing-timeout` (#35) and `missing-concurrency` (#41)
  fingerprints in `scripts/audit_phase_a.py` lazy-import pyyaml and
  no-op silently when it's absent, so without this install the weekly
  cron only ran four of the six checks.
- Locked the install via
  `tests/test_audit_cron_workflow.py::test_pyyaml_installed`, which
  asserts both the presence of the `pip install pyyaml` step and its
  ordering relative to the `id: audit` step — either drop or reorder
  fails loudly with a one-line explanation.
- Added `scripts/README.md` (new) with operator-local-runner setup
  notes (GH_TOKEN bump, pyyaml install, smoke-test command) plus a
  table of the four scripts. Added `scripts/requirements.txt` pinning
  pyyaml>=6.0 so the local install is one line.
- Updated the `audit_phase_a.py` module docstring to call out pyyaml as
  the hard dep for the two yaml-dependent checks, document the lazy-
  import + graceful-degradation pattern and why it's intentional, and
  name the two places pyyaml is guaranteed (audit-cron + tests.yml).

**Why this work, this session:** Surfaced fresh in this session's
Phase A local-audit pass — both `mcp-server-cookbook` and
`portfolio-ops` initially hit rate limits; the GH_TOKEN-retry for
those two showed the "skipping <check>: pyyaml not installed" stderr
notes for portfolio-ops, confirming the gap on the local runner. The
audit-cron workflow had the same gap latent on the weekly cron since
shipping in #34 and would have hit it the first time pyyaml-dependent
findings appeared.

**Open questions / blockers:** none. Test count 157 → 158.

**Next session:** the silent-rot audit-side arc is now functionally
complete on cron. The 13-repo PR-side propagation of yaml-parseability
(#30/#31) and timeout-minutes (#37) locks are both at 12/12; the
concurrency lock just hit 12/12 too with this session's Phase A merges.
A possible next step is to propagate a per-repo concurrency audit-side
fingerprint lock test (mirror of timeout-minutes), but the validation
arc is saturated per multiple prior session memos — likely better to
pivot to real engineering on a priority-tier repo.

## 2026-06-18 — Issue #46: SESSION_PROMPT.md audit step — six fingerprints + pyyaml ensure
**Duration:** ~25 min · **Branch:** `session/2026-06-18-2313-issue-46`

- Updated `session-runner/SESSION_PROMPT.md` step 4 to name all six silent-rot fingerprints (paired-failure, stuck-registration, stale-schedule, phantom-ci, missing-timeout, missing-concurrency). The description had been stuck at the original three since PR #28 added phantom-ci on 2026-06-17, leaving every session prompt-reader miscounting expected coverage.
- Added an idempotent pyyaml ensure to the bash one-liner — `python3 -c 'import yaml' 2>/dev/null || python3 -m pip install --quiet pyyaml` — so the two yaml-dependent fingerprints run at full capacity on the session-runner path. Sibling to PR #45's audit-cron install: two-layer install guarantee now covers both the weekly cron path and the per-session local path.
- Extended `tests/test_session_prompt_phase_a_audit.py` with a `FINGERPRINTS` tuple plus two new tests: a parametrized `test_audit_section_lists_fingerprint` that fails per-fingerprint when names disappear, and `test_audit_section_pyyaml_ensure` that requires both `import yaml` and `pyyaml` to appear in the audit section. Test count 157 → 164 (+7).

**Why this work, this session:** Surfaced directly during this session's Phase A step 4 — read "three silent-rot fingerprints" in the prompt, then watched the audit return `skipping missing-timeout for portfolio-ops: pyyaml not installed` and `skipping missing-concurrency for portfolio-ops: pyyaml not installed`. The prompt was actively misleading about coverage AND the local audit was running at 4-of-6 capacity. Both shapes are exactly what the lock test should have caught, so this PR is both the fix and the inverse safety net for the next drift.

**Open questions / blockers:** none.

**Next session:** Phase A audit caps are now lock-tested against the script's docstring fingerprint list. When a seventh fingerprint lands, the per-fingerprint test will fail loudly until both `FINGERPRINTS` in the lock test and the prompt description are extended. The validation arc on the audit step is now genuinely saturated — pivot to real engineering on a priority-tier repo next.

## 2026-06-18 — Issue #48: SESSION_PROMPT.md audit — export GH_TOKEN before the loop
**Duration:** ~15 min · **Branch:** `session/2026-06-18-2318-issue-48`

- Added an idempotent `export GH_TOKEN="${GH_TOKEN:-$(gh auth token 2>/dev/null)}"` to `session-runner/SESSION_PROMPT.md` step 4, between the pyyaml ensure (#46/#47) and the per-repo audit loop. Pre-set GH_TOKEN wins; missing `gh` silently no-ops. Bumps the audit's per-session GitHub API budget from 60 to 5000 req/h.
- Extended the rationale paragraph with one sentence crediting PR #45 as the local-operator sibling and naming the rate-limit mechanism.
- Added `test_audit_section_exports_gh_token` to the lock test — loose-text match requiring both `GH_TOKEN` and `gh auth token` substrings in the audit section. Same shape as `test_audit_section_pyyaml_ensure` from #46. Test count 164 → 165.

**Why this work, this session:** Same dogfood pattern as #46 — surfaced directly during this session's Phase A step 4. Two of 13 repos (`mcp-server-cookbook`, `portfolio-ops`) returned `HTTP 403 rate limit exceeded` on the unauth path. The two unscanned repos happened to include the one with the only real finding (`portfolio-ops` / `trending-daily` stale-schedule from #17), so a real silent-rot signal was hidden behind a self-inflicted rate-limit. Manual retry with `GH_TOKEN=$(gh auth token)` worked, which proved the fix; this PR makes that automatic.

**Open questions / blockers:** none.

**Next session:** Phase A audit step now has three lockstep guards in SESSION_PROMPT.md — six-fingerprint name list (#46), pyyaml ensure (#46), GH_TOKEN export (#48). The audit step itself is genuinely saturated; pivot to non-audit work on a priority-tier repo.

## 2026-06-18 — Issue #50: audit-cron.yml env.GH_TOKEN lock — cron-path sibling to #48/#49
**Duration:** ~10 min · **Branch:** `session/2026-06-18-2324-issue-50`

- Extended `tests/test_audit_cron_workflow.py` with `test_audit_step_has_gh_token_env`. The workflow already declared `env: GH_TOKEN: ${{ github.token }}` on the audit step (line 52) but no lock test covered it — drop the env block and the audit script's urllib.request calls fall back to unauth (60 req/h), same shape that hit the session-runner path in #48 and got locked in PR #49.
- Dogfood: sed-and-restore the env block locally; the new test failed with the documented pointer to PR #49 and PR #45, including the empty-env value in the message.
- Test count: 165 → 166.

**Why this work, this session:** Audit-side symmetry. The pyyaml install was already protected at two layers (cron path #45 + session-runner path #47). The GH_TOKEN guard was only protected at the session-runner layer (just-shipped PR #49). This PR closes the cron-path lock gap so any future env-block regression on either path fails CI loudly.

**Open questions / blockers:** none.

**Next session:** Phase A audit two-layer install guarantee is now complete: pyyaml at two layers (#45, #47), GH_TOKEN at two layers (#49, #51), six-fingerprint name list at one layer (#47, the only one needed since the script docstring is authoritative). Audit-side lock arc is genuinely saturated. Pivot to a non-audit, non-portfolio-ops repo for substantive engineering next time.

## 2026-06-19 — Issue #52: SESSION_PROMPT.md pyyaml install — PEP 668 escape hatch for local operator path
**Duration:** ~35 min · **Branch:** `session/2026-06-19-issue-52`

- Phase A dogfood: `python3 -m pip install --quiet pyyaml` aborted on jt's local Mac (Homebrew Python) with `error: externally-managed-environment`. The import-check at the top of the audit prelude fell through, the install failed silently, then `audit_phase_a.py` reported `skipping missing-timeout for portfolio-ops: pyyaml not installed` and the same for `missing-concurrency` — defeating the two-layer install guarantee just shipped in #45/#47.
- Patched `session-runner/SESSION_PROMPT.md` line 51 to a three-branch fallback chain: import-check → plain `pip install` (venvs / CI / non-PEP-668) → `pip install --break-system-packages --user` (the documented PEP 668 escape hatch for Homebrew Python on macOS; `--user` is required because plain `--break-system-packages` would try to write to brew's site-packages and fail on permission). Updated the Rationale paragraph to call out the three-layer install guarantee completion.
- Added lock test `test_audit_section_handles_pep_668` — loose substring match on `--break-system-packages` in the audit section, same shape as `test_audit_section_pyyaml_ensure` (#46) and `test_audit_section_exports_gh_token` (#48). Drop the escape hatch and CI fails with a pointer back to #52.
- Dogfood post-fix: uninstalled pyyaml, ran the new three-branch chain verbatim from SESSION_PROMPT.md — third branch installed pyyaml 6.0.3 to user site-packages, re-ran the audit, zero `skipping` stderr lines, only the known operator-blocked `stale-schedule` finding for #17.
- Test count: 166 → 167.

**Why this work, this session:** Direct dogfood evidence in the Phase A audit step. Same pattern as #46/#48/#50 — file an issue from concrete in-session evidence, close it in the same session with the lock-test inverse-safety-net. Substantive work in an otherwise saturated portfolio state (every other repo had zero open priority:high/med issues at session start).

**Open questions / blockers:** none.

**Next session:** Audit-side install guarantee is now three-layer (cron #45 + session-runner pyyaml-ensure #47 + PEP 668 escape #52). Continue the multi-issue loop on a non-portfolio-ops repo per the night-session "pivot to substantive engineering" note from #50.

## 2026-07-04 — Issue #55: verified & closed the systemic symbol-resolution doc-lock propagation
**Duration:** ~10 min · **Branch:** `session/2026-07-04-issue-55-close` (memory-only)

- Phase A this DAY run merged two ready PRs (agent-orchestration-platform #90 GFM pipe-escaping; chunking-strategies-lab #107 inverted validation message), both CI-green with sensible diffs. Silent-rot audit was clean on 12 repos; the one finding (portfolio-ops trending-daily, 8 consecutive failures) is the already-tracked JT-blocked `ANTHROPIC_API_KEY` issue (#17, dup #56) — no new issue filed.
- Independently verified #55's completion before closing rather than trusting the status tables: grepped every repo's architecture-doc test after pulling `main`. All 8 Python repos carry `test_doc_symbol_refs_resolve` (+ injected-drift inverse); all 4 TS repos carry a symbol/tool-resolution axis (nextjs #77, mcp-server-cookbook tool-names #83, ai-app #73, agent-orchestration-platform #88 — all merged). Closed #55 as completed; count-claim locking was an explicit non-goal and stays manual.

**Why this work, this session:** #55 was the only actionable, non-JT-blocked open issue across the portfolio at run start (all `priority:high` empty; both `priority:med` are JT-blocked decision-revisits). Its remediation had fully landed, so verify-and-close was the correct action.

**Open questions / blockers:** none.

**Next session:** Portfolio deeply saturated; this run also fixed prompt-regression-suite #105 (warn-band gate collapse) via a non-tier dogfood hunt round.

## 2026-07-04 — DAY session (Phase A + llm-cost-optimizer #97)

**Phase A:** Merged 2 clean ready PRs — prompt-regression-suite #106 (warn_band==threshold gate-collapse fix) and portfolio-ops #57 (memory). Silent-rot audit clean across 12 repos; the one finding (portfolio-ops `trending-daily` 8 consecutive failures) is the known JT-blocked #17/#56 (ANTHROPIC_API_KEY secret never configured) — no new issue.

**Substantive work:** Resolved llm-cost-optimizer #97 (a decision-revisit): the batch idempotency payload hash was order-sensitive, so resubmitting the same batch in a different order raised a spurious `IdempotencyConflict`. Since the Batch API correlates results by `custom_id` (not row position), a reordered identical batch is the same workload. Made the hash order-independent (sort by `custom_id`), recorded D-013, shipped as **draft** PR #124 for JT to confirm the semantics before merge.

**Saturation:** Ran 12 core-module bug-hunts across the three flagship priority-tier repos plus chunking-strategies-lab — zero real bugs. The flagship core is exhausted; future value in the saturated state comes from resolving filed `decision-revisit` issues (the objectively-correct ones), not from re-hunting core modules. Left vector-search-at-scale #71 for JT — its two resolutions produce different published recall curves (a benchmark-integrity decision).

**Next session:** scan open decision-revisits first; remaining other open issues are demo/GIF captures (#18, #16×2) that need screen capture, not headless work.

## 2026-07-05 (night) — Phase-A pass + 4 dogfood-hunt fixes across 4 repos

**Phase A.** PR review pass found all open PRs were drafts (demo-capture GIF work + llm-cost-optimizer #124 held for JT on D-013), nothing auto-mergeable. Silent-rot audit clean across 12 repos; the one finding (portfolio-ops trending-daily stale-schedule, 8 failures) is the known JT-blocked #17 (dup #56). The priority tier is exhausted of actionable non-media work — three of the five tier repos have zero open issues, and the rest are demo/media captures not runnable headless.

**Work.** In this saturated state I ran three waves of parallel dogfood bug-hunt agents across the not-yet-saturated repos, verifying every finding firsthand before fixing. Shipped and merged four fixes, each its own issue/branch/PR/memory commit: vector-search-at-scale #76 (GFM pipe-escape in `cost_table`), embedding-model-shootout #83 (phantom column in `aggregate_markdown` when `recall_at_k` is empty), agent-orchestration-platform #91 (`read_file_at_ref` gave up on all fixtures after a non-added match), and mcp-server-cookbook #84 (non-atomic `write_file` in the Python sandbox — TS-parity atomic write). All four PRs went green and were squash-merged.

**Rejected findings (5).** mcp sqlGuard underscore-boundary (deliberate — keeps `last_vacuum`/`last_analyze` queryable), prompt-regression `len(w) > 3` hint filter (intentional stopword guard), python-async-llm-pipelines (clean), ai-app-integration-tests (clean), nextjs checkpoint-stream resume leading-space (correct by design for seamless join). The entire third wave (lco cache/routing, rag telemetry/streaming, chunking boundaries) came back empty, confirming flagship non-core modules are saturated too — the stop signal. Hunt yield: 4 real fixes of 12 hunts (~33%, at baseline).

## 2026-07-06 — Phase A + CI-coverage-gap lens (2 fixes)
**Type:** DAY session · multi-issue loop

Phase A: no ready PRs (all open PRs are drafts — demo GIF captures + lco#124 held for JT on D-013). Silent-rot audit clean across 12 repos; the one portfolio-ops trending-daily stale-schedule finding is the known JT-blocked #17 (Anthropic API key never configured) — no new issue.

The static issue queue was exhausted (every remaining open issue is a JT-gated decision-revisit or a headless-unfriendly demo capture), so work came from a new objective lens: **CI-coverage gaps** — a shipped test suite with no CI job. It yielded two real fixes, both in multi-language repos with a second stack not wired into CI:
- **mcp-server-cookbook #90** — the `filesystem-sandbox-py` Python parity server (74 pytest tests) had no CI job; added one (3.11/3.12 matrix, ruff + pytest). PR #93 merged.
- **rag-production-kit #120** (filed this run) — the `demo/nextjs` Vitest suite (13 tests) never ran in CI (Python-only jobs); added a `nextjs-demo` job (node 20, typecheck + vitest). PR #121 merged.

A second lens (broken internal references in README/docs) came up empty across all 12 repos — the only hits were intentional deferred-generation report placeholders (per §10). Stopped cleanly at 2 issues, within the DAY target.

**Next session:** CI-coverage lens is swept (don't re-sweep). Remaining issues are all JT-gated or headless demo captures. Portfolio saturated.

## 2026-07-10 (night) — Phase-A roll-up: 7 PR merges + 3 hits + 1 decision-revisit

**Duration:** ~3h · **Branches:** per-repo `session/2026-07-10-*`

**Phase A.** Merged 7 ready PRs from the prior night run (rag#137, leh#163, prs#118, pyasync#79, ems#92, lco#139, mcp#105) — all green, different repos, no sibling conflicts. Silent-rot audit clean across 12 repos except the known JT-blocked `trending-daily` stale-schedule finding (dup #56).

**Work loop (3 hits, all via the sibling-incomplete-fix meta-lens on the just-merged surface, each verified firsthand before filing):**
1. **lco#141 (issue 140)** — `_extract_first_token_logprobs` guarded None (#106) and non-finite (#95) but both `float()` coercion sites crashed on a *present-but-non-numeric* logprob element off an adapter-set/BYO distribution, aborting `route()`. Exact sibling of the just-merged #138/#139 (non-numeric judge score). Wrapped both in `try/except → abstain`.
2. **mcp#107 (issue 106)** — the postgres-readonly guard blocked file-*read* (`pg_read_file`) and `lo_export` (#94) but missed the adminpack file-*mutation* family (`pg_file_write/unlink/rename/sync`), all confirmed `ALLOW` firsthand. Added `PG_FILE_` prefix + `pg_signal_backend`/`pg_promote`/`pg_wal_replay_*` keywords. README count 126→135.
3. **prs#120 (issue 119)** — `diff_response`'s bare-`ValueError` range guards on `--threshold`/`--warn-band` escaped the CLI's typed-only `except` tuple → raw traceback exit 1 instead of the documented exit 2. Sibling of the just-merged #117/#118. Added a `_validate_thresholds` CLI-entry helper.

**Decision-revisit (not shipped): nextjs#82** — the partial-json parser drops a started-pair inner container, losing the parent key/element (non-monotonic flicker, reachable in the shipped demo). Built and firsthand-verified a fix (remove the `frameSnapshot` pop loop) — but it fails the *explicit named `#72 guard`* tests, i.e. it overturns a deliberate prior decision. Per the handoff (§1.5), reverted the code (tree untouched, 57/57 green) and reclassified #82 as a `decision-revisit` for JT (position A: surface `{}` consistently, recommended; B: also drop the empty `{`).

**Saturation.** Hunted every repo — 7 parallel agent hunts (pyasync, leh, prs, mcp, vsas, aop, nextjs, fs-sandbox) + 15+ firsthand checks (rag telemetry/citation/reranker/rewriter/db, chunking, lco router/pricing/batch/semantic_cache, ems, leh run/diff CLI) — all saturated except the 3 hits. Stopped at 3 hits + 1 decision-revisit (below the 5-9 night target) because the portfolio is decisively saturated; forcing more would be churn over the quality bar. This run's 3 PRs become the next run's freshest sibling-hunt surface.

## 2026-07-15 (night) — Phase A merges + 6 hits via sibling-incomplete-fix

Merged 7 ready PRs from the prior run (aiapp#91, rag#153, lco#157, vsas#106,
ems#106, chunking#131, nextjs#86), all green, different repos. Audit clean across
12 repos (the one portfolio-ops trending-daily stale-schedule finding is the known
JT-blocked one). Static priority:high queue is globally empty as usual, so all work
came from the sibling-incomplete-fix meta-lens on the freshly-merged diffs.

Shipped 6 PRs, all verified firsthand before filing:
- rag#154 — "etc." (the most common sentence-ending abbreviation) was an
  unconditional non-boundary, bypassing citation enforcement (sibling of the
  ms/no/a.m. wave).
- chunking#132 — the embedder_name header cell in _render_summary lacked the
  newline-collapse its sibling strategy_name row cell got in #130.
- leh#178 — @pytest.mark.eval(threshold=False) disabled the eval gate because
  bool is an int subclass and slipped past the #154 range guard.
- mcp#126 — pg_truncate_visibility_map (a real pg_visibility mutator) was missing
  from the postgres-readonly denylist (sibling of the #110 storage-maintenance class).
- nextjs#87 — the error-recovery docstring documented the error event as {reason}
  but the drop path sends {reason, last_token} that the client depends on.
- lco#158 — a second-order cross-repo find off leh#178: the same bool-is-int-subclass
  gap in the router/semantic-cache config validators.

New reusable lens: bool-is-an-int-subclass. Any repo that added isinstance(int,float)
first to reject str/None config systematically misses bool (which passes that check
and coerces in-range). Swept portfolio-wide — lco was the only gap; everything else
was already bool-guarded or has no such seam.

4 of 8 hunt agents returned SATURATED (pyasync, ems, prs, aop). Two process notes:
mcp and nextjs agents tried to prettier-reformat repos whose CI has no prettier — I
reverted that churn and kept minimal hand diffs. Stopped at 6 (within the 5-9 night
target) at decisive saturation across every known lens.

## 2026-08-03 — Issue #63: the audit can only see rot that turns something red

All six existing fingerprints key off GitHub Actions run history — paired runs,
stuck registrations, stale schedules, phantom runs, missing timeouts, missing
concurrency. That is the right net for rot that shows up as failed runs. It is
structurally blind to the opposite shape, and this session ran headfirst into
it.

`mcp-server-cookbook/servers/filesystem-sandbox-py` declared `[tool.ruff]` with
no `[tool.ruff.lint] select`, so it inherited whatever ruff's default rule
selection happened to be, and CI installs ruff unpinned. Same tree: 0.15.13
passes, 0.16.1 finds 8 errors. The audit called that repo clean every session
and was *right* to — `main` is genuinely green, because nothing had been pushed
since before 0.16.1 landed. There were no failed runs to fingerprint. The repo
was simply one push away from red.

That also settles the follow-up floated on 2026-07-31 about adding a "main
branch is red" check. It would not have caught this. The branch is green. The
defect is that what CI enforces is a property of the tool's release calendar
rather than of the repo.

The new `unpinned-lint-config` fingerprint flags any `pyproject.toml` that
configures ruff without stating its rule set. Discovery is a recursive tree walk
rather than a root probe — root-only enumeration is precisely why the six-repo
sweep on 2026-07-31 never looked at this repo, whose only Python package sits
two directories down in a TS-first project. It is stdlib-only (`tomllib`), so it
joins the tier that runs without pyyaml.

It is deliberately narrow. The tempting broader version — flag every unpinned
dev dependency — fires on all nine Python packages every session until #62 is
decided, and an audit line the operator learns to skim past is worse than no
line at all. Verified against all 13 live repos: exactly one finding, the one
mcp-server-cookbook#133 fixes, so it goes quiet on that merge.

One thing worth generalising. The session-prompt lock's `FINGERPRINTS` tuple
carried a comment asking the next author to remember to update it. History shows
that request was ignored three times — phantom-ci, missing-timeout and
missing-concurrency all landed without it, and #46 had to backfill all three at
once. So a comment asking someone to remember is really a bug report about a
missing test. Replaced it with one that derives the set from the script's
`check_*` functions; it caught this PR's own prompt update while I was writing
it.

Also worth recording for #62: a fresh-venv install-and-test sweep across all
eight Python repos with the latest dependencies came back entirely green, so the
dependency-drift lens is exhausted outside mcp. And the portfolio splits clean
down the middle — the four TS repos install via `npm ci` against committed
lockfiles, while the nine Python packages run `pip install -e '.[dev]'` with
nothing pinned. #62 is less "should we pin ruff" than "the Python half has no
lockfile equivalent and the JS half has had one all along."

Shipped as PR #64.

## 2026-08-20 — night run: 11 merges, 8 issues across 8 repos

**Phase A** merged eleven PRs. Ten went straight through. The eleventh,
`agent-orchestration-platform#121`, arrived `MERGEABLE`/`CLEAN` with every check
green and a diff that read `Binary files a/src/eval/score.ts and b/... differ`.
The tie-break key from #120 used U+0000 as its separator and had been committed
as a *literal* NUL; git treats any blob with a NUL in its first 8000 bytes as
binary, so the one file whose ordering semantics were the entire point of the PR
had no reviewable diff, no blame, and no three-way merge. Nothing in the
toolchain could have caught it — the *string* is identical either way, so tsc,
vitest and lint are structurally blind. Green CI plus MERGEABLE/CLEAN is not a
reviewable diff. I swept all eleven open PRs for control bytes before touching
it; only that file hit, and notably `mcp-server-cookbook#140` — a PR entirely
*about* control-character trim parity — came back clean, because it built every
character from a codepoint.

**Two lenses dominated the eight issues.**

The first: *a default that lands at an extreme of a comparison is not a neutral
default.* It paid three times. `chunking-strategies-lab#160` published `0.000`
for a measurement never taken, so a strategy that really scored recall@5 = 0.90
rendered as zero on every column. `embedding-model-shootout#123` made `0.0` the
worst value on the Pareto quality axis, so a 0.97-recall model was dominated by
a 0.12-recall one and dropped from the published frontier.
`ai-app-integration-tests#99` scored two empty token sets as 1.0, so an empty
model response *passed* a semantic assertion. The question that finds all three:
where in the comparison's range does the default sit?

The second: *a sort or selection with no tiebreak*, three more times —
`llm-eval-harness#206`, `llm-cost-optimizer#188`, `rag-production-kit#180`. The
distinction that mattered each time was content versus position: a tiebreak on a
rowid or a scan index removes the dependence on the iteration mechanism but not
on the write order, which is the actual defect. And there's a reachability tell
worth reusing — `utc_now_iso()` returned one distinct value across 2000
back-to-back calls, and six consecutive real `run_suite()` calls all landed on
one second. Measure the timestamp resolution before deciding a tie is exotic.

**A method that paid twice in one run:** after shipping a fix, grep the whole
portfolio for the pattern you just fixed. A `.get(<key>, 0)` sweep returned four
more sites in `embedding-model-shootout`'s plot renderer and the stdout line in
`chunking-strategies-lab`'s runner — both in PRs I had just opened. Second
passes shipped to both. The judgement that goes with it: the plot sites were
already unreachable, but only by call order, and a guarantee that depends on
statement order is not a guarantee. The chunking one was unreachable too, and I
fixed it anyway while pinning the invariant with a test, so the direct index is
provably safe rather than assumed safe.

**The honesty case of the run** was `embedding-model-shootout#123`. A
pre-existing test had *named and asserted* the behaviour I filed as a defect. I
didn't know when I filed, and running the whole suite rather than just my new
file is what surfaced it. I posted a correction on the issue, gave the reasoning
for overriding it, named the defensible opposite reading, said it's cheap to
revert, and rewrote the test in place with the old expectation verbatim in its
docstring. A test that pins observed behaviour isn't the same as a decision —
but the distinction has to be argued, not assumed.

**Two things I declined to file.** `python-async-llm-pipelines`'s
`docs_per_second` falls back to `0.0` where `attach_speedup` sixty lines later
uses `None` for the identical undefined division — and that function's comment
argues against `0.0` explicitly. But I measured `elapsed == 0` as unreachable: 0
of 8000 runs, even with a do-nothing pipeline and an empty doc list. A dead
branch isn't worth a `priority:high` issue, and padding the count would be worse
than stopping at eight. Same call on an `?? 0` in `agent-orchestration-platform`
that only feeds a log line.

**Two thorough empty hunts**, both in `vector-search-at-scale`: exact cosine ties
at the top-k boundary are unreachable with the shipped Gaussian corpus (zero
across five workload shapes × 200 queries, minimum boundary gap ~300 ulp above
float32 noise), and `_percentile` matches numpy's linear method exactly across
thirty cases.

All eight PRs were left ready, mergeable and fully green, one per repo — so no
same-repo MEMORY conflicts next Phase A. The `aop` two-PR conflict the previous
run warned about materialized exactly as predicted and was resolved by serial
rebase keeping both append-only blocks.

**Process note, third run running:** I believed 200 minutes had passed when 79
had. Reading `date` instead of estimating is why the last four issues happened
at all.

---

## 2026-08-24 (night) — 8 Phase-A merges, 12 issues closed across 11 repos

**Phase A.** All eight ready PRs from the 2026-08-21 run merged clean — one per
repo again, so no MEMORY conflicts, which is the fourth consecutive run that
prediction has held. The seven-fingerprint audit came back 12-of-13 clean, with
the one known finding unchanged since 2026-08-12: `portfolio-ops`'
`trending-daily` workflow has 8 consecutive failures because `ANTHROPIC_API_KEY`
was never configured. That is JT-blocked and no new issue was filed.

**The method that dominated the run.** Sweeping the portfolio for a
just-shipped pattern produced **four whole issues from one grep**. `nextjs#104`
turned up `process.env.X ?? "default"` failing to default a *set-but-empty*
string; running that same grep across the four TypeScript repos produced
`ai-app-integration-tests#101`, `mcp-server-cookbook#145` and
`agent-orchestration-platform#124`. Third run running that this has been the
highest-yield method I have.

**But the sharper form of the lens isn't the grep.** It is: *enumerate every
site the rule applies to and diff their conventions.* In every case the defect
was the minority spelling:

- `aop` had four env reads and three conventions — two already correct.
- `pyasync`'s `Workload` had four fields; three rejected `bool`, and the fourth
  was the one the published benchmark numbers are built on.
- `ai-app-integration-tests` had two readers of one env var disagreeing on **8
  of 13** values, every disagreement in the unsafe direction.

The tightest instance was one line apart inside one function: `aop`'s
`resolveToken` does `if (opts.token)` (truthy, correct) and then
`process.env.GITHUB_TOKEN ?? process.env.GH_TOKEN` (nullish, wrong).

**A comment that enumerates hazards is a checklist.** Three findings came from
ticking one off field by field. `pyasync#96`'s comment says "bool subclasses int
and flattens operator intent" and names the harm for the one field it skipped.
`rag#184`'s finiteness sweep covered three of four floats and missed `ts` — the
key every read path filters and orders on. `prs#147`'s guard was *literally*
conditioned on one branch of its own function.

**Three things worth carrying forward as new rules.**

*The same harm by a quieter road.* `prs#147`: the float branch emitted a bare
`Infinity` token — invalid JSON, so a decoder rejects loudly. The integer branch
emitted **valid** JSON that `JSON.parse`, `jq` and most Go/Rust `float64`
decoders turn into `Infinity` with no error at all. When you find a
non-finite-at-egress fix, ask whether a large *finite* value reaches the same
place through the consumer's double conversion.

*A SQLite column type is not a constraint.* `rag#184`: `ts REAL NOT NULL` stored
the string `"2026-08-24"` — `typeof(ts)` came back `text`, because affinity is a
preference. TEXT sorts above every REAL, so it sat in **every** `last_24h()`
window forever and round-tripped out as a `str` in a `float`-annotated field.

*When a package boundary forbids sharing a rule, lock the mirror by executing
both.* `aiapp#101`: `example-app/` has its own `package.json`, so the rule lives
twice and a parity test runs both over a 24-value matrix — a differential test,
not a text comparison. Verified by deleting `"live"` from the mirror: 4 of 26
parity tests failed. And the parity test needs its own anti-vacuous guard,
because a parity assertion over a tiny matrix proves nothing.

**Two process mistakes, one of them new.** In `ems` I ran the anti-vacuous
revert *before* committing and `git checkout --` discarded the uncommitted fix;
that rule is already in my notes and I still slipped on the eighth issue. The new
one is better: in `mcp#145`, `test/repo-stats-readme.test.ts` computes its
expected counts from `git ls-files`, so my new test file was **invisible to it
while untracked** and counted the moment it was committed. The suite passed
locally and failed on CI. "Suite green before `git add`" is not the same
statement as "suite green".

**A negative result worth recording.** I swept all eight Python repos for
`os.environ.get` / `os.getenv`, looking for the Python analogue of the `??`
class. Every site uses `or`, which treats `""` as falsy correctly. The Python
half of the portfolio is clean on that class.

**Three decisions recorded**, and the interesting part is that two of them
deliberately *don't* inherit their siblings' rationale. `llm-eval-harness`
**D-017** decides that the all-zero `hash_embed` vector means *uncomparable* —
rejecting on the authored golden side, counting on the sampled candidate side.
`chunking-strategies-lab` **D-013** and `prompt-regression-suite` **D-009** both
adopt the non-strict mypy gate, mirroring `llm-eval-harness` D-016 and
`llm-cost-optimizer` D-014 *in shape but not in rationale*: those two justify
theirs by shipping a `py.typed` marker, and neither of these repos does. The case
in both is latent-green rot. When copying a sibling repo's decision, check
whether its rationale transfers or only its config.

**Untouched:** `vector-search-at-scale` only. Both its open issues are JT-gated
decision-revisits (#71, #78) and it had two thorough empty hunts on 2026-08-20.
I stopped rather than force a thirteenth issue.

## 2026-08-25 — the MEMORY conflict resolver was erasing `decisions_made` (#65)

**What got done.** `resolve_memory_conflict.py` hardcoded the trailer it reattaches
to the first block as `decisions_made: []` + `followups: []`. Git hoists the two
blocks' common suffix out of a conflict region line by line, so that literal is
the whole trailer only when *both* sessions recorded nothing. When one recorded a
decision, only `followups: []` is common — `decisions_made:` differs and stays
inside the region, still attached to block A — so the hardcoded pair landed on top
of a real one, producing a duplicate key. `yaml.safe_load` keeps the last
duplicate, so the recorded decision read as `[]`, and the tool printed `resolved:`
and exited 0.

**How it was found.** Phase A of this same run hit a MEMORY rebase conflict and I
resolved it by hand. The repo ships a tool for exactly that, so afterwards I went
back and ran it against the shape. Running the shipped tool on the situation you
just had by hand is a cheap, repeatable lens.

**How often the precondition was false.** Of the ten session entries written
tonight, seven had a non-empty trailer. The tool was correct on the three sessions
that recorded nothing and destroyed the record on the seven that recorded
something — it failed precisely on the entries worth writing down.

**Why the existing tests missed it, in their own words.** `Fixtures here are
hand-rolled minimal shapes — no real repo state required.` A hand-rolled fixture
is written to match the shape the code expects, so it can never discover a shape
git actually produces. Every case in the new file is built with `git init`, two
branches and a real `git rebase`.

**The guard is worth more than the fix.** `check_block_shape` refuses to write
when any block has other than exactly one `decisions_made:` and one `followups:`.
`_process` already refused to write a file with conflict markers left in it; a
file that *looks* well-formed but silently lost data is the same class of failure,
and worse, because it parses. Reverting the fix alone turns 6 tests red; reverting
the fix *and* the guard turns 4 red — so the guard catches two cases nothing else
would.

**A second defect my own test found.** The YAML round-trip assertion failed on
`followups: [#107]`: `#` starts a comment in YAML, so the flow sequence is
unterminated. Measured across the portfolio, 74 of 936 session blocks fail
`yaml.safe_load`, 71 of them for exactly this reason, in all thirteen repos. Filed
as #66. The case is excluded from the round-trip test *with the reason stated and
pinned*, rather than papered over.

**Drive-by, same file.** `scripts/README.md` said the audit ships "Six"
fingerprints; it ships seven. Corrected, and called out in the PR rather than
smuggled in.

**Tests.** 16 new, all built from real git conflicts. Suite 179 → 195 green.

## 2026-08-25 — the new guard was too strict, twice (#65 follow-up)

**What happened.** I shipped `check_block_shape` and then ran it against the
portfolio's real history, where it was wrong twice.

First, "every block has exactly one trailer key" refused to write a live file:
a 2026-08-19 block in `agent-orchestration-platform`, and one in portfolio-ops
itself, have no `decisions_made:` line at all. Absence is a pre-existing shape
this tool never created, and only duplication loses data.

Then the absolute `> 1` check refused for a different reason: two *other* blocks
— this repo's 2026-05-27T15:25Z and `prompt-regression-suite`'s 2026-08-07T07:25Z
— are each two session entries fused into one with no `---` between them, so each
carries two `decisions_made:` lines. Those are already-committed instances of the
very class #65 fixes, from before the fix existed. A guard that refuses to operate
on files that already have the damage is useless on exactly the files that need
it, so it now compares against a `before` count and fires only when the resolution
itself introduced duplication.

**The lesson is the one my own test file argues.** Building the fixtures from real
`git rebase` conflicts was the right call and it still missed both of these,
because a freshly-`git init`ed fixture repo has no history to be malformed. Run a
new guard against real data as well as against fixtures.

**It validated itself end to end.** Rebasing this branch onto `main` produced a
genuine append-only MEMORY conflict — and the fixed resolver resolved it
correctly: both session blocks intact, one trailer each, both `yaml.safe_load`-able.
The tool fixed the conflict its own PR created.

**Not repaired here.** The two fused historical blocks are also among the 74
unparseable ones from #66. MEMORY is append-only and repairing history is JT's
call, so they are noted rather than rewritten.

## 2026-08-26 — a ratchet, so the gated half stays open (#66, D-010)

**What got done.** `followups: [#107]` is not valid YAML — `#` begins a comment
when it follows whitespace or opens a token — so the *whole* session block fails
to load. D-010 adopts the quoted form for new blocks, the `portfolio-memory`
skill's schema shows it, and `scripts/check_memory_yaml.py` ratchets the count.

**The issue had two halves and only one was mine.** It said so itself: whether a
mechanical quote-insertion counts as rewriting append-only history "belongs to JT
rather than a session". So I did the going-forward half and built the tool so the
gated half stays open. Worth reading an issue for *which of its acceptance
criteria are yours*.

**The ratchet is the whole design.** A gate demanding zero would have forced the
retro-fix decision by making CI red until someone made it. A baseline freezes the
damage at today's count, so the convention is enforceable tomorrow without
deciding anything about yesterday. When a fix has a gated half, ship a ratchet,
not a gate. That is also `#65`'s follow-up lesson reused one run later, on the
same files: a guard that refuses to operate on already-damaged files is useless
on exactly the files that need it.

**I corrected the issue's own analysis, and posted it there.** `#66` argued for
Option 1 partly because Option 2 "loses the cross-repo form (`leh#212`)". That
form was never broken — YAML starts a comment at `#` only after whitespace or at
token start, so `leh#212` is a plain scalar. Measure the premise of an issue
before implementing its recommendation, even your own.

**The recommendation survived with a different reason.** Quote *every* item, not
only the bare-`#` ones, because "quote a followup only when it starts with `#`"
is correct and unmemorable. A convention written into a skill has to be one a
tired session can apply without thinking; a superset rule with no exceptions
beats a precise one with an exception.

**A test worth reusing.** `test_the_baseline_is_not_vacuous` asserts the
allowance file is neither all-zeros (which would make it a gate) nor huge (which
would make it useless). A committed allowance file has two opposite failure
modes, and both need an assertion — zeroing the baseline turns it red.

**Scope limit, stated.** Only portfolio-ops' own `MEMORY/` is checked in CI,
because it is the only one a portfolio-ops checkout can see. The cross-repo
invocation is a Phase A operator command, documented beside `audit_phase_a.py`.
Enforcing it in all thirteen repos would be twelve more PRs and is not this issue.

**Hygiene.** I created `scripts/__init__.py` for an import, then found it
unnecessary (namespace packages) and deleted it before staging. 224 tests still
green. Check whether a file you added for convenience is actually load-bearing
before committing it.

**Tests.** 27 new; suite 197 → 224 green.

## 2026-08-26 — night run: 13 merges, 13 issues, all thirteen repos

**Phase A.** All thirteen ready PRs from the previous run merged clean — one per
repo, no MEMORY conflicts, for the fifth consecutive run. The audit ran seven
fingerprints over thirteen repos: twelve clean, one known JT-blocked finding
(`trending-daily`, unchanged since 2026-08-12).

**The dominant lens: count the issues per *method* of a protocol and work the one
with zero.** It paid twice. `vector-search-at-scale`'s `Backend` has three
methods — `ingest` got #131 last run, `query` has three issues, and `close` had
none. `llm-cost-optimizer`'s `Storage` has five — `put` had three, `find_nearest`
two, and `invalidate_by_tag` / `purge_expired` / `__len__` had none. A protocol is
exhausted when every method has been enumerated, not when the interesting ones
have. And the smallest method is the one nobody has read: `close` is two to four
lines per adapter, and it answered five different ways, two of them by returning
an empty result list the harness scores as `recall = 0.0` and publishes.

**Second method, sixth run running: sweep the portfolio for a pattern just
shipped.** `rag-production-kit#188` was a dict comprehension transforming only
`v`; grepping all twelve repos for that shape landed on two with the same
`{str(k)}` / `{int(k)}` round trip. One grep, two issues. The sharper question
than the grep is *is the read transform the inverse of the write transform* —
`int()` accepts leading zeros, whitespace, `+`, `_` separators and non-ASCII
decimal digits. `int("٥")` is 5.

**Four new transferable shapes.** An upsert's `DO UPDATE SET` is a subset of its
INSERT column list until someone checks — and the test that *parses the SQL* is
worth more than the three-column fix. A sanitizer can be less robust than the call
it wraps. An index is not the truth: ask what removes a record without telling it,
and whether keys get reused. And a per-item normalizer that runs before a join
eats the seams.

**Three pre-existing tests blocked me, and all three were wrong the same way.**
One asserted the opposite of its own title; one proved "clears index" by querying
after close, which was the defect; one was named after the mechanism, and the
mechanism was the bug. A test name with "and" in it is two claims. A test named
after *how* instead of *what* keeps passing when the how is wrong. And
`prompt-regression-suite#138` is the strongest form: a lock that was correct only
because the thing it locked was fabricated — making the documentation true broke
it, and the repair was to repoint the anchor, not bend the doc back.

**CI caught three things my local runs did not, and all three are process
lessons.** A new D-NNN is a code change to two documents, so run the suite *after*
the MEMORY commit. I measured `json.dumps`'s depth behaviour on one Python version
and generalised it. And a path alias is configured per tool — `tsconfig` mapped
`@/`, `vitest.config.ts` did not. That last one carried the worst verification
mistake of the run: I read `vitest run | tail -4` as a pass, and it showed the
test count without the `Test Files 3 failed` line above it. A suite that fails to
*load* contributes zero tests, so the count shrinks silently instead of going red.

**Two repair patterns worth keeping.** When a guarantee depends on a runtime
property, pin your own bound — and test it by *constraining* the host
(`setrecursionlimit(200)`) rather than asserting what this host survives. And when
a fix has a JT-gated half, ship a ratchet, not a gate: `portfolio-ops#66` freezes
the count of unparseable MEMORY blocks at today's baseline, so the convention is
enforceable tomorrow without forcing a decision about yesterday.

**Four filed-but-unworked followups from prior runs were all real,** three of them
`priority:low` or `med`. Check the followup list before hunting — a previous run
already paid the measurement cost, and a `priority:low` label is not a severity
judgement.

**Stopped at thirteen on structure, not the clock** — 116 of 360 minutes. Every
one of the thirteen repos now has exactly one ready PR, verified per repo, so the
next Phase A has no sibling MEMORY conflicts. A fourteenth issue would have meant
a second ready PR somewhere.

## 2026-08-28 - issue #69: the audit could not see a red default branch

The parent issue asks for a dependency-pinning policy across six repos, and a
previous session deliberately escalated that to JT rather than deciding it. I left
that alone. But the same issue names a second, separable thing that needs no policy
at all: the audit has no fingerprint for "the default branch is broken right now",
and that is why the July break - six repos turned red by a tool release with no
commits - was invisible to the next session's Phase A.

The near miss is the interesting part. One existing check already fetches exactly
the right data and then asks a narrower question of it: it flags a commit that
produced both a success and a failure, which catches a duplicated or flaky workflow
but is blind to a branch that is uniformly red. The data was there; nobody asked.

What pointed me at it was partitioning the existing detectors by what kind of thing
they look at. Four key off shapes in run history, three are static properties of
config files, and the cell for "current state of the branch" was empty.

The anti-vacuous pass then did the best work of the session. Three of my four revert
arms went red as expected; the fourth, removing the filter that skips in-flight
runs, left everything passing. An in-progress run always has a null conclusion,
which was never going to be flagged as red anyway, so a test asserting "no finding"
passed with or without the filter. The filter's actual job runs the other way: it
looks past an in-flight run to the last completed one, so a branch that is red with
a rerun queued still gets reported. Removing it causes a missed detection - the
exact failure this fingerprint exists to end. The generalisation worth keeping is
that when a guard skips a value, the test that matters is not what the skip
suppresses but what it lets you reach.

I validated the check against real history rather than only fixtures, and against
the one repo that could plausibly double-report: its failing workflows are all
scheduled ones, so the new push-scoped check stays quiet and the existing
stale-schedule finding keeps them.

One process near-miss. Running the formatter reformatted eleven files when I had
edited three, because my local linter is older than CI's - the parent issue's
problem in reverse. Recording the formatter's file list on main first, reverting
everything outside my intent, and then asserting the final list matches that
baseline exactly is what kept the diff readable.

## 2026-08-28 - night run: ten issues, and one lens behind half of them

Phase A merged all nine PRs the previous run left - one per repo, no memory
conflicts, the sixth consecutive time that discipline has held. The audit reported
twelve of thirteen repos clean, with the one known scheduled-workflow finding that
has been blocked on a missing API key since mid-August.

One lens accounted for half the night's work: a fix's own enumeration is a coverage
claim, and the real population is usually bigger. An environment-variable helper
opened by listing "four env-reading sites" - there were six, and the two it missed
carried the exact guard it was written to replace. A lock in another repo hand-listed
its three modules, so a fourth copy of the defect it guards against passed all 631
tests. An issue asked for its table to be run against every server, and doing so
found a second server with its own bug. A package surveyed its own frozen dataclasses
and found two, which was true within that package and had never been run elsewhere.
And the silent-rot audit had seven fingerprints and no cell at all for "is the
default branch broken right now" - the gap the July tooling break walked through.

The move is cheap: when a comment contains a list or a count, go count the real
population. Its twin is that a hand-listed guard can never see a new member, which
is the mirror image of the vacuous-test problem I have been solving all month. I
converted four such locks to discovery this run.

The anti-vacuous pass earned its keep three times and twice it changed the code
rather than the tests. Once it deleted a guard I had just written - a boolean check
on a value only ever compared for equality against 404, which no boolean can equal.
Once an arm came back green, and fixing the test revealed that the filter's real job
ran the opposite way from what I had assumed: it looks past an in-flight run to the
last completed one, so removing it causes a missed detection rather than a false one.

Two process notes worth keeping. I nearly shipped the inverse of a bug inside its own
fix, quietly turning a value that used to fail a boot into a silent default; my own
new test caught it, and that shape is easy to miss because it looks like part of the
fix. And I wrote a source-scanning rule in the negative form twice, and both times it
flagged code that was correct - stating it positively, as what must be present, and
naming the exceptions with a test that each still exists, is the version that works.

I stopped at ten with four hours left on the clock, and the reason is structural
rather than fatigue. Ten repos now have exactly one ready, green PR each, which is
what makes the next session's merge pass conflict-free. An eleventh issue would mean
a second PR in a repo that already has one. The three repos without a PR were each
actually hunted tonight and found clean on every axis I applied, rather than assumed.
