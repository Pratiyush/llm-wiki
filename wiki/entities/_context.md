---
type: folder-context
title: Entities
---

# Entities

People, companies, projects, products, tools, and libraries the wiki
tracks. Pages here use `type: entity` frontmatter and live as
`TitleCase.md` files (e.g. `OpenAI.md`, `ReactJS.md`).

**When to walk this folder in a query:**
- The user asks "who" (person), "what product", "what library", "which
  company" — this is the first folder to check.
- The user asks about an ecosystem or stack — entity pages cross-link
  to their related concepts.

**When to skip this folder:**
- The user asks about an idea, pattern, or method — prefer
  `wiki/concepts/` instead (`concepts/_context.md` for the split).
- The user asks "when" / timeline questions — `wiki/sources/` (session
  transcripts) is usually a better starting point.

Each page should have a `## Connections` section linking to at least
one concept and at least one other entity.
