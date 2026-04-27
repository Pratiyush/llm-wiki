# docs-hub spec

## Goal

Editorial index page for the docs site (`/docs/`). Tutorials, reference, deployment — all linked from one place.

## URL pattern

- `/docs/`
- `/docs/index.html`

## Must

- Page `<title>` contains "Docs".
- A sidebar table of contents (left side) with the major sections — NOT an inline `<details>` block in the body (closes the layout half of #457).
- The "Latest tagged release: vX.Y.Z" line MUST match `llmwiki.__version__` (closes the staleness half of #457; auto-substituted at build time via the `{{__llmwiki_version__}}` placeholder).
- Top nav active link is "Docs".
- Every link in the hub resolves (no 404 on internal docs links).

## Should

- The version line is hyperlinked to the matching GitHub Release.
- The TOC sidebar collapses to an accordion on viewports < 1024px (matches the responsive nav-hamburger breakpoint).
- The hub page itself is generated from `docs/index.md` via `compile_docs_site` (no separate hand-maintained HTML).

## Won't

- Won't auto-link to deferred / declined docs from `docs/maintainers/DECLINED.md`.

## Cross-references

- #457 (closed) — version auto-substitution shipped in v1.3.65; sidebar layout in v1.3.65 follow-up
- `llmwiki/docs_pages.py:compile_docs_site`
