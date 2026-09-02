# scripts/

Portfolio-ops operator scripts. Stdlib-only where possible; pyyaml is the
only third-party dep, used by two `audit_phase_a.py` fingerprints.

## Scripts

| Script | Purpose | Spec |
|---|---|---|
| `audit_phase_a.py` | Eight silent-rot fingerprints across the 13 portfolio repos. Used at the top of Phase A in every session and as the cron payload for `.github/workflows/audit-cron.yml`. | #19, extended in #21/#22, #32, #35, #41, #63, #69 |
| `audit_issue_sync.py` | Decides whether an audit finding set should **file** a new `[audit-cron]` issue, **comment** on the open one, or stay **silent**. Compares stable per-kind finding identities — excluding volatile fields like `consecutive_failures`, `sha` and `sample_shas` — against the machine-readable block the last run recorded on the issue. Replaces the presence-only skip that let one unclosable issue suppress every new finding for ~10 weeks. | #72 |
| `trending_scan.py` | Daily trending intake (operator-blocked until `ANTHROPIC_API_KEY` and `PORTFOLIO_PAT` are configured — see #17). | #1, D-003 |
| `prune_stale_trending.py` | Weekly prune of stale trending issues per handoff §5. | D-003 |
| `check_memory_yaml.py` | Ratchet on unparseable `MEMORY/full_history_ai.md` session blocks. Fails when a repo's count *grows* past `memory_yaml_baseline.json`; never demands zero, so the retro-fix decision stays open. | #66, D-010 |
| `resolve_memory_conflict.py` | Rebase helper for `MEMORY/full_history_{ai,human}.md` YAML/Markdown merge conflicts. Reattaches the trailer git hoisted, and refuses to write a block with a duplicated `decisions_made:`/`followups:` key. | #11, #23, #25, #65 |

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
# repo checked out can run the cross-repo one.
cd ~/projects/portfolio
python3 portfolio-ops/scripts/check_memory_yaml.py --root .
# -> 0 within baseline, 1 a repo regressed, 2 usage/IO error
```

`check_memory_yaml.py` is a **ratchet**: it compares each repo against
`scripts/memory_yaml_baseline.json` and fails only when a count grows. It does
not demand zero. `MEMORY/` is append-only (handoff §10), and whether the 74
existing unparseable blocks are retro-fixed is a JT decision (#66) that the
ratchet deliberately leaves open. `--write-baseline` re-freezes the counts, and
should only be used as part of a deliberate retro-fix.

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
