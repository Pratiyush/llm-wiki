You are maintaining a Karpathy-style LLM Wiki. Your job is to read a
raw session transcript and produce a structured wiki source page.

## Input

The raw session markdown is provided below. It includes frontmatter
with metadata (project, date, model, tools used) and the full
conversation transcript.

## Output format

Produce ONLY the body sections below (no frontmatter — the caller
adds that). Use `[[wikilinks]]` for cross-references.

The FIRST line of your response MUST be a suggested-tags HTML
comment listing 3–5 topical tags (kebab-case, lowercase, no spaces)
that describe *what the session was about*, not who produced it:

```
<!-- suggested-tags: prompt-caching, anthropic-api, token-budget -->
```

Good tags name concrete subjects a reader would search for (e.g.
`prompt-caching`, `rag`, `regex-vs-llm`, `github-actions`, `sqlite-fts`).
Bad tags are broad (`coding`, `discussion`) or structural (`summary`,
`session`) — the pipeline already emits those.  Do NOT repeat the
adapter (`claude-code`, `codex-cli`), project slug, or model family
(`claude`, `gpt`) — those are added deterministically.

Emit the comment, then a blank line, then the body:

```markdown
<!-- suggested-tags: ..., ..., ... -->

## Summary

2-4 sentence synthesis of what the session accomplished. Focus on
decisions made, problems solved, and tools/libraries chosen.

## Key Claims

- Claim 1 (a concrete, falsifiable statement from the session)
- Claim 2
- Claim 3

## Key Quotes

> "Direct quote from the session" — context for why it matters

## Connections

- [[EntityName]] — how they relate to this session
- [[ConceptName]] — how it connects

## Contradictions

- Contradicts [[OtherPage]] on: ... (only if applicable)
```

## Rules

1. Do NOT copy the conversation verbatim — synthesize
2. Every claim must be traceable to something said in the session
3. Use `[[wikilinks]]` for any person, tool, library, framework, or
   concept mentioned. TitleCase for entities, TitleCase for concepts.
4. If the session contradicts known wiki content, record BOTH claims
   under ## Contradictions. Never silently overwrite.
5. Keep it concise — the source page is a summary, not a transcript.

## Session to synthesize

Frontmatter:
```yaml
{meta}
```

Body:
```markdown
{body}
```
