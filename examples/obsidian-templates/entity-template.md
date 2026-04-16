<%*
const date = tp.date.now("YYYY-MM-DD");
const etype = await tp.system.suggester(
  ["person", "org", "tool", "concept", "api", "library", "project"],
  ["person", "org", "tool", "concept", "api", "library", "project"],
  false,
  "Entity type"
);
_%>---
title: "<% await tp.file.title %>"
type: entity
entity_type: <% etype %>
tags: [entity, <% etype %>]
sources: []
confidence: 0.5
lifecycle: draft
last_updated: <% date %>
---

# <% await tp.file.title %>

> [!info] Entity page
> Use for people, orgs, tools, concepts, APIs, libraries, or projects.

One-paragraph description of this entity — who/what it is, why it matters.

## Key Facts

- Fact 1
- Fact 2

## Sessions

- [[session-slug]] (YYYY-MM-DD) — what happened

## Connections

- [[RelatedEntity]]
- [[RelatedConcept]]

## Inline Dataview

**Sources citing this entity:**
```dataview
LIST
FROM "sources"
WHERE contains(file.outlinks, this.file.link)
```
