# scripts/

Portfolio-ops operator scripts. Stdlib-only where possible; pyyaml is the
only third-party dep, used by two `audit_phase_a.py` fingerprints.

## Scripts

| Script | Purpose | Spec |
|---|---|---|
| `audit_phase_a.py` | Nine silent-rot fingerprints across the 13 portfolio repos. Used at the top of Phase A in every session and as the cron payload for `.github/workflows/audit-cron.yml`. | #19, extended in #21/#22, #32, #35, #41, #63, #69, #76 |
| `audit_issue_sync.py` | Decides whether an audit finding set should **file** a new `[audit-cron]` issue, **comment** on the open one, or stay **silent**. Compares stable per-kind finding identities — excluding volatile fields like `consecutive_failures`, `sha` and `sample_shas` — against the machine-readable block the last run recorded on the issue. Replaces the presence-only skip that let one unclosable issue suppress every new finding for ~10 weeks. | #72 |
| `trending_scan.py` | Daily trending intake (operator-blocked until `ANTHROPIC_API_KEY` and `PORTFOLIO_PAT` are configured — see #17). | #1, D-003 |
| `prune_stale_trending.py` | Weekly prune of stale trending issues per handoff §5. | D-003 |
| `check_memory_yaml.py` | Ratchet on unparseable `MEMORY/full_history_ai.md` session blocks, and with `--kind decisions` on unparseable `MEMORY/core_decisions_ai.md` entries. A block or entry that loads but repeats a key, or a decision whose id repeats an earlier one, counts too: that is what a clean `merge=union` merge of two appends leaves. Fails when a repo's count *grows* past `memory_yaml_baseline.json`; never demands zero, so the retro-fix decision stays open. Phase A runs it over all 13 repos' `origin/main` (`--root --ref`). | #66, D-010, #75, D-013, #107, #112, #117 |
| `check_merge_attr.py` | Reports every local clone or worktree under `portfolio-ops/` and `repos/*` whose `git check-attr merge` on `MEMORY/full_history_{ai,human}.md` or `MEMORY/core_decisions_{ai,human}.md` is not `unspecified`. A leftover `merge=union` in `.git/info/attributes` turns the conflict `resolve_memory_conflict.py` handles into a clean, glued merge. Phase A only: `audit-cron` has no local clones. | #107, #117 |
| `resolve_memory_conflict.py` | Rebase helper for `MEMORY/full_history_{ai,human}.md` YAML/Markdown merge conflicts. Rebuilds both whole sides and writes ours, then theirs from the last section break they share, so an entry git split into several hunks stays whole (#95) and a hoisted trailer needs no special case. Refuses an entry present on both sides after they diverge, and refuses to write a block with a duplicated `decisions_made:`/`followups:` key. Handles `merge.conflictStyle=diff3`/`zdiff3` (drops an empty `|||||||` base, refuses a non-empty one), and refuses to write if any conflict-marker line is left. Either side of a hunk may be empty (a key or paragraph only one entry has, #101), and both files are resolved and checked before either is written, so a refusal never leaves MEMORY/ half-resolved. Refuses an edit to the last existing entry under the default style too, by checking the merge base from git's index (stage 1) is intact before the cut; with no stage-1 base, two appended tails opening with the same heading or `session:` line are refused as ambiguous (#104). | #11, #23, #25, #65, #90, #95, #101, #104 |

## Local-runner setup

```bash
# Optional but recommended: bump the unauth GitHub rate limit by 60×.
export GH_TOKEN=$(gh auth token)

# Install pyyaml for the two yaml-dependent audit fingerprints
# (missing-timeout, missing-concurrency). The other four checks are
# stdlib-only and work without it.
pip install -r scripts/requirements.txt

# Smoke-test the audit on one repo.
python3 scripts/audit_phase_a.py --repo llm-eval-harness

# MEMORY YAML ratchet across the whole portfolio. Run from the checkout root
# that holds both `portfolio-ops/` and `repos/` -- the layout Phase A assumes.
# portfolio-ops' own CI runs the single-repo form; only an operator with every
# repo checked out can run the cross-repo one. Phase A step 4 runs exactly
# these two lines after fetching every clone (#112). `--ref origin/main` reads
# each file with `git show` as of the last fetch. Without it, the files are
# read from each clone's working tree, which is whatever branch the last
# session left it on.
cd ~/projects/portfolio
python3 portfolio-ops/scripts/check_memory_yaml.py --root . --ref origin/main
python3 portfolio-ops/scripts/check_memory_yaml.py --root . --ref origin/main --kind decisions
# -> 0 within baseline, 1 a repo regressed, 2 usage/IO error
python3 portfolio-ops/scripts/check_merge_attr.py --root .
# -> 0 every checkout unspecified, 1 a merge attribute is set, 2 usage error
```

Since #107 the history ratchet also counts a block that loads but repeats a
top-level key. Two entries glued without their `---` fence load as one mapping
in which the second entry's keys win, so the first entry disappears with no
parse error. The 29 such blocks on the 13 origin/main files on 2026-10-21 were
added to each repo's baseline, and nothing else was added.

`check_memory_yaml.py` is a **ratchet**: it compares each repo against
`scripts/memory_yaml_baseline.json` and fails only when a count grows. It does
not demand zero. `MEMORY/` is append-only (handoff §10), and whether the 74
existing unparseable blocks are retro-fixed is a JT decision (#66) that the
ratchet deliberately leaves open. `--write-baseline` re-freezes the counts for
the `--kind` it was given and only for the repos that run checked. The other
kind's counts are kept, and so is every repo a `--repo` or `--file` run did not
check (#111). Use it only as part of a deliberate retro-fix.

`--kind decisions` (#75) applies the same ratchet to `core_decisions_ai.md`,
where `related_issues: [#188]` breaks YAML the same way `followups: [#107]`
does. That file is one YAML sequence, so a whole-file load fails at the first
bad line and reads zero decisions; the checker loads each `- id:` entry on its
own instead, which is what lets the count fall as entries are repaired and rise
by exactly one when a bad entry is added. Measured on 2026-10-19: 63 of 235
entries across the 13 repos, every one of them a bare `#` in a flow list, and
quoting those lines alone makes all 13 files load whole. New entries quote
every list item (D-013).

Without pyyaml installed, `audit_phase_a.py` still runs but skips the
two yaml-dependent checks with a stderr note:

```
skipping missing-timeout for <repo>: pyyaml not installed
skipping missing-concurrency for <repo>: pyyaml not installed
```

The lazy import + graceful degradation pattern is intentional: the
script is usable on a minimal venv for the four stdlib checks and a
missing dep never crashes the session-runner Phase A bash wrapper that
branches on exit code.

## Where pyyaml is guaranteed

- `.github/workflows/audit-cron.yml`'s `audit` job installs pyyaml
  explicitly (locked by
  `tests/test_audit_cron_workflow.py::test_pyyaml_installed`).
- `.github/workflows/tests.yml`'s `test` job installs `pytest pyyaml`
  for the lock-test suite, which includes the workflow-shape and
  yaml-parseability locks.
