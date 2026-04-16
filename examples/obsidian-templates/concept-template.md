<%*
const date = tp.date.now("YYYY-MM-DD");
_%>---
title: "<% await tp.file.title %>"
type: concept
tags: [concept]
sources: []
confidence: 0.5
lifecycle: draft
last_updated: <% date %>
---

# <% await tp.file.title %>

> [!info] Concept page
> Use for ideas, patterns, frameworks, methods, theories.

One-paragraph definition of this concept — what it is, why it matters.

## Key Facts

- Fact 1
- Fact 2

## Examples

- Example from [[session-slug]]

## Connections

- [[RelatedConcept]]
- [[RelatedEntity]]

## Inline Dataview

**Sources discussing this concept:**
```dataview
LIST
FROM "sources"
WHERE contains(file.outlinks, this.file.link)
```
