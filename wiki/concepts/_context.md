---
type: folder-context
title: Concepts
---

# Concepts

Ideas, patterns, methods, decisions, and frameworks the wiki tracks.
Pages here use `type: concept` frontmatter and live as `TitleCase.md`
files (e.g. `ReinforcementLearning.md`, `RAG.md`).

**When to walk this folder in a query:**
- The user asks "how does X work", "what is Y", or "why did they
  choose Z" — concept pages explain reasoning, not actors.
- The user asks about trade-offs or alternatives — concepts are where
  comparisons live.

**When to skip this folder:**
- The user asks about a specific person, product, or company — prefer
  `wiki/entities/` (`entities/_context.md` for the split).
- The user asks "what happened recently" — `wiki/sources/` carries the
  timeline.

Concept pages should link to the entities that instantiate them and
to any sources that discuss them.
