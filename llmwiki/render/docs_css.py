"""Docs-specific visual system (v1.2.0 · #265).

"Minimalism + Trust & Authority" — quiet premium editorial aesthetic for
the `docs/` + `docs/tutorials/` pages when rendered into the static site.
Applied by adding `docs_shell: true` to the page's frontmatter.

Design brief (inherited from the brand-system doc #115):

- Max-width 760 px body (single-column reading), 1200 px hub grid.
- Inter 1.0625 rem / 1.75 line-height for prose, JetBrains Mono 0.9 rem
  for inline + block code.
- Type scale: h1 3.25 rem 700, h2 1.75 rem 650, h3 1.25 rem 600. Large
  numbered section markers (``01 · Install``).
- Single purple accent (#7C3AED) — same through-line as the rest of the
  site. Neutral off-white (#FAFAF9) background, deep ink (#0F172A) body.
- Hairline borders (1 px), zero drop shadows on content.
- Generous vertical rhythm: 96 px section padding, 48 px between
  h2 → h3 → p.
- Callouts: Trusted (emerald) / Warning (amber) / Result (violet) as the
  only editorial chrome.

Rules:

- Every selector is namespaced under `.docs-shell` so the styles only
  apply to pages that opt in via ``docs_shell: true``.
- Inherits brand-system CSS tokens rather than inventing new ones.
"""

from __future__ import annotations

