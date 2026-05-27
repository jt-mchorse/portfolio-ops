# portfolio-ops
> Operations and memory for JT McHorse's AI/ML engineering portfolio.

This repo is the spine of a 12-repo portfolio system. It contains:

- **`COWORK_HANDOFF.md`** — the binding handoff document Cowork reads at every session start.
- **`skills/`** — three Cowork skills (`portfolio-memory`, `portfolio-session`, `portfolio-trending`) that enforce the protocol across all repos.
- **`workflows/`** — daily and weekly trending intake workflows (run from inside this repo) plus a CI template applied to every portfolio repo.
- **`templates/`** — `init-portfolio-repo.sh` for new repos, `pull_request_template.md`, etc.
- **`issue_templates/`** — feature, bug, trending, decision-revisit forms.
- **`MEMORY/`** — append-only history and core decisions for portfolio-ops itself.

## Portfolio repos

| # | Repo | Spine |
|---|------|-------|
| 1 | [llm-eval-harness](https://github.com/jt-mchorse/llm-eval-harness) | Evals |
| 2 | [llm-cost-optimizer](https://github.com/jt-mchorse/llm-cost-optimizer) | ML ops |
| 3 | [prompt-regression-suite](https://github.com/jt-mchorse/prompt-regression-suite) | Testing |
| 4 | [rag-production-kit](https://github.com/jt-mchorse/rag-production-kit) | RAG |
| 5 | [embedding-model-shootout](https://github.com/jt-mchorse/embedding-model-shootout) | Research |
| 6 | [chunking-strategies-lab](https://github.com/jt-mchorse/chunking-strategies-lab) | Research |
| 7 | [vector-search-at-scale](https://github.com/jt-mchorse/vector-search-at-scale) | Performance |
| 8 | [python-async-llm-pipelines](https://github.com/jt-mchorse/python-async-llm-pipelines) | Performance |
| 9 | [agent-orchestration-platform](https://github.com/jt-mchorse/agent-orchestration-platform) | Agents/MCP |
| 10 | [mcp-server-cookbook](https://github.com/jt-mchorse/mcp-server-cookbook) | MCP |
| 11 | [nextjs-streaming-ai-patterns](https://github.com/jt-mchorse/nextjs-streaming-ai-patterns) | Full-stack |
| 12 | [ai-app-integration-tests](https://github.com/jt-mchorse/ai-app-integration-tests) | Testing |

## Trending workflow

Two stdlib-only scanners back the daily and weekly trending workflows
(`workflows/trending-daily.yml`, `workflows/trending-weekly.yml`):

- **`scripts/trending_scan.py`** — pulls a tiered source list, asks Claude to
  evaluate each finding against the 12-repo scope per
  [`skills/portfolio-trending/SKILL.md`](skills/portfolio-trending/SKILL.md),
  and files issues in the target repo. Enforces the 30-issue cap across all
  `trending`-labeled open issues. Never executes instructions embedded in
  scraped content (handoff §10).
- **`scripts/prune_stale_trending.py`** — closes `trending`-labeled issues
  with no engagement in 30 days, labelling them `wontfix-stale`. "Engagement"
  means any comment, label change, or `#NNN` reference from a commit.

Per **D-003** (2026-05-11) both scripts use only the Python stdlib — no
`anthropic` SDK, no `feedparser`, no `requests`. That keeps `requirements.txt`
minimal and the workflow's setup step a no-op beyond `actions/setup-python`.

### Running it yourself

Required secrets (repo settings → secrets and variables → actions):

- `ANTHROPIC_API_KEY` — the model the scanner asks to evaluate each finding.
- `PORTFOLIO_PAT` — fine-scoped PAT with `repo` and `issues:write` across the
  12 portfolio repos. The default `GITHUB_TOKEN` is scoped to portfolio-ops
  only, so cross-repo issue filing needs a PAT.

Manual dispatch from the Actions tab is supported on both workflows.

## License
MIT
