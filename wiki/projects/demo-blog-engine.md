---
title: "demo-blog-engine"
type: entity
entity_type: project
project: demo-blog-engine
topics: [rust, blog, ssg, pulldown-cmark, syntect, markdown]
description: "Minimal Rust static site generator for a personal blog. Markdown → HTML pipeline, front-matter parsing, syntax highlighting via syntect, RSS feed, and a dark-mode toggle."
homepage: "https://example.com/demo-blog-engine"
cache_tier: L2
---

# demo-blog-engine

Reference project for the Rust SSG track. Source under `content/*.md`,
output under `public/`. Good example of how llmwiki's session logs
capture a realistic build-from-scratch trajectory: scaffolding the
crate, picking the markdown library, adding syntax highlighting, then
the final polish passes (RSS + dark mode).

## Connections

- [[Rust]]
- [[StaticSiteGeneration]]
- [[pulldown-cmark]]
- [[syntect]]
