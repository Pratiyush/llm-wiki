# Reader-first article shell

> Status: scaffolded in v1.2.0 (#112). Opt-in per page via frontmatter;
> default rendering is unchanged. The module ships the layout + CSS +
> slot contract; gradual adoption across the 647 session pages happens
> in follow-up PRs.

## Why

Today's session pages render as transcripts (frontmatter → summary →
conversation → connections). The "reader shell" wraps the same content
in a **Wikipedia-style encyclopedia layout** so pages feel like articles
someone wrote, not logs someone dumped.

```
┌──────────────────────────────────────────────────────────────┐
│  Browse drawer  │  Article header + utility bar              │
│  (nav pane)     ├────────────────────┬────────────────────── │
│                 │  Article body      │  Infobox              │
│                 │                    ├────────────────────── │
│                 │                    │  Revisions            │
│                 │                    ├────────────────────── │
│                 │                    │  See also             │
│                 │                    ├────────────────────── │
│                 │                    │  References           │
└─────────────────┴────────────────────┴────────────────────── ┘
```

## Opting in

Add `reader_shell: true` to the page's frontmatter:

```yaml
---
title: "RAG"
type: concept
reader_shell: true       # ← this page renders through the new shell
last_updated: 2026-04-19
---
```

Pages without the flag render through the existing pipeline **exactly
as before**. No existing selectors are redefined; shell CSS is scoped
under `.reader-shell` so it can't leak.

## Slots

Every slot is **optional** — empty ones collapse (no empty chrome).
Builders populate a :class:`ShellSlots` instance and pass it to
:func:`render_article_shell`.

| Slot | Source | Content |
|---|---|---|
| `title` | `title` frontmatter field | `<h1>` |
| `subtitle` | `subtitle` frontmatter or derived | one-line tagline under h1 |
| `breadcrumbs` | pipeline-computed | nav path to the page |
| `utility_actions` | pipeline defaults | copy markdown, download `.txt`, view raw |
| `body_html` | rendered markdown | the main article prose |
| `infobox` | `extract_infobox_fields(meta)` | metadata table (type, project, model, lifecycle, cache_tier, confidence, dates) |
| `drawer_links` | `drawer_links` frontmatter or project default | left-pane browse list |
| `revisions` | build-pipeline revision log | (date, summary) pairs |
| `see_also` | parsed `## Connections` section | outbound wikilinks as a see-also list |
| `references` | parsed `## Sources` / `## References` | citations list |

### Auto-extracted infobox fields

From `llmwiki/reader_shell.py :: INFOBOX_FIELDS_IN_ORDER`:

| Frontmatter key | Label |
|---|---|
| `type` | Type |
| `entity_type` | Entity type |
| `project` | Project |
| `model` | Model |
| `lifecycle` | Lifecycle |
| `cache_tier` | Cache tier |
| `confidence` | Confidence (formatted to 2 decimals if float in `[0, 1]`) |
| `last_updated` | Last updated |
| `date` | Date |

Unknown frontmatter keys don't end up in the infobox — add them to
`INFOBOX_FIELDS_IN_ORDER` + `INFOBOX_FIELD_LABELS` in the module if
you want them surfaced.

## Python API

```python
from llmwiki.reader_shell import (
    ShellSlots,
    build_slots,
    extract_infobox_fields,
    is_reader_shell_enabled,
    render_article_shell,
)

if is_reader_shell_enabled(meta):
    slots = build_slots(
        title=meta.get("title", ""),
        body_html=rendered_body,
        meta=meta,
        breadcrumbs=[("Home", "/"), ("Concepts", "/concepts/"), ("RAG", "")],
        see_also=[("Karpathy", "/entities/Karpathy.html")],
        references=[("Original gist", "https://gist.github.com/karpathy/…")],
        utility_actions=[
            ("Copy markdown", "javascript:copyMarkdown()"),
            ("Download .txt", "./page.txt"),
        ],
    )
    shell_html = render_article_shell(slots)
    # Wrap the existing <main> template body with shell_html.
else:
    # Existing rendering path — no changes.
    ...
```

