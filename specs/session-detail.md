# session-detail spec

## Goal

Full transcript page for one session — every user message, every assistant response, every tool call. The "this is what I actually did" view.

## URL pattern

- `/sessions/<project>/<YYYY-MM-DD>-<slug>.html`

## Must

- Page `<title>` follows pattern `Session: <short-id> — <date> — LLM Wiki`.
- Breadcrumbs: `Home › Projects › <project> › <short-id>` (`.breadcrumbs`).
- An h1 carrying the session id and date.
- Tool-result blocks are wrapped in `<details class="collapsible-result">` and collapsed by default for results > 500 chars.
- Each fenced code block carries a `.copy-code-btn` with min-height 44px (WCAG touch target — closes one of the v1.3.67 fixes).
- A "Copy as markdown" button at the top copies the full transcript to clipboard.
- Per-page sibling files exist at the same path: `<page>.txt` (plain text) and `<page>.json` (structured metadata + body).
- Reading-time estimate visible in the header (e.g. "8 min read").
- Active nav link is "Sessions".

## Should

- Related-pages panel at the bottom links to other sessions in the same project + entity / concept pages mentioned in the body.
- Highlight.js syntax highlighting works in both light and dark themes.
- Deep-link icons appear next to every h2/h3 on hover.

## Won't

- Won't show raw `.jsonl` content — sessions are pre-rendered to clean markdown, not raw event streams.

## Cross-references

- `tests/e2e/features/session_page.feature`
- `tests/e2e/features/copy_markdown.feature`
- v1.3.67 (#679) — 44px touch-target fixes for `.copy-code-btn`
