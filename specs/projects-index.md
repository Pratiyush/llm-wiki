# projects-index spec

## Goal

Browseable index of every project in the wiki, with at-a-glance freshness signal so users see what's been touched recently.

## URL pattern

- `/projects/`
- `/projects/index.html`

## Must

- Page `<title>` contains "Projects".
- A grid of `.card` elements — one per discovered project.
- Each card has:
  - A project title (h2 or h3 inside the card).
  - A freshness badge with class one of: `fresh-green`, `fresh-yellow`, `fresh-red`.
  - A link target that routes to `/projects/<slug>.html`.
- The active nav link is "Projects".
- Cards are sorted by last-touched timestamp DESC (greenest first).

## Should

- Empty wikis (0 projects) render a friendly "No projects yet" message rather than an empty page.
- Hovering a card subtly elevates it (`box-shadow` transition, no layout shift).

## Won't

- Won't paginate. If a wiki has 1000 projects, all 1000 cards render and the page scrolls — pagination would be a follow-up feature, not silent truncation.

## Cross-references

- `tests/e2e/features/homepage.feature` — partial coverage of project-card rendering
- #455 (closed) — first/last-session date-range chip on cards
