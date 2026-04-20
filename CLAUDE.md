# llmwiki — Claude Code Schema

You are maintaining an **LLM Wiki** (per [Karpathy's spec](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)) that compiles the user's Claude Code session history into a structured, interlinked markdown knowledge base.

## Three layers

```
raw/           IMMUTABLE. Session transcripts converted from ~/.claude/projects/*/*.jsonl.
               Flat naming: YYYY-MM-DDTHH-MM-project-slug.md (no subdirectories).
               Never modify files here. Treat as source-of-truth for facts.

wiki/          YOU OWN THIS. LLM-generated pages that summarise, cross-reference, and
               synthesise the raw layer. All of your writes go here.
  index.md         Catalog of every page in the wiki. Update on every ingest.
  log.md           Append-only chronological record of every operation.
  overview.md      Living synthesis across all sources.
  sources/         One summary page per raw source (kebab-case slug).
  entities/        People, companies, projects, products (TitleCase.md).
  concepts/        Ideas, frameworks, methods, theories (TitleCase.md).
  syntheses/       Saved query answers (kebab-case slug).
  comparisons/     Side-by-side diffs of two or more entities/concepts (kebab-case slug). [v0.2+]
  questions/       First-class open questions with state tracking (kebab-case slug). [v0.2+]
  archive/         Deprecated / demoted pages preserved for history. [v0.2+]

site/          GENERATED. Static HTML from `python3 -m llmwiki build`. Do not edit by hand.
```

## Slash commands (and what they do)

| Command | Intent | Workflow |
|---|---|---|
| `/wiki-sync` | Convert new `.jsonl` sessions into `raw/sessions/` AND ingest them into `wiki/` | Runs `python3 -m llmwiki sync`, then executes the Ingest Workflow below for each new file |
| `/wiki-ingest <path>` | Ingest one source or folder | Executes the Ingest Workflow for the given path |
| `/wiki-query <question>` | Answer a question from the wiki | Executes the Query Workflow below |
| `/wiki-lint` | Find orphans, broken links, stale pages | Executes the Lint Workflow below |
| `/wiki-build` | Regenerate the static HTML site | Runs `python3 -m llmwiki build` |
| `/wiki-serve` | Start the local HTTP server | Runs `python3 -m llmwiki serve` |
| `/wiki-update` | Update one wiki page in place (v0.2+) | Surgical edit of one page without re-ingest |
| `/wiki-graph` | Build the knowledge graph (v0.2+) | Walks `[[wikilinks]]` → `graph/graph.json` + `graph.html` |
| `/wiki-reflect` | Higher-order self-reflection over the wiki (v0.2+) | Finds gaps, patterns, and suggests new pages |

## Ingest Workflow

Triggered by `/wiki-ingest <path>` or `/wiki-sync`.

1. **Read the source file(s)** under `raw/` using the Read tool.
2. **Read wiki context** — `wiki/index.md` and `wiki/overview.md` — so you know what's already there.
3. **For each source file**, write `wiki/sources/<slug>.md` using the Source Page Format below. `<slug>` comes from the YAML frontmatter's `slug` field when present, otherwise from the filename.
4. **Update `wiki/index.md`** — add the new source under `## Sources`.
5. **Update `wiki/overview.md`** — revise the synthesis if the new source adds substantial new information. Don't rewrite for trivia.
6. **Create/update entity pages** (`wiki/entities/<Name>.md`) for any people, companies, projects, products, tools, libraries mentioned. TitleCase filename.
7. **Create/update concept pages** (`wiki/concepts/<Name>.md`) for any ideas, patterns, frameworks, or decisions mentioned.
8. **Cross-link** everything with `[[wikilinks]]` under `## Connections` on every page.
9. **Flag contradictions** — if a new source contradicts existing wiki content, add a `## Contradictions` section to the affected page and leave BOTH claims visible. Do not silently overwrite.
10. **Append to `wiki/log.md`** with the format: `## [YYYY-MM-DD] ingest | <title>`

### Session-derived source specifics

Files under `raw/sessions/<YYYY-MM-DDTHH-MM>-<project>-<slug>.md` are auto-generated from `.jsonl` transcripts (flat naming, no subdirectories). They have rich YAML frontmatter (`project`, `slug`, `started`, `model`, `tools_used`, `gitBranch`, etc.). When ingesting these:

- **Trust the frontmatter** — don't re-infer metadata from the body
- **Do NOT copy the Conversation section verbatim** — treat it as raw material to summarize
- **Create or update a project entity page** at `wiki/entities/<ProjectSlug>.md` with a bulleted session list under `## Sessions`
- **Extract decisions** — anything the user explicitly locked ("decision locked", "let's go with", "I decided...") goes into `wiki/concepts/`
- **Extract tools + libraries** — every `tools_used` entry and every library mentioned in code previews becomes a potential entity page
- **If `is_subagent: true`** — link the page as a child of its parent session rather than a standalone entity

## Source Page Format

```markdown
---
title: "Source Title"
type: source
tags: [claude-code, session-transcript]
date: YYYY-MM-DD
source_file: raw/sessions/<YYYY-MM-DDTHH-MM>-<project>-<slug>.md
project: <project-slug>
model: <model-id>
---

## Summary
2–4 sentence synthesis of what the session accomplished.

## Key Claims
- Claim 1
- Claim 2
- Claim 3

## Key Quotes
> "Quote here" — context

## Connections
- [[EntityName]] — how they relate
- [[ConceptName]] — how it connects

## Contradictions
- Contradicts [[OtherPage]] on: ...
```

## Entity / Concept Page Format

```markdown
---
title: "Entity Name"
type: entity  # or: concept
tags: []
sources: [source-slug-1, source-slug-2]
last_updated: YYYY-MM-DD
---

# Entity Name

One-paragraph description.

## Key Facts
- Fact 1
- Fact 2

## Sessions
- [[session-slug]] (YYYY-MM-DD) — what happened

## Connections
- [[RelatedEntity]]
- [[RelatedConcept]]
```

## Query Workflow

Triggered by `/wiki-query <question>`.

1. Read `wiki/index.md` and `wiki/overview.md` to identify relevant pages.
2. **(v0.5, #60) Before descending into a folder, read its `_context.md`** if one exists (e.g. `wiki/entities/_context.md`, `wiki/concepts/_context.md`). The context file is a one- or two-paragraph description of what lives in that folder — use it to decide whether the folder is worth walking into for the current query, and which of its pages to read in full versus skip. This saves context tokens on every deep query.
3. Use Read on the matching pages.
4. Synthesise an answer with inline `[[wikilink]]` citations.
5. If the answer is substantial (3+ paragraphs), ask the user if they want it saved to `wiki/syntheses/<slug>.md`.
6. Append to `wiki/log.md` with `## [YYYY-MM-DD] query | <question>`.

## Lint Workflow

Triggered by `/wiki-lint`.

Use Grep and Read to find:

1. **Orphan pages** — wiki pages with no inbound `[[links]]` from any other page.
2. **Broken wikilinks** — `[[Name]]` pointing to a page that does not exist.
3. **Contradictions** — claims that conflict across pages.
4. **Stale summaries** — pages whose `last_updated` is older than the newest source that contributes to them.
5. **Missing entity pages** — entities mentioned in 3+ source pages but lacking their own page.
6. **Data gaps** — questions the wiki can't answer; suggest new sources or queries.
7. **(v0.5, #60) Uncontexted folders** — any `wiki/` subfolder containing >10 `.md` files that lacks a `_context.md` stub. Large knowledge folders without a context description make deep queries more expensive per call — suggest creating a stub that describes what lives there. Use `python3 -c "from llmwiki.context_md import find_uncontexted_folders; from pathlib import Path; print(list(find_uncontexted_folders(Path('wiki'))))"` or load the helper directly.

Output a report to the chat. Ask the user if they want it saved to `wiki/lint-report.md`.

## Naming Conventions

- **Source slugs**: `kebab-case` (matches the raw filename without `.md`)
- **Entity pages**: `TitleCase.md` (e.g., `OpenAI.md`, `AndrejKarpathy.md`)
- **Concept pages**: `TitleCase.md` (e.g., `ReinforcementLearning.md`, `RAG.md`)
- **Synthesis pages**: `kebab-case.md`

## Index Format

```markdown
# Wiki Index

## Overview
- [Overview](overview.md)

## Sources
- [Source Title](sources/slug.md) — one-line summary

## Entities
- [Entity Name](entities/EntityName.md) — one-line description

## Concepts
- [Concept Name](concepts/ConceptName.md) — one-line description

## Syntheses
- [Analysis Title](syntheses/slug.md) — what question it answers
```

## Log Format

Each entry starts with `## [YYYY-MM-DD] <operation> | <title>` so it's grep-parseable:

```
grep "^## \[" wiki/log.md | tail -10
```

Operations: `sync`, `ingest`, `query`, `lint`, `build`.

## Hard rules

1. **`raw/` is immutable.** Never modify files under `raw/`. If source data is wrong, fix the converter, not the output. **Enforced at runtime as of #326**: `llmwiki sync` refuses to overwrite an existing `raw/` file unless you pass `--force`; failures go into `.llmwiki-quarantine.json` so you can see what didn't sync and why. Non-AI adapters (Obsidian, Jira, Meeting, PDF) are opt-in only — they never fire on a default `sync` without explicit `enabled: true` in `sessions_config.json`.
2. **No silent overwrites.** When ingest conflicts with existing wiki content, record both claims under `## Contradictions`.
3. **Cross-link everything.** Every page should have a `## Connections` section with at least one `[[wikilink]]`.
4. **Frontmatter is authoritative.** Always fill `title`, `type`, `tags`, `sources` (where applicable), and `last_updated`.
5. **One commit per page group** when publishing to git — match the PR rules in the open-source framework.
