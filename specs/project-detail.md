# project-detail spec

## Goal

Single-project hub showing the project's own activity heatmap and every session that ran inside it.

## URL pattern

- `/projects/<slug>.html`

## Must

- Page `<title>` contains the project slug.
- Breadcrumbs read: `Home › Projects › <slug>` (`.breadcrumbs`).
- An h1 with the project slug.
- A project-scoped activity heatmap (`.activity-heatmap`) showing only this project's session distribution over 365 days.
- A list of sessions ordered by date DESC; each session links to its detail page.
- Active nav link is "Projects".

## Should

- Session count visible somewhere in the header or summary block.
- Project topics (`topics:` frontmatter from `wiki/projects/<slug>.md`) render as chips next to the title when present.

## Won't

- Won't include the global cross-project heatmap from `/` — that one belongs on the home page.

## Cross-references

- `wiki/projects/<slug>.md` — source of project metadata (topics, summary, etc.)
- #455 (closed) — date-range chip pattern
