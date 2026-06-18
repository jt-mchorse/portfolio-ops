# scripts/

Portfolio-ops operator scripts. Stdlib-only where possible; pyyaml is the
only third-party dep, used by two `audit_phase_a.py` fingerprints.

## Scripts

| Script | Purpose | Spec |
|---|---|---|
| `audit_phase_a.py` | Six silent-rot fingerprints across the 13 portfolio repos. Used at the top of Phase A in every session and as the cron payload for `.github/workflows/audit-cron.yml`. | #19, extended in #21/#22, #32, #35, #41 |
| `trending_scan.py` | Daily trending intake (operator-blocked until `ANTHROPIC_API_KEY` and `PORTFOLIO_PAT` are configured — see #17). | #1, D-003 |
| `prune_stale_trending.py` | Weekly prune of stale trending issues per handoff §5. | D-003 |
| `resolve_memory_conflict.py` | Rebase helper for `MEMORY/full_history_{ai,human}.md` YAML/Markdown merge conflicts. | #11, #23, #25 |

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
```

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
