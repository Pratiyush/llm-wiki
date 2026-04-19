# Editorial brand system

> Status: canonical reference for llmwiki's visual system (v1.2.0 · #115).
> If you're changing how any part of the generated site looks — or exporting a
> screenshot / OG image / PDF / slide deck — this document is the source of truth.

llmwiki is a **reading-first product**. The site is rendered locally from
markdown, then handed to the user like a book they wrote. The brand does three
things in service of that:

1. Get out of the way of the prose.
2. Make every page feel unmistakably like "an llmwiki page" — so the static
   site, the PDF export, a screenshot in a tweet, and a slide deck all read
   as a single product.
3. Work identically in light mode, dark mode, print, and Obsidian.

All tokens live in [`llmwiki/render/css.py`](../../llmwiki/render/css.py) as CSS
custom properties on `:root` + `[data-theme="dark"]`. This doc mirrors them so
contributors don't have to grep the CSS.

---

## 1. Typography

| Scale | Typeface | Weight | Use |
|---|---|---|---|
| Body | **Inter**, with `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` fallback | 400 | Body copy (line-height **1.7**) |
| Strong | Inter | 600 | Bold inline, labels, nav items |
| Headings | Inter | 600–700 | h1–h6; weight scales down with level |
| Code / mono | **JetBrains Mono**, with `'SF Mono', 'Fira Code', monospace` fallback | 400 | Inline code, pre blocks, keyboard shortcuts, CLI transcripts |

CSS tokens: `--font` (body/headings), `--mono` (code).

### Rules

- **Never ship web-font files.** Inter and JetBrains Mono have first-class
  system support on all three major OSes or load via the user's browser; we
  don't want a network request to render a wiki page.
- **Line-height 1.7** for body copy — reading-first density. Denser UI
  surfaces (nav, cards, tables) use 1.4–1.5.
- **Heading weight 600, not 700, below h2.** Keeps the hierarchy readable
  without shouting.
- **Monospace blocks use 0.875rem (14 px) at 1.6 line-height.** Tools outputs
  and code samples stay scannable without dominating the page.

### Why these two

- **Inter** — the same type family used by GitHub, Anthropic, Linear, Vercel.
  Neutral enough to disappear on long sessions, opinionated enough to feel
  intentional. Ships on macOS/Windows/Android out of the box; Linux gets a
  close match via the system fallback chain.
- **JetBrains Mono** — designed for reading code and diff output. Ligatures
  are left enabled (defaults to on in the typeface) because the audience is
  engineers.

---

## 2. Color palette

Every surface is a CSS variable so the whole palette flips in one place when
you toggle light/dark.

### Light mode (default)

| Token | Hex | Role |
|---|---|---|
| `--bg` | `#ffffff` | Primary page background |
| `--bg-alt` | `#f8fafc` | Secondary surfaces (tables, sidebars) |
| `--bg-card` | `#ffffff` | Cards, modals — same as bg but bordered |
| `--bg-code` | `#edf0f5` | Code block background (slightly darker than `--bg-alt` for contrast) |
| `--text` | `#0f172a` | Primary text (WCAG AAA on `--bg`) |
| `--text-secondary` | `#475569` | Labels, captions (WCAG AA+ on `--bg`) |
| `--text-muted` | `#6b7280` | Timestamps, de-emphasized info (WCAG AA) |
| `--border` | `#d1d5db` | Card borders, emphasized separators |
| `--border-subtle` | `#e2e8f0` | Hairline dividers |
| `--accent` | `#7C3AED` | Links, buttons, focus rings, brand marks |
| `--accent-light` | `#a78bfa` | Hover state, active tab underline |
| `--accent-bg` | `#f5f3ff` | Tinted background for accent-scoped blocks |

### Dark mode

Applied via either `@media (prefers-color-scheme: dark)` or explicit
`:root[data-theme="dark"]`:

| Token | Hex |
|---|---|
| `--bg` | `#0c0a1d` |
| `--bg-alt` | `#110f26` |
| `--bg-card` | `#16142d` |
| `--bg-code` | `#1a1836` |
| `--text` | `#e2e8f0` |
| `--text-secondary` | `#94a3b8` |
| `--text-muted` | `#8b9bb5` (WCAG AA: 6.97:1) |
| `--border` | `#2d2b4a` |
| `--border-subtle` | `#1f1d3a` |
| `--accent-bg` | `#1e1a3a` |

Accent `#7C3AED` stays the same in both themes — it's the through-line that
makes a screenshot recognizable even without the rest of the palette.

### Rules

- **WCAG 2.1 AA minimum** for every text/bg pair. Muted text in dark mode is
  explicitly checked to 6.97:1.
- **Accent is never used for body copy.** Links get it; body stays `--text`.
- **Status colors** use the same hues across light/dark:
  - success `#10b981` / hover `#059669`
  - warning `#f59e0b` / hover `#d97706`
  - danger `#ef4444` / hover `#dc2626`
  - info `#3b82f6` / hover `#2563eb`

---

## 3. Elevation + radius

| Token | Value | Use |
|---|---|---|
| `--radius` | `8px` | Cards, buttons, inputs, code blocks |
| `--shadow` | `0 10px 25px -5px rgba(15,23,42,.1), 0 8px 10px -6px rgba(15,23,42,.04)` | Heavy elements (command palette, modal) |
| `--shadow-card` | `0 1px 3px rgba(15,23,42,.08), 0 1px 2px rgba(15,23,42,.04)` | Default card resting state |
| `--shadow-card-hover` | `0 4px 12px rgba(15,23,42,.12), 0 2px 4px rgba(15,23,42,.06)` | Card hover |

