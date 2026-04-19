---
title: "llmwiki documentation"
type: navigation
docs_shell: true
---

# llmwiki documentation

A local, stdlib-only Python knowledge base built from your AI-coding-agent
session transcripts. Install in five minutes, then keep every session
searchable, interlinked, and offline. No database, no account, no cloud.

---

## Getting started — 5 minutes

| # | Tutorial | Time |
|---|---|---|
| 01 | [Installation](tutorials/01-installation.md) — macOS / Linux / Windows / Docker | 5 min |
| 02 | [First sync](tutorials/02-first-sync.md) — from install to a browsable site | 5 min |

*If it's not working in 10 minutes, [open an issue](https://github.com/Pratiyush/llm-wiki/issues/new) — that's a bug in the docs.*

---

## Use with your agent

- **[Claude Code](tutorials/03-use-with-claude-code.md)** — slash commands, session metadata, `/wiki-ingest`, `/wiki-sync`, `/wiki-query`.
- **[Codex CLI](tutorials/04-use-with-codex-cli.md)** — sync from `~/.codex/sessions/`, live-session filtering.
- *Adapter reference:* [Claude Code](adapters/claude-code.md) · [Codex CLI](adapters/codex-cli.md) · [Cursor](adapters/cursor.md) · [Gemini CLI](adapters/gemini-cli.md) · [Copilot](adapters/copilot.md) · [Obsidian](adapters/obsidian.md) · [PDF](adapters/pdf.md).

---

## Use it locally

- **[Query your wiki](tutorials/05-querying-your-wiki.md)** — `/wiki-query`, `/wiki-graph`, `/wiki-lint`, `/wiki-review`, `/wiki-serve`.
- **[Bring your existing Obsidian / Logseq vault](tutorials/06-bring-your-obsidian-vault.md)** — `llmwiki sync --vault <path>`, non-destructive by default.
- **[Example workflows](tutorials/07-example-workflows.md)** — four real, end-to-end workflows.

---

## Deploy

| Target | Guide |
|---|---|
| GitHub Pages | [deploy/github-pages.md](deploy/github-pages.md) |
| GitLab Pages | [deploy/gitlab-pages.md](deploy/gitlab-pages.md) |
| Docker / GHCR | [deploy/docker.md](deploy/docker.md) |
| Vercel / Netlify | [deploy/vercel-netlify.md](deploy/vercel-netlify.md) |
| PyPI publishing | [deploy/pypi-publishing.md](deploy/pypi-publishing.md) |
| Homebrew tap | [deploy/homebrew-setup.md](deploy/homebrew-setup.md) |

---

## Reference

- **[CLI reference](reference/cli.md)** — every `python3 -m llmwiki <subcommand>` with every flag and realistic examples.
- **[Slash commands reference](reference/slash-commands.md)** — every `/wiki-*` command used from Claude Code / Codex.
- **[UI reference](reference/ui.md)** — every screen on the compiled site, how to reach it, what it shows.
- **[Architecture](architecture.md)** — three layers (`raw/` / `wiki/` / `site/`).
- **[Configuration](configuration.md)** · **[Full configuration reference](configuration-reference.md)**.
- **[Cache tiers](reference/cache-tiers.md)** — L1 / L2 / L3 / L4 frontmatter.
- **[Prompt caching + batch API](reference/prompt-caching.md)**.
- **[Reader API contract](reference/reader-api.md)** — stable shapes of every file `llmwiki build` writes.
- **[Reader-first article shell](reference/reader-shell.md)** — opt-in Wikipedia-style layout.
- **[Entity schema](reference/entity-schema.md)** — structured model-profile frontmatter.
- **[Adapter authoring](adapter-authoring.md)** — write an adapter for a new agent.

---

## Operate

- **[FAQ](faq.md)** · **[Troubleshooting](troubleshooting.md)** · **[Privacy](privacy.md)**.
- **[Testing — visual regression](testing/visual-regression.md)**.
- **[Accessibility](accessibility.md)** (WCAG 2.1 AA).
- **[Benchmarks](benchmarks.md)** · **[Competitor landscape](competitor-landscape.md)**.
- **Maintainers** — governance docs at [`docs/maintainers/`](https://github.com/Pratiyush/llm-wiki/tree/master/docs/maintainers).

---

## Contributing

- **[Style guide](style-guide.md)** — how to write docs that match this site's voice.
- **[Adapter authoring](adapter-authoring.md)** — ship a new agent adapter.
- **[Architecture](architecture.md)** — understand the three-layer model before changing code.
- **[Roadmap](roadmap.md)** · **[Public roadmap](public-roadmap.md)**.

---

## What llmwiki is not

It's not a vector database, not a RAG framework, not a hosted service. It
compiles markdown from JSONL transcripts, writes a static site, and stays
out of the way. The only third-party runtime dependency is `markdown`.

## What's new

See the **[changelog](../changelog.html)**. Latest tagged release:
[v1.1.0-rc2](https://github.com/Pratiyush/llm-wiki/releases/tag/v1.1.0-rc2).
