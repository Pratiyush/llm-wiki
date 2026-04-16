---
title: "Navigation Hints"
type: navigation
last_updated: 2026-04-16
---

# Hints — Writing Conventions & Navigation Rules

Load this file on-demand via `@wiki/hints.md` when you need detailed rules.

## Page Naming

- **Source slugs:** `kebab-case` (matches the raw filename without `.md`)
- **Entity pages:** `TitleCase.md` (e.g., `OpenAI.md`, `AndrejKarpathy.md`)
- **Concept pages:** `TitleCase.md` (e.g., `ReinforcementLearning.md`, `RAG.md`)
- **Synthesis pages:** `kebab-case.md`

## Entity Types

Every entity page must declare one of 7 `entity_type` values:

| Type | Use For | Example |
|------|---------|---------|
| `person` | Individual human | Pratiyush, Karpathy |
| `org` | Company or organization | Anthropic, OpenAI |
| `tool` | Software tool or service | Claude Code, Obsidian |
| `concept` | Abstract idea / pattern | RAG, Attention Mechanism |
| `api` | API or protocol | MCP, REST |
| `library` | Code library / package | React, Flask, spaCy |
| `project` | Named product / project | AiNewsletter, Germanly |

## Required Frontmatter

Every page MUST have: `title`, `type`, `tags`, `last_updated`.
Entity/concept pages also need: `sources`, `confidence`, `lifecycle`, `entity_type`.

## Writing Style

- Use active voice
- Keep summaries to 2-4 sentences
- Prefer `[[wikilinks]]` over bare text when referencing other pages
- Every page needs a `## Connections` section with at least one wikilink
- Flag contradictions — never silently overwrite

## Confidence Scoring

Pages receive a confidence score from 0.0 to 1.0 based on:
- Source count (30%): how many raw sources mention this
- Source quality (30%): official docs > blog > forum > LLM-generated
- Recency (20%): last 30 days = 1.0, 90+ days = 0.5
- Cross-references (20%): 6+ inbound links = 1.0

## Lifecycle States

- `draft` — newly created, unreviewed
- `reviewed` — lint passed, basic quality confirmed
- `verified` — high confidence, human-confirmed
- `stale` — 90+ days without update (auto-transition)
- `archived` — kept for history (manual transition only)
