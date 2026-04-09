# Accessibility (WCAG 2.1 AA)

llmwiki targets **WCAG 2.1 Level AA** for all generated HTML pages.

## Automated audit

We run [axe-core](https://github.com/dequelabs/axe-core) via
`axe-playwright-python` against four representative page types:

| Page type | Route |
|---|---|
| Home | `index.html` |
| Projects index | `projects/index.html` |
| Sessions index | `sessions/index.html` |
| Session detail | `sessions/<project>/<slug>.html` |

Run the audit locally:

```bash
PYTHONPATH=. python3 scripts/a11y_audit.py
```

Current status: **0 axe-core violations** across all four page types.

## What we cover

### Color contrast

All text meets the WCAG AA minimum contrast ratio:

| Token | Light mode | Dark mode | Min ratio |
|---|---|---|---|
| `--text` (body) | `#0f172a` on `#ffffff` | `#e2e8f0` on `#0c0a1d` | 4.5:1 |
| `--text-secondary` | `#475569` on `#ffffff` | `#94a3b8` on `#0c0a1d` | 4.5:1 |
| `--text-muted` | `#6b7280` on `#ffffff` (4.84:1) | `#8b9bb5` on `#0c0a1d` (6.97:1) | 4.5:1 |
| `--accent` (links) | `#7C3AED` on `#ffffff` | `#7C3AED` on `#0c0a1d` | 4.5:1 |
| hljs keywords | `#c23a40` on `#f1f5f9` (4.82:1) | theme default | 4.5:1 |

### Keyboard navigation

- **Skip-to-content link** (`<a class="skip-link">`) visible on first Tab press, jumps to `<main id="main-content">`
- **Focus indicators**: 2px solid `var(--accent)` outline on all interactive elements via `:focus-visible`
- **Command palette**: reachable via `Cmd+K` / `Ctrl+K`
- **Keyboard shortcuts**: `?` opens help dialog listing all shortcuts; `g h`, `g p`, `g s` for navigation; `j`/`k` for table rows
- **Tab order**: logical document order (nav > breadcrumbs > content > footer)

### Semantic HTML

- `<html lang="en">` on every page
- `<main id="main-content">` wraps all content
- `<nav aria-label="...">` for top nav, breadcrumbs, and mobile bottom nav
- `<header>`, `<footer>`, `<section>` used semantically
- Breadcrumbs use `aria-current="page"` on the current page
- Command palette uses `role="dialog"` + `aria-modal="true"` + `aria-label`

### Links in text blocks

Links within running text (footer, breadcrumbs) have underlines so they
are distinguishable without relying solely on color, per WCAG 1.4.1.

### Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

## Fixes applied (v0.9)

| Issue | Fix |
|---|---|
| `--text-muted` contrast 2.56:1 (light) / 4.09:1 (dark) | Darkened to `#6b7280` (light, 4.84:1) / `#8b9bb5` (dark, 6.97:1) |
| hljs `.hljs-keyword` 4.17:1 on `--bg-code` | Override to `#c23a40` (4.82:1) in light mode |
| Footer/breadcrumb links indistinguishable from text | Added underlines (dotted for breadcrumbs, solid for footer) |
| No skip-to-content link | Added `.skip-link` hidden except on `:focus` |
| `<main>` lacked `id` for skip target | Added `id="main-content"` |

## Out of scope

- **Screen reader testing**: VoiceOver smoke test recommended but not automated
- **WCAG AAA**: We target AA; AAA contrast (7:1) is not guaranteed for muted text
- **Third-party CDN content**: highlight.js theme colors beyond keyword/type are not overridden
