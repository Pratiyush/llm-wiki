"""Inline CSS for the static site (v1.1 · #217).

Extracted from ``llmwiki/build.py`` in the #217 refactor. Byte-identical
to the pre-refactor constant — verified by ``llmwiki build`` hash.

The full style sheet ships as a Python string so the builder can inline
it into every page without needing a separate request. Theme toggle
variables, highlight.js overrides, heatmap colors, tool-chart tokens,
and mobile/print media queries all live here.
"""

from __future__ import annotations

CSS = """/* llmwiki — god-level docs style */
:root {
  --bg: #ffffff;
  --bg-alt: #f8fafc;
  --bg-card: #ffffff;
  --bg-code: #edf0f5;                      /* v1.0 #119: slightly darker for better contrast */
  --text: #0f172a;
  --text-secondary: #475569;
  --text-muted: #6b7280;                   /* WCAG AA: 4.84:1 on white, 4.63:1 on --bg-alt */
  --border: #d1d5db;                       /* v1.0 #119: stronger card borders (was #e2e8f0) */
  --border-subtle: #e2e8f0;                /* for less prominent separators */
  --accent: #7C3AED;
  --accent-light: #a78bfa;
  --accent-bg: #f5f3ff;
  --radius: 8px;
  --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
  --shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.04);
  --shadow-card: 0 1px 3px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04);  /* v1.0 #119: card shadow */
  --shadow-card-hover: 0 4px 12px rgba(15, 23, 42, 0.12), 0 2px 4px rgba(15, 23, 42, 0.06);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0c0a1d;
    --bg-alt: #110f26;
    --bg-card: #16142d;
    --bg-code: #1a1836;
    --text: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-muted: #8b9bb5;  /* WCAG AA: 6.97:1 on dark bg */
    --border: #2d2b4a;
    --border-subtle: #1f1d3a;
    --accent-bg: #1e1a3a;
    --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    --shadow-card: 0 2px 6px rgba(0, 0, 0, 0.35);
    --shadow-card-hover: 0 6px 16px rgba(0, 0, 0, 0.45);
  }
}
:root[data-theme="dark"] {
  --bg: #0c0a1d;
  --bg-alt: #110f26;
  --bg-card: #16142d;
  --bg-code: #1a1836;
  --text: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #8b9bb5;
  --border: #2d2b4a;
  --border-subtle: #1f1d3a;
  --accent-bg: #1e1a3a;
  --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
  --shadow-card: 0 2px 6px rgba(0, 0, 0, 0.35);
  --shadow-card-hover: 0 6px 16px rgba(0, 0, 0, 0.45);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }
body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.7; -webkit-font-smoothing: antialiased; overflow-wrap: break-word; word-wrap: break-word; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
/* Skip-to-content link — visible only on keyboard focus */
.skip-link { position: absolute; left: -9999px; top: auto; width: 1px; height: 1px; overflow: hidden; z-index: 999; padding: 8px 16px; background: var(--accent); color: #fff; font-weight: 600; font-size: 0.9rem; border-radius: 0 0 6px 0; text-decoration: none; }
.skip-link:focus { position: fixed; top: 0; left: 0; width: auto; height: auto; overflow: visible; }
.container { max-width: 1080px; margin: 0 auto; padding: 0 24px; }
.muted { color: var(--text-muted); }
kbd { display: inline-block; padding: 2px 6px; font-family: var(--mono); font-size: 0.72rem; color: var(--text-secondary); background: var(--bg-code); border: 1px solid var(--border); border-radius: 4px; line-height: 1; }

/* Reading progress bar */
.progress-bar { position: fixed; top: 0; left: 0; height: 3px; width: 0%; background: var(--accent); z-index: 200; transition: width 0.1s; }

/* Nav */
/* v1.0 #119: add a subtle shadow + stronger blur so the nav stays grounded on light backgrounds */
.nav { position: sticky; top: 0; z-index: 100; background: var(--bg); border-bottom: 1px solid var(--border); box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
.nav-inner { max-width: 1080px; margin: 0 auto; padding: 0 24px; height: 56px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.nav-brand { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 0.95rem; color: var(--text); text-decoration: none; flex-shrink: 0; }
.nav-brand:hover { text-decoration: none; }
.nav-links { display: flex; align-items: center; gap: 16px; }
.nav-links a { color: var(--text-secondary); font-size: 0.86rem; font-weight: 500; text-decoration: none; }
.nav-links a:hover { color: var(--text); text-decoration: none; }
.nav-links a.active { color: var(--accent); }

.nav-search-btn { display: flex; align-items: center; gap: 8px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; font-family: var(--font); color: var(--text-secondary); cursor: pointer; font-size: 0.82rem; transition: all 0.15s; }
.nav-search-btn:hover { border-color: var(--accent); color: var(--accent); }
.nav-search-btn svg { flex-shrink: 0; }
@media (max-width: 767px) { .nav-search-btn span, .nav-search-btn kbd { display: none; } }
/* Tablet + mobile: the six text anchors (Home/Projects/Sessions/Models/Compare/Changelog)
   overflow a 768px viewport at 0.9rem/gap-20, so collapse them below the
   1024 desktop breakpoint. Users still have Search + Theme in the top nav,
   the command palette via Cmd+K, and the mobile bottom nav below 767. */
@media (max-width: 1023px) { .nav-links > a { display: none; } }

.theme-toggle { background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-secondary); transition: all 0.2s; padding: 0; flex-shrink: 0; }
.theme-toggle:hover { border-color: var(--accent); color: var(--accent); }
.theme-toggle svg { width: 18px; height: 18px; }
.theme-toggle .icon-sun { display: none; }
.theme-toggle .icon-moon { display: block; }
:root[data-theme="dark"] .theme-toggle .icon-sun { display: block; }
:root[data-theme="dark"] .theme-toggle .icon-moon { display: none; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .theme-toggle .icon-sun { display: block; }
  :root:not([data-theme="light"]) .theme-toggle .icon-moon { display: none; }
}

/* Hero */
.hero { padding: 56px 0 40px; margin-bottom: 20px; background: var(--bg-alt); border-bottom: 1px solid var(--border); }
.hero-sm { padding: 32px 0 24px; margin-bottom: 12px; }
.hero h1 { font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; color: var(--text); margin-bottom: 8px; overflow-wrap: break-word; }
.hero .hero-sub { color: var(--text-secondary); font-size: 0.9rem; line-height: 1.6; overflow-wrap: break-word; }
.hero .hero-sub code { font-family: var(--mono); background: var(--bg-card); padding: 1px 6px; border-radius: 4px; font-size: 0.82rem; border: 1px solid var(--border); }
.hero .hero-sub a { color: var(--accent); font-weight: 500; }

/* Breadcrumbs */
.breadcrumbs { font-size: 0.82rem; color: var(--text-muted); margin-bottom: 16px; }
.breadcrumbs a { color: var(--text-secondary); text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 2px; text-decoration-color: var(--border); }
.breadcrumbs a:hover { color: var(--accent); text-decoration: underline; }
.breadcrumbs .crumb-sep { margin: 0 6px; color: var(--text-muted); }
.breadcrumbs [aria-current="page"] { color: var(--text); font-weight: 500; }

/* Section */
.section { padding: 28px 0 32px; }
.section h2 { font-size: 1.5rem; font-weight: 700; margin: 24px 0 16px; color: var(--text); }
.section h3 { font-size: 1.15rem; font-weight: 600; margin: 20px 0 10px; color: var(--text); }

.meta-tools { font-size: 0.82rem; margin-bottom: 12px; overflow-wrap: break-word; }

/* Actions strip */
.session-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
.btn { display: inline-flex; align-items: center; padding: 6px 14px; font-size: 0.82rem; font-weight: 500; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; color: var(--text-secondary); cursor: pointer; text-decoration: none; transition: all 0.15s; font-family: var(--font); }
.btn:hover { border-color: var(--accent); color: var(--accent); text-decoration: none; }
.btn-primary { background: var(--accent); color: #ffffff; border-color: var(--accent); }
.btn-primary:hover { background: var(--accent-light); border-color: var(--accent-light); color: #ffffff; }
.btn.copied { background: var(--accent-bg); color: var(--accent); border-color: var(--accent); }

/* Code copy button */
.code-wrap { position: relative; }
.copy-code-btn { position: absolute; top: 8px; right: 8px; padding: 4px 10px; font-size: 0.72rem; font-weight: 500; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; color: var(--text-secondary); cursor: pointer; font-family: var(--font); opacity: 0; transition: opacity 0.15s; z-index: 2; }
.code-wrap:hover .copy-code-btn { opacity: 1; }
.copy-code-btn:hover { border-color: var(--accent); color: var(--accent); }
.copy-code-btn.copied { background: var(--accent-bg); color: var(--accent); border-color: var(--accent); opacity: 1; }

/* Content */
.content { color: var(--text); font-size: 0.95rem; max-width: 100%; overflow-wrap: break-word; word-wrap: break-word; min-width: 0; }
.content h1, .content h2, .content h3, .content h4 { margin: 28px 0 12px; font-weight: 600; color: var(--text); scroll-margin-top: 72px; overflow-wrap: break-word; }
.content h1 { font-size: 1.6rem; }
.content h2 { font-size: 1.3rem; border-bottom: 1px solid var(--border); padding-bottom: 6px; margin-top: 36px; }
.content h3 { font-size: 1.08rem; color: var(--accent); }
.content h4 { font-size: 0.98rem; color: var(--text-secondary); }
.content p { margin: 12px 0; color: var(--text); overflow-wrap: break-word; }
.content ul, .content ol { margin: 12px 0 12px 24px; }
.content li { margin: 4px 0; overflow-wrap: break-word; word-wrap: break-word; }
.content li code { word-break: break-all; }
.content code { font-family: var(--mono); background: var(--bg-code); padding: 2px 6px; border-radius: 4px; font-size: 0.82em; word-break: break-word; overflow-wrap: anywhere; }
.content pre { background: var(--bg-code); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; overflow-x: auto; overflow-y: hidden; margin: 16px 0; font-size: 0.82rem; line-height: 1.5; max-width: 100%; white-space: pre; }
.content pre code { background: none; padding: 0; font-size: inherit; word-break: normal; white-space: pre; overflow-wrap: normal; }
.content blockquote { border-left: 3px solid var(--accent); padding: 8px 16px; color: var(--text-secondary); background: var(--accent-bg); margin: 16px 0; border-radius: 0 var(--radius) var(--radius) 0; }
.content table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.88rem; display: block; overflow-x: auto; }
.content th, .content td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; overflow-wrap: break-word; }
.content th { background: var(--bg-alt); font-weight: 600; }
.content tr:nth-child(even) { background: var(--bg-alt); }
.content strong { font-weight: 600; }
.content hr { border: none; border-top: 1px solid var(--border); margin: 32px 0; }
.content .headerlink { opacity: 0; margin-left: 8px; color: var(--text-muted); font-weight: 400; text-decoration: none; }
.content h1:hover .headerlink, .content h2:hover .headerlink, .content h3:hover .headerlink, .content h4:hover .headerlink { opacity: 1; }

/* v0.5: highlight.js owns token colours (see hljs-light / hljs-dark <link>
   tags in page_head). We only style the code block container so it matches
   the rest of the wiki's visual language. */
.article pre,
.article pre code.hljs {
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin: 16px 0;
  overflow-x: auto;
}
.article pre code.hljs { padding: 14px 16px; display: block; }
.article pre { padding: 0; }
.article :not(pre) > code.hljs { background: transparent; padding: 0; }
/* a11y: GitHub hljs theme keyword #d73a49 only has 4.17:1 on --bg-code;
   override to #c23a40 (4.82:1) for WCAG AA compliance in light mode. */
:root:not([data-theme="dark"]) .hljs-keyword,
:root:not([data-theme="dark"]) .hljs-type { color: #c23a40; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .hljs-keyword, :root:not([data-theme="light"]) .hljs-type { color: unset; } }

/* Cards */
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin: 16px 0; }
.card { display: block; padding: 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); text-decoration: none; color: var(--text); transition: all 0.15s; box-shadow: var(--shadow-card); }
.card:hover { border-color: var(--accent); text-decoration: none; transform: translateY(-1px); box-shadow: var(--shadow-card-hover); }
.card-title { font-weight: 600; font-size: 0.95rem; margin-bottom: 4px; color: var(--text); }
.card-meta { font-size: 0.82rem; color: var(--text-secondary); }
.card-stats { font-size: 0.78rem; margin-top: 6px; }
.card-badge { margin-top: 8px; }

/* Content-freshness badge (#57) */
.freshness {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 2px 10px; border-radius: 999px;
  font-size: 0.72rem; font-weight: 600; white-space: nowrap;
  border: 1px solid;
}
.freshness::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: currentColor;
}
.fresh-green   { color: #15803d; background: #dcfce7; border-color: #86efac; }
.fresh-yellow  { color: #b45309; background: #fef3c7; border-color: #fcd34d; }
.fresh-red     { color: #b91c1c; background: #fee2e2; border-color: #fca5a5; }
.fresh-unknown { color: #6b7280; background: #f3f4f6; border-color: #d1d5db; }
:root[data-theme="dark"] .fresh-green   { color: #86efac; background: #052e16; border-color: #065f46; }
:root[data-theme="dark"] .fresh-yellow  { color: #fcd34d; background: #3a2a06; border-color: #78350f; }
:root[data-theme="dark"] .fresh-red     { color: #fca5a5; background: #3a0a0a; border-color: #7f1d1d; }
:root[data-theme="dark"] .fresh-unknown { color: #9ca3af; background: #1f2937; border-color: #374151; }
@media print {
  .freshness { background: #fff !important; color: #000 !important; border-color: #ccc !important; }
  .freshness::before { background: #000 !important; }
}

/* Sub-agent collapsible */
.sub-section { margin-top: 32px; }
.sub-section summary { font-size: 1.15rem; font-weight: 600; cursor: pointer; padding: 8px 0; color: var(--text-secondary); }
.sub-section summary:hover { color: var(--accent); }

/* Sessions table */
.table-wrap { max-width: 100%; overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg-card); }
.sessions-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.sessions-table thead { position: sticky; top: 56px; background: var(--bg-alt); z-index: 1; }
.sessions-table th, .sessions-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.sessions-table th { background: var(--bg-alt); font-weight: 600; color: var(--text-secondary); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }
.sessions-table tr:last-child td { border-bottom: none; }
.sessions-table tr:hover { background: var(--bg-alt); }
.sessions-table tr.selected { background: var(--accent-bg); }
.sessions-table td.num { text-align: right; font-variant-numeric: tabular-nums; color: var(--text-secondary); }
.sessions-table code { font-family: var(--mono); font-size: 0.82em; color: var(--text-secondary); }
.sessions-table tr[hidden] { display: none; }

/* Filter bar */
.filter-bar { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin-bottom: 16px; padding: 12px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); }
.filter-bar label { display: flex; flex-direction: column; gap: 4px; font-size: 0.72rem; color: var(--text-muted); font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; }
.filter-bar select, .filter-bar input { padding: 6px 10px; font-size: 0.85rem; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-family: var(--font); min-width: 140px; }
.filter-bar input[type="text"] { min-width: 180px; }
.filter-bar .btn { align-self: end; }
.filter-count { font-size: 0.78rem; margin-left: auto; align-self: end; }

/* Synthesis block */
.synthesis { background: var(--accent-bg); border: 1px solid var(--accent-light); border-radius: var(--radius); padding: 20px 24px; margin-bottom: 24px; }
.synthesis h2, .synthesis h3 { color: var(--accent); margin-top: 0; }
.synthesis p { margin: 10px 0; }

/* Command palette */
.palette { position: fixed; inset: 0; z-index: 300; display: none; }
.palette[aria-hidden="false"] { display: block; }
.palette-backdrop { position: absolute; inset: 0; background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(4px); }
.palette-modal { position: relative; max-width: 600px; margin: 10vh auto 0; background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow); overflow: hidden; }
.palette-header { display: flex; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--border); }
.palette-header svg { color: var(--text-muted); flex-shrink: 0; }
.palette-header input { flex: 1; background: transparent; border: none; outline: none; font-family: var(--font); font-size: 0.95rem; color: var(--text); }
.palette-header input::placeholder { color: var(--text-muted); }
.palette-results { list-style: none; max-height: 50vh; overflow-y: auto; padding: 6px 0; }
.palette-results li { padding: 10px 16px; cursor: pointer; border-left: 3px solid transparent; }
.palette-results li.active { background: var(--accent-bg); border-left-color: var(--accent); }
.palette-results li:hover { background: var(--bg-alt); }
.palette-results .result-title { font-weight: 500; font-size: 0.9rem; color: var(--text); }
.palette-results .result-meta { font-size: 0.75rem; color: var(--text-muted); margin-top: 2px; }
.palette-results .result-type { display: inline-block; padding: 1px 6px; background: var(--bg-code); border-radius: 3px; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.04em; margin-right: 6px; color: var(--accent); }
.palette-footer { display: flex; gap: 16px; padding: 10px 16px; border-top: 1px solid var(--border); font-size: 0.75rem; background: var(--bg-alt); }

/* Help dialog */
.help-dialog { position: fixed; inset: 0; z-index: 250; display: none; }
.help-dialog[aria-hidden="false"] { display: block; }
.help-modal { position: relative; max-width: 420px; margin: 15vh auto 0; background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 24px; box-shadow: var(--shadow); }
.help-modal h2 { font-size: 1.1rem; margin-bottom: 16px; }
.help-modal table { width: 100%; font-size: 0.88rem; margin-bottom: 16px; }
.help-modal td { padding: 6px 0; }
.help-modal td:first-child { width: 130px; }

/* Footer */
.footer { padding: 32px 0; border-top: 1px solid var(--border); margin-top: 48px; background: var(--bg-alt); }
.footer p { font-size: 0.85rem; color: var(--text-muted); text-align: center; }
.footer a { text-decoration: underline; text-underline-offset: 2px; }

/* Changelog page — narrow reading column + keep-a-changelog typography */
.container.narrow { max-width: 860px; }
.changelog-body { padding: 40px 0 64px; }
.changelog-body .article h2 { margin-top: 48px; padding-bottom: 8px; border-bottom: 1px solid var(--border); font-size: 1.5rem; }
.changelog-body .article h2:first-child { margin-top: 0; }
.changelog-body .article h3 { margin-top: 28px; font-size: 1.1rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; }
.changelog-body .article h4 { margin-top: 20px; font-size: 0.98rem; }
.changelog-body .article ul { margin: 12px 0 20px; padding-left: 22px; }
.changelog-body .article li { margin: 6px 0; line-height: 1.6; }
.changelog-body .article li > code,
.changelog-body .article p > code { font-size: 0.86rem; padding: 1px 6px; background: var(--bg-code); border-radius: 4px; }
.changelog-body .article p { line-height: 1.7; }
.changelog-body .article a { color: var(--accent); }
.changelog-body .article hr { margin: 36px 0; border: 0; border-top: 1px solid var(--border); }
.changelog-body .article blockquote { margin: 16px 0; padding: 8px 16px; border-left: 3px solid var(--accent); color: var(--text-secondary); background: var(--bg-alt); border-radius: 0 4px 4px 0; }

/* v0.4: Related pages panel */
.related-pages { margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--border); }
.related-pages h3 { font-size: 1.05rem; color: var(--text-secondary); margin-bottom: 12px; }
.related-pages ul { list-style: none; margin: 0; padding: 0; }
.related-pages li { padding: 6px 0; font-size: 0.9rem; border-bottom: 1px solid var(--border); }
.related-pages li:last-child { border-bottom: none; }

/* v0.8 (#64, #72): GitHub-style 365-day activity heatmap. Rendered as a
   build-time SVG in build.py (see llmwiki/viz_heatmap.py). The CSS custom
   properties below get picked up by the inlined SVG via its own <style>
   block so the colors swap with the page theme. The pre-v0.8 JS-based
   tiny-strip heatmap is gone. */
:root {
  --heatmap-0: #dde1e6;        /* v1.0 #119: darker level-0 for visibility on white */
  --heatmap-1: #9be9a8;
  --heatmap-2: #40c463;
  --heatmap-3: #30a14e;
  --heatmap-4: #216e39;
}
:root[data-theme="dark"] {
  --heatmap-0: #161b22;
  --heatmap-1: #0e4429;
  --heatmap-2: #006d32;
  --heatmap-3: #26a641;
  --heatmap-4: #39d353;
}
.heatmap-section { padding-top: 16px; padding-bottom: 16px; }
.activity-heatmap { margin-bottom: 24px; padding: 14px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); overflow-x: auto; }
.heatmap-label { font-size: 0.78rem; margin-bottom: 8px; }
.heatmap-svg { display: block; max-width: 100%; }
.heatmap-svg rect { transition: stroke 0.1s; }
.heatmap-svg rect:hover { stroke: var(--accent); stroke-width: 1; }

/* v0.8 (#65): Tool-call bar chart — rendered as pure SVG by
   llmwiki/viz_tools.py. CSS custom properties drive the category
   colors so the page theme can override them; dark-mode variants
   use saturated fills that read against the dark card background. */
:root {
  /* v1.0 #119: slightly less saturated in light mode — bars read cleaner on white card background */
  --tool-cat-io: #2563eb;
  --tool-cat-search: #9333ea;
  --tool-cat-exec: #ea580c;
  --tool-cat-network: #059669;
  --tool-cat-plan: #475569;
  --tool-cat-other: #6b7280;
}
:root[data-theme="dark"] {
  --tool-cat-io: #60a5fa;
  --tool-cat-search: #c084fc;
  --tool-cat-exec: #fb923c;
  --tool-cat-network: #34d399;
  --tool-cat-plan: #94a3b8;
  --tool-cat-other: #9ca3af;
}
.tool-chart-section { padding-top: 8px; padding-bottom: 16px; }
.tool-chart-card { margin: 16px 0 24px; padding: 14px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); overflow-x: auto; }
.tool-chart-label { font-size: 0.78rem; margin-bottom: 8px; }
.tool-chart-svg { display: block; max-width: 100%; }
.tool-chart-svg rect { transition: opacity 0.1s; stroke: rgba(15, 23, 42, 0.08); stroke-width: 1; }  /* v1.0 #119: thin stroke for bar definition */
:root[data-theme="dark"] .tool-chart-svg rect { stroke: rgba(255, 255, 255, 0.05); }
.tool-chart-svg rect:hover { opacity: 0.85; }

/* v0.8 (#66): Token usage card — stacked bars for four token categories
   plus a cache hit ratio badge. Rendered as plain HTML by
   llmwiki/viz_tokens.py. Colors follow the same category convention as
   the tool chart (blue = input, amber = cache_creation, green = cache_read,
   purple = output). */
:root {
  --token-input: #3b82f6;
  --token-cache-creation: #f59e0b;
  --token-cache-read: #10b981;
  --token-output: #a855f7;
  --token-area-fill: rgba(59, 130, 246, 0.22);
  --token-area-stroke: #3b82f6;
}
:root[data-theme="dark"] {
  --token-input: #60a5fa;
  --token-cache-creation: #fbbf24;
  --token-cache-read: #34d399;
  --token-output: #c084fc;
  --token-area-fill: rgba(96, 165, 250, 0.22);
  --token-area-stroke: #60a5fa;
}
.token-card { margin: 16px 0 24px; padding: 14px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); }
.token-card-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.token-card-title { font-weight: 600; font-size: 0.9rem; }
.token-card-total { font-size: 0.78rem; }
.token-row { display: grid; grid-template-columns: 120px 1fr 64px; gap: 10px; align-items: center; margin: 4px 0; font-size: 0.82rem; }
.token-label { color: var(--text-secondary); }
.token-bar-wrap { height: 10px; background: var(--bg-alt); border-radius: 3px; overflow: hidden; }
.token-bar { display: block; height: 100%; border-radius: 3px; }
.token-bar-input { background: var(--token-input); }
.token-bar-cache_creation { background: var(--token-cache-creation); }
.token-bar-cache_read { background: var(--token-cache-read); }
.token-bar-output { background: var(--token-output); }
.token-value { text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: var(--text-secondary); }
.token-ratio { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--border); font-size: 0.8rem; display: flex; gap: 8px; align-items: baseline; }
.token-ratio-label { color: var(--text-secondary); }
.token-ratio-value { font-weight: 600; font-size: 0.95rem; }
.token-ratio-value.tier-green   { color: #15803d; }
.token-ratio-value.tier-yellow  { color: #b45309; }
.token-ratio-value.tier-red     { color: #b91c1c; }
.token-ratio-value.tier-unknown { color: var(--text-secondary); }
:root[data-theme="dark"] .token-ratio-value.tier-green  { color: #86efac; }
:root[data-theme="dark"] .token-ratio-value.tier-yellow { color: #fcd34d; }
:root[data-theme="dark"] .token-ratio-value.tier-red    { color: #fca5a5; }
.token-ratio.tier-green   { background: rgba(34, 197, 94, 0.08); }
.token-ratio.tier-yellow  { background: rgba(234, 179, 8, 0.08); }
.token-ratio.tier-red     { background: rgba(239, 68, 68, 0.08); }
.token-ratio { padding: 8px 10px; border-radius: 4px; }
.token-timeline-svg { display: block; max-width: 100%; }

/* Site-wide token stats on the home page */
.token-stats-section { padding-top: 8px; padding-bottom: 16px; }
.token-stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 8px 0 24px; }
.token-stat { padding: 14px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); text-decoration: none; color: var(--text); display: block; }
a.token-stat:hover { border-color: var(--accent); }
.token-stat-label { font-size: 0.76rem; margin-bottom: 4px; }
.token-stat-value { font-size: 1.4rem; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
.token-stat-sub { font-size: 0.75rem; margin-top: 4px; }

/* v0.7 (#55): Model entity info card + /models/ sortable table. The
   `.model-card` is rendered by llmwiki/models_page.py.render_model_info_card;
   the `.models-table` is inside render_models_index. Both reuse existing
   theme vars — no new custom properties. */
.model-card { margin: 20px 0; padding: 18px 22px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); }
.model-card-header { display: flex; gap: 10px; align-items: baseline; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
.model-card-title { font-size: 1.25rem; font-weight: 700; }
.model-card-provider { font-size: 0.95rem; }
.model-card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px 18px; margin-bottom: 14px; }
.model-card-kv { display: flex; flex-direction: column; gap: 2px; font-size: 0.88rem; }
.model-card-kv .muted { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }
.model-card-row { display: flex; gap: 12px; align-items: baseline; font-size: 0.88rem; margin: 8px 0; }
.model-card-row-label { min-width: 80px; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }
.model-price-cell { margin-right: 14px; font-family: 'JetBrains Mono', monospace; }
.model-card-section-title { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 14px; margin-bottom: 8px; }
.model-card-benches { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); }
.model-bench-row { display: grid; grid-template-columns: 140px 1fr 52px; gap: 10px; align-items: center; margin: 4px 0; font-size: 0.85rem; }
.model-bench-label { color: var(--text-secondary); }
.model-bench-bar { height: 10px; background: var(--bg-alt); border-radius: 3px; overflow: hidden; }
.model-bench-fill { display: block; height: 100%; background: var(--accent); border-radius: 3px; }
.model-bench-value { text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: var(--text-secondary); }
.model-warnings { margin: 12px 0; padding: 10px 14px; background: rgba(234, 179, 8, 0.08); border: 1px solid #f59e0b; border-radius: 4px; font-size: 0.85rem; }
.model-warnings summary { cursor: pointer; font-weight: 600; color: #b45309; }
:root[data-theme="dark"] .model-warnings { background: rgba(234, 179, 8, 0.12); }
:root[data-theme="dark"] .model-warnings summary { color: #fcd34d; }
.models-table-wrap { overflow-x: auto; margin: 20px 0; }
.models-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.models-table th, .models-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.models-table th { font-weight: 600; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); background: var(--bg-alt); }
.models-table td { font-family: 'JetBrains Mono', monospace; }
.models-table td:first-child { font-family: inherit; }
.models-table tr:hover td { background: var(--bg-alt); }
.models-table a { color: var(--accent); text-decoration: none; font-weight: 500; }
.models-table a:hover { text-decoration: underline; }

/* v0.7 (#56): Changelog timeline + inline pricing sparkline + home
   "Recently updated" card. All rendered by llmwiki/changelog_timeline.py.
   Timeline is a vertical list with a connecting line on the left,
   newest entry first, numeric deltas colored by direction. */
.timeline-card { margin: 20px 0; padding: 18px 22px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); }
.timeline-card-title { font-size: 0.88rem; font-weight: 600; margin-bottom: 12px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }
.timeline-sparkline { display: flex; align-items: center; gap: 12px; padding: 6px 0 12px; font-size: 0.78rem; }
.timeline-sparkline .price-sparkline { flex: 0 0 auto; }
.changelog-timeline { list-style: none; margin: 0; padding: 0 0 0 18px; position: relative; border-left: 2px solid var(--border); }
.timeline-item { position: relative; padding: 8px 0 8px 16px; font-size: 0.88rem; }
.timeline-date { display: block; font-size: 0.76rem; color: var(--text-secondary); font-family: 'JetBrains Mono', monospace; margin-bottom: 2px; }
.timeline-dot { position: absolute; left: -23px; top: 14px; width: 8px; height: 8px; border-radius: 50%; background: var(--accent); border: 2px solid var(--bg-card); }
.timeline-body { display: block; }
.timeline-event { font-weight: 500; }
.timeline-detail { font-size: 0.82rem; color: var(--text-secondary); margin-top: 4px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.timeline-field { font-size: 0.78rem; padding: 1px 6px; background: var(--bg-alt); border-radius: 3px; }
.timeline-delta { display: inline-flex; gap: 6px; align-items: baseline; font-family: 'JetBrains Mono', monospace; }
.timeline-from { color: var(--text-secondary); text-decoration: line-through; text-decoration-thickness: 1px; }
.timeline-to { font-weight: 600; color: var(--text); }
.timeline-arrow { color: var(--text-secondary); }
.timeline-arrow-down { color: #15803d; }
.timeline-arrow-up { color: #b91c1c; }
:root[data-theme="dark"] .timeline-arrow-down { color: #86efac; }
:root[data-theme="dark"] .timeline-arrow-up { color: #fca5a5; }

.recently-updated-section { padding-top: 8px; padding-bottom: 16px; }
.recently-updated-card { margin: 8px 0 24px; padding: 14px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); }
.recently-updated-title { font-size: 0.78rem; margin-bottom: 10px; }
.recently-updated-list { list-style: none; margin: 0; padding: 0; }
.recently-updated-item { display: grid; grid-template-columns: 180px 100px 1fr; gap: 10px; align-items: baseline; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 0.88rem; min-width: 0; }
.recently-updated-item:last-child { border-bottom: none; }
.recently-updated-item > * { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recently-updated-item a { color: var(--accent); text-decoration: none; font-weight: 500; }
.recently-updated-item a:hover { text-decoration: underline; }
.recently-updated-date { font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; }
/* Below 640px the 180+100+1fr grid is too wide — collapse to a single
   column so each item stacks vertically instead of overflowing. */
@media (max-width: 639px) {
  .recently-updated-item { grid-template-columns: 1fr; gap: 2px; padding: 8px 0; }
  .recently-updated-item > * { white-space: normal; }
}

/* Project topics — GitHub-style tag chips on project cards, project
   detail pages, and the home-page grid. Rendered by
   llmwiki/project_topics.py. Tag colors are theme-neutral so the
   same style reads on both project cards (light background) and
   the project hero strip. */
.project-topics { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.topic-chip {
  display: inline-block;
  padding: 3px 10px;
  background: var(--bg-alt);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 500;
  line-height: 1.4;
  text-decoration: none;
  transition: all 0.1s;
}
a.topic-chip:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--bg-card);
}
.topic-chip-more { opacity: 0.7; }
.card-topics { margin-top: 8px; }
.card-topics .topic-chip { font-size: 0.68rem; padding: 2px 8px; }
.project-topics-section { padding-top: 12px; padding-bottom: 8px; }
.project-topics-section .container { padding-top: 16px; padding-bottom: 4px; }
.project-description { margin: 0 0 10px; font-size: 0.92rem; line-height: 1.5; max-width: 680px; }
.project-hero-topics { margin-bottom: 6px; }
.project-homepage { display: inline-block; margin-top: 6px; font-size: 0.82rem; color: var(--accent); text-decoration: none; }
.project-homepage:hover { text-decoration: underline; }

/* v0.7 (#58): Auto-generated vs-comparison pages. Side-by-side table
   with difference highlighting, benchmark bar chart, price delta, and
   a stub summary section the user fills in. */
.vs-section { margin: 24px 0; }
.vs-section h2 { font-size: 1.2rem; font-weight: 600; margin: 0 0 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.vs-table { width: 100%; border-collapse: collapse; margin: 12px 0 24px; font-size: 0.92rem; }
.vs-table th, .vs-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }
.vs-table th:first-child { width: 180px; color: var(--text-secondary); font-weight: 500; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.03em; }
.vs-table .vs-colhead { font-size: 1rem; background: var(--bg-alt); }
.vs-table .vs-colhead a { color: var(--accent); text-decoration: none; }
.vs-table .vs-colhead a:hover { text-decoration: underline; }
.vs-table td { font-family: 'JetBrains Mono', monospace; }
.vs-table .cell-diff { background: rgba(124, 58, 237, 0.08); font-weight: 600; }
:root[data-theme="dark"] .vs-table .cell-diff { background: rgba(167, 139, 250, 0.12); }
.vs-bench-chart { display: block; max-width: 100%; margin: 8px 0; }
.vs-summary-stub p { padding: 14px 18px; background: var(--bg-alt); border-left: 3px solid var(--accent); border-radius: 0 4px 4px 0; font-style: italic; }
.vs-index-table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 0.92rem; }
.vs-index-table th, .vs-index-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }
.vs-index-table th { font-weight: 600; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); background: var(--bg-alt); }
.vs-index-table a { color: var(--accent); text-decoration: none; font-weight: 500; }
.vs-index-table a:hover { text-decoration: underline; }
.vs-index-table tr:hover td { background: var(--bg-alt); }


/* Agent badge — shows which AI agent produced the session */
.agent-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  border: 1px solid;
  vertical-align: middle;
}
.agent-claude   { color: #7C3AED; background: rgba(124,58,237,0.1); border-color: rgba(124,58,237,0.3); }
.agent-codex    { color: #059669; background: rgba(5,150,105,0.1); border-color: rgba(5,150,105,0.3); }
.agent-copilot  { color: #2563EB; background: rgba(37,99,235,0.1); border-color: rgba(37,99,235,0.3); }
.agent-cursor   { color: #D97706; background: rgba(217,119,6,0.1); border-color: rgba(217,119,6,0.3); }
.agent-gemini   { color: #DC2626; background: rgba(220,38,38,0.1); border-color: rgba(220,38,38,0.3); }
.agent-obsidian { color: #7E22CE; background: rgba(126,34,206,0.1); border-color: rgba(126,34,206,0.3); }
.agent-pdf      { color: #B91C1C; background: rgba(185,28,28,0.1); border-color: rgba(185,28,28,0.3); }
.agent-unknown  { color: #6B7280; background: rgba(107,114,128,0.1); border-color: rgba(107,114,128,0.3); }
:root[data-theme="dark"] .agent-claude   { color: #A78BFA; background: rgba(167,139,250,0.15); border-color: rgba(167,139,250,0.3); }
:root[data-theme="dark"] .agent-codex    { color: #34D399; background: rgba(52,211,153,0.15); border-color: rgba(52,211,153,0.3); }
:root[data-theme="dark"] .agent-copilot  { color: #60A5FA; background: rgba(96,165,250,0.15); border-color: rgba(96,165,250,0.3); }
:root[data-theme="dark"] .agent-cursor   { color: #FBBF24; background: rgba(251,191,36,0.15); border-color: rgba(251,191,36,0.3); }
:root[data-theme="dark"] .agent-gemini   { color: #F87171; background: rgba(248,113,113,0.15); border-color: rgba(248,113,113,0.3); }
.sessions-table .agent-badge { font-size: 0.65rem; padding: 1px 6px; }

/* v0.4: Deep-link icon next to headings */
.content h2 .deep-link, .content h3 .deep-link, .content h4 .deep-link { margin-left: 8px; font-size: 0.8em; opacity: 0; text-decoration: none; transition: opacity 0.15s; }
.content h2:hover .deep-link, .content h3:hover .deep-link, .content h4:hover .deep-link { opacity: 0.7; }
.content h2 .deep-link:hover, .content h3 .deep-link:hover { opacity: 1; text-decoration: none; }

/* v0.4: Mark highlighting in search results */
mark { background: var(--accent-bg); color: var(--accent); padding: 0 2px; border-radius: 3px; font-weight: 500; }

/* Hover-to-preview wikilinks */
.wikilink-preview { position: fixed; max-width: 360px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow); padding: 12px 14px; z-index: 250; pointer-events: auto; font-size: 0.85rem; animation: fadeIn 0.1s ease-out; }
.wikilink-preview .wl-title { font-weight: 600; color: var(--text); margin-bottom: 6px; }
.wikilink-preview .wl-body { color: var(--text-secondary); font-size: 0.8rem; line-height: 1.5; max-height: 140px; overflow: hidden; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }

/* Timeline block on sessions index */
.timeline-block { margin-bottom: 16px; padding: 12px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); }
.timeline-label { font-size: 0.78rem; margin-bottom: 6px; }
.timeline-block svg rect { transition: opacity 0.15s; }
.timeline-block svg rect:hover { opacity: 1 !important; }

/* TOC sidebar (session pages, desktop only, injected by JS) */
.toc-sidebar { position: fixed; top: 88px; left: max(16px, calc((100vw - 1080px) / 2 - 240px)); width: 220px; max-height: calc(100vh - 120px); overflow-y: auto; padding: 12px 14px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); font-size: 0.82rem; z-index: 50; display: none; }
.toc-sidebar .toc-title { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); font-weight: 600; margin-bottom: 8px; }
.toc-sidebar ul { list-style: none; padding: 0; margin: 0; }
.toc-sidebar li { margin: 0; }
.toc-sidebar li.toc-h3 { padding-left: 12px; }
.toc-sidebar li.toc-h4 { padding-left: 24px; }
.toc-sidebar .toc-link { display: block; padding: 4px 8px; color: var(--text-secondary); border-left: 2px solid transparent; line-height: 1.4; text-decoration: none; border-radius: 0 4px 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.toc-sidebar .toc-link:hover { color: var(--text); background: var(--bg-alt); text-decoration: none; }
.toc-sidebar .toc-link.active { color: var(--accent); border-left-color: var(--accent); background: var(--bg-alt); font-weight: 500; }
@media (min-width: 1340px) { .toc-sidebar { display: block; } }

/* Mobile bottom navigation */
.mobile-bottom-nav { display: none; }
/* Mobile bottom nav breakpoint at 767 matches the common 768 tablet cutoff
   (Bootstrap/Tailwind). At 767 and below we show the bottom nav; at 768+
   we assume the user has enough horizontal room for the top-nav controls. */
@media (max-width: 767px) {
  .mobile-bottom-nav {
    display: flex; position: fixed; bottom: 0; left: 0; right: 0;
    background: var(--bg-card); border-top: 1px solid var(--border);
    padding: 6px 0 calc(6px + env(safe-area-inset-bottom, 0px));
    justify-content: space-around; align-items: center;
    z-index: 150; backdrop-filter: saturate(1.5) blur(8px);
    -webkit-backdrop-filter: saturate(1.5) blur(8px);
  }
  .mbn-link {
    display: flex; flex-direction: column; align-items: center; gap: 2px;
    background: none; border: none; color: var(--text-secondary);
    padding: 4px 10px; font-size: 0.66rem; font-weight: 500;
    text-decoration: none; cursor: pointer; font-family: inherit;
    min-width: 52px; transition: color 0.15s;
  }
  .mbn-link svg { width: 20px; height: 20px; stroke-width: 2; }
  .mbn-link:hover, .mbn-link:active { color: var(--accent); text-decoration: none; }
  .mbn-link.active { color: var(--accent); }
  body { padding-bottom: 76px; }
  .nav-links .nav-search-btn, .nav-links .theme-toggle { display: none; }
}

/* Print */
@media print {
  :root {
    --bg: #fff; --bg-alt: #fff; --bg-card: #fff; --bg-code: #f5f5f5;
    --text: #000; --text-secondary: #333; --text-muted: #555;
    --border: #ccc; --accent: #000;
  }
  .nav, .footer, .palette, .help-dialog, .session-actions, .filter-bar,
  .progress-bar, .nav-search-btn, .theme-toggle, .copy-code-btn,
  .wikilink-preview, .timeline-block, .toc-sidebar, .mobile-bottom-nav,
  .related-pages, .activity-heatmap, .tool-chart-card, .token-card, .token-stat-grid, .model-warnings, .timeline-card, .recently-updated-card, .deep-link, .breadcrumbs,
  .meta-tools { display: none !important; }
  body { background: #fff; color: #000; font-size: 11pt; padding-bottom: 0; }
  .hero { padding: 12px 0 8px; background: #fff; border: none; }
  .hero h1 { font-size: 18pt; color: #000; }
  .hero .hero-sub { color: #333; font-size: 10pt; }
  .container { max-width: 100%; padding: 0 12pt; }
  .content { font-size: 11pt; }
  .content h1, .content h2, .content h3, .content h4 { page-break-after: avoid; break-after: avoid; color: #000; }
  .content pre, .content blockquote, .content table, .content img, .content figure { page-break-inside: avoid; break-inside: avoid; }
  .content pre { border: 1px solid #ccc; background: #f8f8f8; font-size: 9pt; }
  .content code { font-size: 9pt; }
  .content a { color: #000; text-decoration: underline; }
  .content a[href^="http"]:after { content: " (" attr(href) ")"; font-size: 8pt; color: #555; word-break: break-all; }
  .content img, .content svg { max-width: 100%; height: auto; }
  article { max-width: 100% !important; }
  .section { padding: 0 !important; }
}
"""

# v1.2 (#112): reader-first article shell CSS. Appended so pages that
# don't opt in (via `reader_shell: true` frontmatter) keep rendering
# exactly as before — no existing selectors are redefined.
from llmwiki.reader_shell import READER_SHELL_CSS as _READER_SHELL_CSS  # noqa: E402
CSS = CSS + "\n" + _READER_SHELL_CSS

# v1.2 (#265): docs-shell CSS for the production documentation pages.
# Only pages with ``docs_shell: true`` frontmatter (the tutorials + the
# hub index) pick up these styles — selectors are all namespaced under
# ``.docs-shell`` so no existing page changes render.
from llmwiki.render.docs_css import DOCS_SHELL_CSS as _DOCS_SHELL_CSS  # noqa: E402
CSS = CSS + "\n" + _DOCS_SHELL_CSS
