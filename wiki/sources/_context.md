---
type: folder-context
title: Sources
---

# Sources

Per-session summary pages — one markdown file per raw session file
under `raw/sessions/`. Slugs are `kebab-case` and match the raw
filename. Frontmatter uses `type: source`.

**When to walk this folder in a query:**
- The user asks "when did I work on X" or "what did I do in session Y".
- The user asks for a timeline or recent activity — source pages have
  `date` frontmatter and are the chronological spine of the wiki.
- The user wants a direct quote from an actual session.

**When to skip this folder:**
- The user asks "who/what/how/why" questions — prefer
  `wiki/entities/` or `wiki/concepts/` first and follow their
  `## Connections` back here only if needed.
- The folder is large (hundreds of sessions). Read the session list
  in `wiki/index.md` first and only open specific files that match
  the query's date range or keywords.

Never modify files under `raw/sessions/` — they are immutable source
data. Source pages here are the LLM's editable summary layer.
