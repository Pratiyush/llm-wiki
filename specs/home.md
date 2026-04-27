# home spec

## Goal

The landing page for a built llmwiki. Within 5 seconds a visitor must understand what the site is, what they can do here, and where to go next.

## URL pattern

- `/`
- `/index.html`

## Must

- Page `<title>` contains "LLM Wiki".
- A visible hero heading with text "LLM Wiki" (h1).
- A subtitle paragraph mentioning "sessions".
- Top nav has links: Home, Projects, Sessions, Graph, Docs, Changelog.
- Active link in the nav is "Home" (carries `class="active"`).
- A 365-day activity heatmap section below the hero.
- A token-stats grid block (`.token-stat-grid`) below the heatmap.
- A project grid (`.card.card-project`) with at least one card.
- Each project card carries a freshness chip (`.freshness`) reflecting last-touched recency.
- Cmd+K (or `/`) opens the command palette without a full page navigation.
- "Skip to content" link is the first focusable element (a11y).
- Focus ring is visible when tabbing through interactive elements.

## Should

- The first project card is the most-recently-touched project.
- The page first-contentful-paint stays under 1 second on a built demo site.
- Scrolling the page revealing the project grid does not cause any layout shift (CLS = 0).
- Theme respects the system `prefers-color-scheme` on first visit and the saved choice on subsequent visits.

## Won't

- Won't ship inline session content on this page — only project cards summarising the corpus.
- Won't auto-redirect anywhere; this is the canonical entry point.

## Cross-references

- `tests/e2e/features/homepage.feature` — partial Gherkin coverage today
- #455 (closed) — required date range on project cards
- ADR-001 — Playwright stack (`docs/maintainers/ADR-001-playwright-stack.md`)
