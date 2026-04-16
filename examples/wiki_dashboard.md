---
title: "Wiki Dashboard"
type: navigation
last_updated: ""
---

# Wiki Dashboard

Live overview of the wiki. Open in Obsidian with the Dataview plugin enabled.
All queries read YAML frontmatter across `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/syntheses/`.

## Recently Updated (last 14 days)

```dataview
TABLE last_updated, type, project
FROM "sources" OR "entities" OR "concepts" OR "syntheses"
WHERE last_updated
SORT last_updated DESC
LIMIT 20
```

## By Confidence

### High confidence (≥ 0.8)

```dataview
TABLE confidence, type, last_updated
FROM "sources" OR "entities" OR "concepts"
WHERE confidence >= 0.8
SORT confidence DESC
```

### Low confidence (< 0.5) — needs review

```dataview
TABLE confidence, type, last_updated
FROM "sources" OR "entities" OR "concepts"
WHERE confidence < 0.5
SORT confidence ASC
```

## By Lifecycle

### Draft

```dataview
LIST
FROM "sources" OR "entities" OR "concepts" OR "syntheses"
WHERE lifecycle = "draft"
```

### Reviewed

```dataview
LIST
FROM "sources" OR "entities" OR "concepts" OR "syntheses"
WHERE lifecycle = "reviewed"
```

### Verified

```dataview
LIST
FROM "sources" OR "entities" OR "concepts" OR "syntheses"
WHERE lifecycle = "verified"
```

### Stale — needs refresh

```dataview
TABLE last_updated, type
FROM "sources" OR "entities" OR "concepts"
WHERE lifecycle = "stale"
SORT last_updated ASC
```

### Archived

```dataview
LIST
FROM "sources" OR "entities" OR "concepts"
WHERE lifecycle = "archived"
```

## By Project

```dataview
TABLE length(rows) AS pages
FROM "sources" OR "entities"
WHERE project
GROUP BY project
SORT length(rows) DESC
```

## By Entity Type

```dataview
TABLE length(rows) AS count
FROM "entities"
WHERE entity_type
GROUP BY entity_type
SORT length(rows) DESC
```

## Open Questions

```dataview
LIST
FROM "questions"
WHERE !contains(file.name, "_context")
```

## Orphan Candidates

Pages with no `sources` field or empty sources list (possibly uncited claims):

```dataview
LIST
FROM "entities" OR "concepts"
WHERE !sources OR length(sources) = 0
```

## Summary

```dataview
TABLE WITHOUT ID
    length(filter(file.path, (p) => contains(p, "sources/"))) AS Sources,
    length(filter(file.path, (p) => contains(p, "entities/"))) AS Entities,
    length(filter(file.path, (p) => contains(p, "concepts/"))) AS Concepts,
    length(filter(file.path, (p) => contains(p, "syntheses/"))) AS Syntheses
FROM "sources" OR "entities" OR "concepts" OR "syntheses"
FLATTEN file.path
GROUP BY ""
```

## Connections

- [[index]] — full wiki catalog
- [[overview]] — living synthesis
- [[hints]] — writing conventions