## CSS

Inline CSS lives in `llmwiki/reader_shell.py :: READER_SHELL_CSS` and is
appended to the main site CSS at build time. All selectors namespace
under `.reader-shell`:

- `.reader-shell` — outer CSS grid (drawer | main | rail)
- `.reader-shell__drawer` — left navigation pane (sticky)
- `.reader-shell__main` — center article column
- `.reader-shell__header` — title + breadcrumbs + utility bar
- `.reader-shell__utility` — action button row
- `.reader-shell__body` — article prose
- `.reader-shell__rail` — right side-column (sticky)
- `.reader-shell__infobox` — metadata table (dl/dt/dd)
- `.reader-shell__revisions` — revision history section
- `.reader-shell__see-also` — see-also links
- `.reader-shell__references` — references links

### Responsive breakpoints

- **≤ 760 px** — single column, rail collapses below body.
- **761–1100 px** — two columns (body + rail). Drawer hidden.
- **≥ 1101 px** — three columns (drawer + body + rail).

## Accessibility

- Breadcrumbs use `<nav aria-label="Breadcrumb">` with `aria-current="page"` on the last entry.
- Infobox uses `<aside aria-label="Metadata">` + a `<dl>` for screen-reader-friendly semantics.
- Utility bar uses `role="toolbar" aria-label="Page actions"`.
- Rail sections each carry `aria-label` matching their heading.
- Empty drawer shows explanatory copy rather than blank space so no one
  lands on an unlabelled region.

## XSS safety

- `body_html` is trusted (comes from the build pipeline's markdown
  renderer) — passed through verbatim.
- Every other slot is HTML-escaped at render time:
  - Titles, subtitles, breadcrumb labels, infobox values, link labels,
    revision summaries, utility button labels, drawer link text.
- A malicious frontmatter `title: "<script>"` renders as
  `&lt;script&gt;` — safe.

## Non-goals (#112 explicitly scoped out)

- **Revision tracking pipeline.** The slot exists; the build pipeline
  doesn't compute the list yet. Today callers pass an empty
  `revisions=[]` or derive from git log.
- **Automatic `see_also` extraction from `## Connections`.** Callers
  pass the list in explicitly; the parser landing with #112 is scope
  creep. (Parsed on the caller side, using `WIKILINK_RE` from
  `llmwiki/lint/__init__.py`.)
- **Converting all 647 session pages.** The scaffold ships opt-in so
  the first real adopter is a maintainer-chosen page. Bulk migration is
  a follow-up.

## Live adopters (#285)

Pages with `reader_shell: true` as of v1.1.0-rc8:

| Page | Why |
|---|---|
| [`wiki/entities/ClaudeSonnet4.md`](../../wiki/entities/ClaudeSonnet4.md) | Flagship model entity — has infobox-worthy pricing, benchmarks, modalities that map cleanly to the Wikipedia-style shell |
| [`wiki/projects/llm-wiki.md`](../../wiki/projects/llm-wiki.md) | Meta project page — showcases `reader_shell` on the framework's own canonical page |

To opt a page in, add `reader_shell: true` to its frontmatter and rebuild with `llmwiki build`. The shell renders infobox + table of contents + references rail automatically from the page's existing frontmatter + wikilinks.

## Related

- `llmwiki/reader_shell.py` — implementation
- `llmwiki/render/css.py` — where `READER_SHELL_CSS` gets appended
- `docs/design/brand-system.md` — the CSS tokens this shell inherits
- `docs/reference/cache-tiers.md` — sibling opt-in feature, now also has live adopters (#285)
- `#112` — this issue
- `#114` — static prototype hub (the sibling layout surface)
- `#285` — live-adoption polish for this + cache_tier
