# Maintainer roadmap

> **Audience:** maintainers planning the next releases. This is a
> living doc; update it as you merge PRs.
>
> For the detailed historical roadmap (v0.1 → v0.4), see
> [`docs/roadmap.md`](../roadmap.md). This page is the forward-looking
> short-list.

## Release theme overview

| Release | Theme | Status |
|---|---|---|
| v0.1 — Foundation | Session adapter + wiki + static site + search | **shipped** |
| v0.2 — Graph + multi-source | Knowledge graph, watch mode, Cursor/Obsidian adapters | **shipped** |
| v0.3 — Synth + eval | Eval framework, i18n scaffold, PDF adapter | **shipped** |
| v0.4 — AI + human dual format | `llms.txt`, JSON-LD, per-page `.txt`/`.json`, MCP export | **shipped** |
| v0.5 — Demo + dev ergonomics | highlight.js CDN, Pages deploy, README screenshots, raw-HTML escape | **shipped** |
| v0.6 — Distribution | qmd export adapter, Obsidian vault overlay | **shipped** (qmd) / **partial** (overlay) |
| v0.7 — Structured entities | Model schema, changelog timeline, vs-comparison pages, project topics | **shipped** |
| v0.8 — Visualizations | Activity heatmap, tool chart, token usage card | **shipped** |
| v0.9 — Maintainer scaffolding | Governance docs, review checklists, slash commands | **shipping now** |
| v1.0 — Stability pass | API freeze, docs polish, upgrade guide, LTS promise | planned |

## Near-term (next 2-4 weeks)

Start with issues that are already `priority:should` in the queue.

- [ ] **Auto vs-comparison pages** — #58 ✅ shipped
- [ ] **qmd export adapter** — #59 ✅ shipped
- [ ] **Maintainer governance** — #62 ✅ shipping now
- [ ] **PyPI release automation** — #42 (v0.6). One-tag-push → published
- [ ] **Homebrew formula** — #41 (v0.6). `brew install llmwiki`
- [ ] **Vault overlay mode** — #54 (v0.6). Compile existing Obsidian
      vaults without a sync step
- [ ] **PDF adapter graduation** — #39 (v0.5). Scaffold → production
- [ ] **Cursor adapter graduation** — #37 (v0.5). Scaffold → production
- [ ] **Gemini CLI adapter graduation** — #38 (v0.5). Scaffold → production

## Mid-term (v0.10 → v0.12)

- **L1/L2/L3 cache-tier frontmatter** — #52. Per-page freshness tiers
  so `/wiki-query` can prune cold pages from context
- **Wiki candidates approval flow** — #51. Staging area for LLM-
  generated pages before they land in `wiki/`
- **Prompt caching + batch API for sync** — #50. Significant cost
  reduction on large repos
- **ChatGPT conversation-export adapter** — #44
- **OpenCode/OpenClaw adapter** — #43
- **WCAG 2.1 AA audit** — #46
- **Lazy search index** — #47. Per-project index chunks instead of one
  monolith
- **Playwright E2E tests** — #45
- **Scheduled-sync templates** — #48 (launchd / systemd / Task
  Scheduler)

## Long-term (v1.0+)

- **API freeze** — CLI flags, frontmatter schema, slash-command
  contracts
- **LTS branch** — v1.x gets security fixes for 12 months
- **Upgrade guide** — concrete migration recipes for every breaking
  change between 0.x and 1.0
- **Plugin marketplace** — `.claude-plugin/marketplace.json` entries
  for the community
- **Hosted demo mode** — opt-in one-click deploy so people can try
  llmwiki without `git clone`

## Decision log (what we decided NOT to do)

See [`DECLINED.md`](DECLINED.md).

## Re-reading this doc

- **Every Friday:** skim the near-term list, move items that shipped
  into the release-theme table, pull in anything new from the issue
  queue
- **Before a release:** check that every item in the theme is
  actually shipped (search the CHANGELOG for the PR numbers)
- **After a release:** bump the "near-term" section to the new
  release window

This doc is the contract between what maintainers think is next
and what contributors pick up. Keep it short. If it gets longer
than one screen, prune.