# Docs-only CSS, appended to the main stylesheet. Scoped under
# `.docs-shell` so it can't leak onto regular session / entity pages.
DOCS_SHELL_CSS = """
/* --- Docs shell (v1.2.0 · #265) --- */
.docs-shell {
  max-width: 760px;
  margin: 0 auto;
  padding: 64px 32px 128px;
  font-family: var(--font);
  font-size: 1.0625rem;
  line-height: 1.75;
  color: var(--text);
  letter-spacing: -0.01em;
}

.docs-shell > h1,
.docs-shell > header h1 {
  font-size: 2.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 48px 0 20px;
  color: var(--text);
}

.docs-shell h2 {
  font-size: 1.75rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  line-height: 1.25;
  margin: 72px 0 20px;
  padding-top: 32px;
  border-top: 1px solid var(--border-subtle);
  color: var(--text);
}

.docs-shell h2:first-of-type {
  border-top: none;
  padding-top: 0;
  margin-top: 48px;
}

.docs-shell h3 {
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.3;
  margin: 48px 0 16px;
  color: var(--text);
}

.docs-shell h4 {
  font-size: 1rem;
  font-weight: 600;
  margin: 32px 0 12px;
  color: var(--text);
}

.docs-shell p,
.docs-shell ul,
.docs-shell ol {
  margin: 0 0 20px;
}

.docs-shell ul,
.docs-shell ol {
  padding-left: 1.6em;
}

.docs-shell li {
  margin: 8px 0;
}

.docs-shell li > p {
  margin: 0 0 8px;
}

/* Inline code */
.docs-shell p code,
.docs-shell li code,
.docs-shell td code,
.docs-shell th code {
  font-family: var(--mono);
  font-size: 0.875em;
  padding: 2px 6px;
  background: var(--bg-code);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  color: var(--text);
  letter-spacing: 0;
}

/* Code blocks */
.docs-shell pre {
  font-family: var(--mono);
  font-size: 0.9rem;
  line-height: 1.65;
  background: var(--bg-code);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 20px 24px;
  margin: 28px 0;
  overflow-x: auto;
  color: var(--text);
}

.docs-shell pre code {
  font-family: inherit;
  background: transparent;
  border: none;
  padding: 0;
  font-size: inherit;
  color: inherit;
}

/* Links */
.docs-shell a {
  color: var(--accent);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
  text-decoration-color: color-mix(in srgb, var(--accent) 35%, transparent);
  transition: text-decoration-color 0.12s ease;
}

.docs-shell a:hover {
  text-decoration-color: var(--accent);
}

/* Blockquote — used for the "Trusted" / "Warning" / "Result" callouts */
.docs-shell blockquote {
  margin: 28px 0;
  padding: 16px 24px;
  background: var(--accent-bg);
  border-left: 3px solid var(--accent);
  border-radius: 4px;
  color: var(--text);
}

.docs-shell blockquote p {
  margin: 0;
}

/* Horizontal rules — editorial dividers */
.docs-shell hr {
  margin: 72px auto;
  width: 56px;
  height: 1px;
  background: var(--border);
  border: none;
}

/* Tables — clean editorial look */
.docs-shell table {
  width: 100%;
  border-collapse: collapse;
  margin: 32px 0;
  font-size: 0.96rem;
}

.docs-shell thead th {
  text-align: left;
  font-weight: 600;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.docs-shell tbody td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: top;
  color: var(--text);
}

.docs-shell tbody tr:last-child td {
  border-bottom: none;
}

/* Frontmatter strip — "Time: 5 min · You'll need: …" stacked below the
   title as a hairline rule with one row per field. Grid keeps labels in
   a narrow left column so values align across fields + wrap cleanly. */
.docs-shell .docs-meta {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 8px 20px;
  padding: 20px 0;
  margin: 0 0 56px;
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
  font-size: 0.93rem;
  color: var(--text-secondary);
}

.docs-shell .docs-meta dt {
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  align-self: start;
  padding-top: 3px;
}

.docs-shell .docs-meta dd {
  margin: 0;
  line-height: 1.55;
  color: var(--text);
}

.docs-shell .docs-meta code {
  font-family: var(--mono);
  font-size: 0.85em;
  padding: 1px 6px;
  background: var(--bg-code);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
}

.docs-shell .docs-meta a {
  color: var(--accent);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
}

/* Tutorial lead-in — the first paragraph after the meta strip. The
   heading after it gives just enough rhythm; we lift the paragraph to
   a slightly larger size + calmer color so the "Why this matters"
   section header reads as a proper divider. */
.docs-shell > .docs-meta + hr + h2 + p,
.docs-shell > h1 + p {
  font-size: 1.15rem;
  line-height: 1.65;
  color: var(--text-secondary);
}

/* Emphasis for bold inline — a touch darker than regular body */
.docs-shell strong {
  font-weight: 600;
  color: var(--text);
}

/* Responsive */
@media (max-width: 760px) {
  .docs-shell {
    padding: 40px 20px 96px;
    font-size: 1rem;
    line-height: 1.7;
  }
  .docs-shell > h1 {
    font-size: 2.25rem;
  }
  .docs-shell h2 {
    font-size: 1.4rem;
    margin-top: 56px;
  }
  .docs-shell pre {
    padding: 16px 18px;
    border-radius: 6px;
  }
  .docs-shell table {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
  }
}

/* Dark mode — inherit all tokens, no overrides needed; just nudge blockquote */
:root[data-theme="dark"] .docs-shell blockquote {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .docs-shell blockquote {
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }
}

/* Hub index hero — applied to docs/index.md h1 only. Stays a full step
   bigger than tutorial h1 (2.75 rem) so the hub is unmistakably the
   landing page. */
.docs-shell.docs-hub > h1 {
  font-size: 3.5rem;
  letter-spacing: -0.03em;
  margin-bottom: 12px;
}

.docs-shell.docs-hub > h1 + p {
  font-size: 1.25rem;
  line-height: 1.55;
  color: var(--text-secondary);
  max-width: 620px;
  margin-bottom: 72px;
}

/* Passthrough pages (reference docs, adapter guides, deploy guides)
   get a gentler wrapper — same column width + typography, but the
   meta-strip / hub-hero accents don't apply. */
.docs-shell.docs-passthrough > h1 {
  font-size: 2.4rem;
}

@media (max-width: 760px) {
  .docs-shell.docs-hub > h1 {
    font-size: 2.5rem;
  }
  .docs-shell.docs-hub > h1 + p {
    font-size: 1.0625rem;
    margin-bottom: 48px;
  }
}
"""
