# sessions-index spec

## Goal

Browseable, filterable table of every session across every project. The single page where a user goes to find "that session I had two weeks ago about X".

## URL pattern

- `/sessions/`
- `/sessions/index.html`

## Must

- Page `<title>` contains "Sessions".
- A `.filter-bar` block above the table containing:
  - `<select id="filter-project">` with one option per project plus "All projects".
  - `<select id="filter-model">` with one option per model plus "All models".
  - `<input id="filter-text" placeholder="Filter by slug…">` — text-search across slug.
  - `<input id="filter-date-from" type="date">` and `<input id="filter-date-to" type="date">`.
  - A `#filter-count` badge showing live "N shown" count.
- Each filter has a visible label (a11y — closes #454).
- A `.sessions-table` rendering one row per session with columns: Session, Agent, Project, Date, Model, Msgs, Tools.
- The activity timeline above the table reports calendar span (e.g. "365 days · 42 active") not just day count (closes #453).
- The Session column shows a unique slug per row (no Date duplicates between Session and Date columns — closes #452).
- Sticky header so column headings stay visible while scrolling.
- Active nav link is "Sessions".

## Should

- Filters operate purely client-side (no server round-trip).
- Filter state persists across navigation via `sessionStorage` so going to a session and clicking back keeps the user's filter selection.
- Empty filter state renders "0 of N shown" rather than hiding the table chrome.

## Won't

- Won't load full session bodies inline — the table is metadata only.
- Won't paginate; sticky-header scroll is the answer for large corpora.

## Cross-references

- `tests/e2e/features/responsive.feature` — sticky-header coverage
- #452, #453, #454 (all closed) — column layout, timeline label, filter a11y