Dark-mode shadows use the same geometry with higher alpha (`0.35` → `0.45`)
so they read against the deep backgrounds.

### Rules

- **One radius.** 8 px everywhere; smaller elements (code snippets, pill
  badges) use 4 px — see next section.
- **Two shadow steps max** per page. More than that reads as a UI tour, not
  a document.
- **Never use `border-radius: 50%`** except on avatars — full circles
  signal "interactive control" and compete with links.

### Smaller radius variants

Used inline, not as tokens (small surface area, low reuse):

- `4px` — inline `code`, keyboard chips (`<kbd>`), per-cell filter pills
- `4px` — `copy-code-btn`, heading deep-link anchors
- `6px` — nav controls, theme toggle, secondary buttons

---

## 4. Motion

llmwiki is a reading surface — motion should be almost invisible. Every
timing, duration, and easing choice below is deliberately boring.

| Token | Value | Use |
|---|---|---|
| `--transition-micro` | `0.1s ease` | Heatmap cell tooltip, tool-chart bar tooltip |
| `--transition-fast` | `0.15s ease` | Card hover, nav link, deep-link anchor, button |
| `--transition-med` | `0.2s ease` | Theme toggle background, palette mount |
| `--transition-slow` | `0.3s ease` | Reserved for command palette fade |

These aren't yet extracted as tokens in `css.py` — individual rules inline
the literal seconds. Extracting is tracked as a future cleanup.

### Rules

- **Respect `prefers-reduced-motion`.** `css.py` already sets
  `animation-duration: 0.01ms` and `transition-duration: 0.01ms` when the
  user-agent asks for it. Any new animation must not opt out.
- **No page-level scroll hijacking.** `scroll-behavior: smooth` on `html`
  is fine; JS-driven scroll animations are not.
- **Hover effects are reversible.** If you darken a card on hover, the off
  state is reached by reversing the same transition, not a new one.
- **Never auto-play.** Heatmaps, graphs, and timelines render once — they
  don't loop.

---

## 5. Spacing

No scale token yet — spacing is inlined in rules (padding/gap/margin). The
canonical steps used across the codebase:

- **2 px** — border-radius adjustments, hairline separators
- **4 px** — icon gaps, inline-code padding
- **8 px** — button padding, card inner gap (`gap-2`)
- **12 px** — paragraph spacing, list indent
- **16 px** — card padding (resting), section gap
- **24 px** — major section separators, hero padding
- **32–48 px** — page-level container padding at ≥ 768 px

A future token pass (`--space-1`…`--space-6`) is on the roadmap; until then,
stay inside this set when adding rules to keep the rhythm consistent.

---

## 6. Export consistency

All generated artifacts must inherit the same tokens:

| Artifact | Inherits |
|---|---|
| Static HTML site (`site/`) | Full CSS from `llmwiki/render/css.py` |
| Graph viewer (`site/graph.html`) | `--g-*` palette mirroring the main site |
| PDF export (future) | Print stylesheet adds explicit black-on-white + page breaks |
| Marp slide export | Keeps Inter + JetBrains Mono + `#7C3AED` accent |
| QMD export | Quarto theme sets body = Inter, mono = JetBrains Mono |
| Obsidian vault (via symlink) | Reads `.obsidian/themes/llmwiki.css` (future) |
| Screenshots in README | Taken in light mode for consistency |

### Social preview image

When a page links externally (OpenGraph / `twitter:image`):

- Background: `#0c0a1d` (dark bg)
- Heading: Inter 700, 72 px, `#e2e8f0`
- Accent stripe: `#7C3AED` 4 px × full width along the top
- Logo wordmark: "llm**wiki**" — Inter 800, 120 px, `#a78bfa` for "llm",
  `#e2e8f0` for "wiki"

---

## 7. Do / don't

**Do**
- Let the text breathe — line-height 1.7 for any paragraph > 3 lines.
- Keep cards borderless-ish — 1 px `--border-subtle` with `--shadow-card`.
- Use `--accent` for one thing per section (a link, a badge, a button —
  not all three).
- Flip the whole palette via `data-theme`, not per-component opt-ins.
- Match existing radius/shadow tokens before inventing new values.

**Don't**
- Don't mix mono and sans in the same run of prose. Pick Inter, drop into
  mono only for `code`.
- Don't use accent on body copy.
- Don't add a third shadow level.
- Don't use custom web fonts — Inter + JetBrains Mono are the only two.
- Don't build contrast into the HTML (e.g. `<span style="color:white">`);
  always go through a variable so the theme toggle works.

---

## 8. Changelog for this doc

When you change a token or add a scale step, add a one-line entry to
[`CHANGELOG.md`](../../CHANGELOG.md) under `### Changed` with the new token
name + value + where it's used. That keeps the brand history traceable in
the release notes.

## Related

- `llmwiki/render/css.py` — source of truth for every CSS variable
- `llmwiki/render/js.py` — theme toggle + palette sync logic
- `docs/reference/cache-tiers.md` — also uses the accent palette for badges
- `#115` — this issue
