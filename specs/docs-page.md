# docs-page spec

## Goal

A single editorial doc rendered with the same site chrome as the rest of llmwiki. Same nav, same theme, same fonts.

## URL pattern

- `/docs/<page-name>.html`

## Must

- Page `<title>` contains the doc's frontmatter title.
- Top nav with active "Docs" link, identical to every other page.
- Theme attribute (`<html data-theme="dark|light">` or absent for system) persists from any prior page in this tab (closes #458).
- The body content matches `docs/<page>.md` rendered via the same `md_to_html` pipeline build.py uses.
- All wiki-internal links use relative paths so the page works on `file://` and any subdirectory deploy.

## Should

- Inline `<details>` summary blocks expand without navigating the page.
- A "Edit on GitHub" link in the page footer links to the source `.md` on master.

## Won't

- Won't render docs flagged `docs_shell: false` (those stay GitHub-rendered).

## Cross-references

- #458 (closed) — theme persistence on `/docs/`
- #282 — tutorial UX polish (in-page TOC + prev/next + edit-on-GitHub)
