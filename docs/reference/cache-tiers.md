# Cache tiers — load-priority frontmatter

> Status: shipped in v1.2.0 (#52). Optional frontmatter field
> `cache_tier: L1|L2|L3|L4` tells `/wiki-query` how eagerly to load the
> page during context build.

## Why

Today `/wiki-query` reads `wiki/index.md` + `wiki/overview.md` eagerly,
then reads candidate pages on-demand. There's no way to tell the LLM
"this entity is hot — always preload it" vs "this one is archival —
skip unless directly named."

Cache tiers make that explicit without changing anything for pages that
don't opt in.

## The four tiers

| Tier | Meaning | When loaded | Recommended for | Soft budget |
|---|---|---|---|---|
| **L1** | Always loaded | Read in full for every `/wiki-query` | index, overview, hints, CRITICAL_FACTS, 1–2 most-referenced entities | ≤ 5 k tokens combined |
| **L2** | Summary pre-load | First `## Summary` section pre-loaded; body on demand | Active projects, hot entities | ≤ 20 k tokens combined |
| **L3** | On-demand *(default)* | Loaded only when another page links to it | The vast majority of pages | — |
| **L4** | Archive | Never loaded unless explicitly named | Deprecated entities, old sessions, `status: archived` pages | — |

If a page has no `cache_tier` field, it's treated as **L3**. Existing
wikis keep working byte-identically.

## Setting a tier

Add to any page's frontmatter:

```yaml
---
title: "RAG"
type: concept
cache_tier: L1          # ← always preload this entity
last_updated: 2026-04-19
---
```

## How `/wiki-query` uses it

1. Read `wiki/index.md` + `wiki/overview.md` (same as before — these
   are implicitly L1 whether they carry the field or not).
2. Read every page with `cache_tier: L1` in full.
3. Read the `## Summary` section of every page with `cache_tier: L2`.
4. For each `[[wikilink]]` resolved during the answer, read the target
   page if its tier is L3 or lower. (L4 pages are skipped unless the
   user explicitly names them in the query.)

## Lint helpers (`/wiki-lint`)

The `cache_tier_consistency` rule catches:

- **Wasted preload** — L1 page with 0 inbound links
- **Archived but hot** — L4 page with ≥ 3 inbound links
- **Tier/status mismatch** — page with `status: archived` but
  `cache_tier != L4`
- **Invalid tier** — frontmatter value that isn't one of `L1 / L2 / L3 / L4`
- **L1 pool too big** — sum of L1 page bodies exceeds the 5 k token
  budget

## Python API

```python
from llmwiki.cache_tiers import (
    parse_cache_tier,
    is_preloaded,
    summary_excerpt,
    tier_budget_tokens,
    TIER_METADATA,
)

tier, warning = parse_cache_tier(page_meta.get("cache_tier"))
# "L3", None — default when the field is absent

if is_preloaded(tier):
    # L1 reads the full body, L2 reads only the Summary
    preload_text = page_body if tier == "L1" else summary_excerpt(page_body)
```

## Tradeoffs — how to choose

- **Don't put everything in L1.** L1 pages trade context tokens for
  discovery speed. If you promote 50 pages to L1 you've blown 30 k
  tokens every query.
- **Default L3 is the right answer for most pages.** Only promote a
  page to L1 or L2 once you've observed `/wiki-query` walking to it
  repeatedly.
- **Demote rather than delete.** When a page stops being relevant, tag
  it L4 instead of archiving — you keep history searchable for
  `llmwiki lint` + explicit queries, but pay zero context cost for
  typical questions.

## Live adopters (#285)

Pages carrying an explicit `cache_tier` as of v1.1.0-rc8:

| Page | Tier | Why |
|---|---|---|
| [`wiki/entities/ClaudeSonnet4.md`](../../wiki/entities/ClaudeSonnet4.md) | L1 | Flagship model entity — queries about current Claude behaviour always need this |
| [`wiki/entities/GPT5.md`](../../wiki/entities/GPT5.md) | L2 | Reference comparison point, hot but not always loaded |
| [`wiki/projects/llm-wiki.md`](../../wiki/projects/llm-wiki.md) | L1 | Meta project page — the framework's own canonical entry |
| [`wiki/projects/demo-blog-engine.md`](../../wiki/projects/demo-blog-engine.md) | L2 | Demo project, loaded when queries touch SSG / Rust |
| [`wiki/projects/demo-ml-pipeline.md`](../../wiki/projects/demo-ml-pipeline.md) | L2 | Demo project, loaded when queries touch ML / HuggingFace |
| [`wiki/projects/demo-todo-api.md`](../../wiki/projects/demo-todo-api.md) | L2 | Demo project, loaded when queries touch FastAPI / OAuth2 |

This exercises `CacheTierConsistency` in real conditions.  To opt a page in, add `cache_tier: L1` (or `L2`/`L3`/`L4`) to its frontmatter.

## Related

- `#52` — the issue that shipped this
- `#285` — live-adoption polish
- `llmwiki/cache_tiers.py` — implementation
- `llmwiki/lint/rules.py :: CacheTierConsistency` — lint rule
- `docs/reference/reader-shell.md` — sibling opt-in feature, see "Live adopters" there
- `docs/reference/prompt-caching.md` — sibling: Anthropic-level prompt
  cache control
