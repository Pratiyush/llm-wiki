---
title: "Overview"
type: synthesis
sources: []
last_updated: "2026-04-25"
---

# Overview

This wiki is the seed corpus llmwiki itself ships with — a small, redacted
example set used by the [`Lint + build seeded wiki`](../.github/workflows/wiki-checks.yml)
CI gate to verify that lint and build still produce a valid site after every
change. The pages under `wiki/entities/` and `wiki/projects/` are deliberately
tiny synthetic examples; real users see their own data populated here once
`llmwiki sync` runs against their session history.

The wiki is structured per [[CRITICAL_FACTS]]: `raw/` is immutable, `wiki/`
is the LLM-maintained layer, and `site/` is the generated static HTML.

## Connections

- [[CRITICAL_FACTS]] — hard rules about the three-layer model
- [[demo-blog-engine]] — example project page
- [[demo-todo-api]] — example project page
- [[demo-ml-pipeline]] — example project page
- [[llm-wiki]] — the meta project (this repo's own wiki)
