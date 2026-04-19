"""llmwiki — static HTML site builder.

Reads converted markdown sources under `raw/` and produces a complete static
site under `site/` with:

- Home + projects index + sessions index + per-project + per-session pages
- Inter + JetBrains Mono typography, purple accent (#7C3AED)
- Light / dark theme toggle (data-theme + system preference + localStorage)
- Global search index (site/search-index.json) — client-side fuzzy matcher
- Cmd+K command palette (vanilla JS, no framework)
- Keyboard shortcuts: /, g h, g p, g s, j/k, ?
- highlight.js client-side syntax highlighting (CDN, light + dark themes)
- Collapsible tool-result sections (<details>) for long outputs
- Copy-as-markdown + copy-code buttons (Clipboard API + execCommand fallback)
- Breadcrumbs + reading progress bar
- Filter bar on the sessions table
- Mobile-responsive, print-friendly
- ARIA focus rings and prefers-reduced-motion support

Stdlib + `markdown` (required). No optional deps — highlight.js loads from CDN.
Usage:
    python3 -m llmwiki build [--synthesize] [--out <dir>]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import markdown
from markdown.preprocessors import Preprocessor

from llmwiki import REPO_ROOT
from llmwiki.changelog_timeline import (
    extract_price_points,
    find_recently_updated,
    parse_changelog,
    render_changelog_timeline,
    render_price_sparkline,
    render_recent_activity,
    render_recently_updated,
)
from llmwiki.log_reader import recent_events as _recent_log_events
from llmwiki.compare import (
    discover_user_overrides,
    generate_pairs,
    pair_slug,
    render_comparison_body,
    render_comparisons_index,
)
from llmwiki.context_md import is_context_file
from llmwiki.freshness import freshness_badge, load_freshness_config
from llmwiki.models_page import (
    discover_model_entities,
    discover_model_entities_with_meta,
    render_model_info_card,
    render_models_index,
)
from llmwiki.project_topics import (
    get_project_topics,
    load_project_profile,
    render_topic_chips,
)
from llmwiki.viz_heatmap import collect_session_counts, render_heatmap
from llmwiki.viz_tokens import (
    render_project_token_card,
    render_session_token_card,
    render_site_token_stats,
)
from llmwiki.viz_tools import (
    render_project_tool_chart,
    render_session_tool_chart,
)

# ─── paths ─────────────────────────────────────────────────────────────────

RAW_DIR = REPO_ROOT / "raw"
RAW_SESSIONS = RAW_DIR / "sessions"
DEFAULT_OUT_DIR = REPO_ROOT / "site"
# v0.7+: optional per-project metadata (topics, description, homepage).
# Users drop a `wiki/projects/<slug>.md` file with frontmatter.
PROJECTS_META_DIR = REPO_ROOT / "wiki" / "projects"


# ─── frontmatter ───────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    meta: dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            meta[k.strip()] = (
                [x.strip() for x in inner.split(",") if x.strip()] if inner else []
            )
        else:
            meta[k.strip()] = v
    return meta, body


# ─── discovery ─────────────────────────────────────────────────────────────

def discover_sources(root: Path) -> list[tuple[Path, dict[str, Any], str]]:
    out: list[tuple[Path, dict[str, Any], str]] = []
    if not root.exists():
        return out
    for p in sorted(root.rglob("*.md")):
        # v0.5 (#60): `_context.md` files are folder metadata for LLM
        # navigation, not pages. Skip them so they never appear in the
        # session index, search index, or AI-consumable exports.
        if is_context_file(p):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        out.append((p, meta, body))
    return out


def group_by_project(
    sources: list[tuple[Path, dict[str, Any], str]],
) -> dict[str, list[tuple[Path, dict[str, Any], str]]]:
    g: dict[str, list[tuple[Path, dict[str, Any], str]]] = defaultdict(list)
    for p, meta, body in sources:
        project = str(meta.get("project") or p.parent.name)
        g[project].append((p, meta, body))
    for k in g:
        g[k].sort(key=lambda t: str(t[1].get("started", t[0].name)))
    return g


# ─── markdown normaliser + renderer ───────────────────────────────────────

_H1_LINE_RE = re.compile(r"^#\s+.*\n", re.MULTILINE)


def strip_leading_h1(body: str) -> str:
    m = _H1_LINE_RE.search(body)
    if m and m.start() < 200:
        body = body[: m.start()] + body[m.end() :]
        body = body.lstrip("\n")
    return body


def normalize_markdown(body: str) -> str:
    """Fix common markdown glitches from the converter:
    1. Insert blank line before lists that follow a bold header.
    2. Outdent fenced code blocks that are 2-space-indented under a list item.
    """
    body = re.sub(
        r"(\*\*(?:Tools used|Tool results):\*\*)\n(?!\n)", r"\1\n\n", body,
    )
    lines = body.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "```" and line.startswith("  "):
            if out and out[-1].strip():
                out.append("")
            out.append("```")
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                bl = lines[i]
                if bl.startswith("  "):
                    bl = bl[2:]
                out.append(bl)
                i += 1
            if i < len(lines):
                out.append("```")
                i += 1
                if i < len(lines) and lines[i].strip():
                    out.append("")
        else:
            out.append(line)
            i += 1
    return "\n".join(out)


# v0.5 (#74): Session content frequently mentions HTML-ish strings in prose —
# e.g. an assistant describing how a hidden `<textarea class="md-source">` works.
# The default Python markdown library passes raw HTML tags through unchanged,
# which means a session that mentions `<textarea>` outside of backticks leaks
# an unclosed textarea into the DOM, swallowing every following element
# (including the <script> tag that boots highlight.js). The v0.5 hljs swap
# made this pre-existing bug catastrophic — before, Pygments rendered code
# server-side so the broken tail didn't visibly matter; now, a single
# unescaped tag breaks the whole page's syntax highlighting.
#
# The preprocessor below escapes anything that *looks* like an HTML tag start
# (`<tagname` or `</tagname`) outside of inline backticks. Fenced code blocks
# are already extracted into placeholders by `fenced_code` (priority 25) before
# this runs (priority 22). Priority 22 also ensures we run *before*
# `html_block` (priority 20) so raw HTML blocks never get a chance to be
# preserved as-is. Bare `<` / `<space>` (e.g. `x < 10`) are left alone —
# markdown's own escaper handles those. HTML comments (`<!-- ... -->`) are
# preserved because the regex only matches `<[letter]`, not `<!`, and
# build.py emits an `<!-- llmwiki:metadata -->` comment that AI agents parse.
_TAG_START_RE = re.compile(r"<(/?[A-Za-z][A-Za-z0-9:_-]*)")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


class _EscapeRawHtmlPreprocessor(Preprocessor):
    """Escape HTML tag-start patterns outside code spans so raw `<textarea>`
    etc. in session prose can never leak into the DOM as live elements.
    See the comment above `md_to_html` for the full rationale."""

    def run(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        for line in lines:
            parts: list[tuple[str, str]] = []
            last = 0
            for m in _INLINE_CODE_RE.finditer(line):
                parts.append(("text", line[last : m.start()]))
                parts.append(("code", m.group(0)))
                last = m.end()
            parts.append(("text", line[last:]))
            rebuilt: list[str] = []
            for kind, part in parts:
                if kind == "text":
                    rebuilt.append(_TAG_START_RE.sub(r"&lt;\1", part))
                else:
                    rebuilt.append(part)
            out.append("".join(rebuilt))
        return out


def md_to_html(body: str) -> str:
    body = normalize_markdown(body)
    # v0.5: highlight.js replaces server-side Pygments/codehilite. The
    # fenced_code extension emits `<pre><code class="language-xxx">` and
    # highlight.js (loaded via CDN in page_head) picks it up client-side.
    # Benefits: lighter builds, no optional dep, consistent look across pages,
    # and auto-detection for untagged blocks.
    extensions = ["fenced_code", "tables", "toc", "sane_lists"]
    ext_configs: dict[str, dict[str, Any]] = {
        "toc": {"permalink": True, "toc_depth": "2-3"},
    }
    md = markdown.Markdown(extensions=extensions, extension_configs=ext_configs)
    # v0.5 (#74): escape raw HTML tags in prose so session content mentioning
    # `<textarea>` etc. can't break the page. Runs after fenced_code (25) and
    # before html_block (20), so fenced code is preserved verbatim (through
    # placeholders), inline code via backticks is preserved by this
    # preprocessor's own backtick-skipping, and everything else is safe.
    md.preprocessors.register(
        _EscapeRawHtmlPreprocessor(md), "escape_raw_html_tags", 22
    )
    return md.convert(body)


def md_to_plain_text(body: str) -> str:
    """Strip markdown to plain text for the search index."""
    body = normalize_markdown(strip_leading_h1(body))
    # Remove code blocks (they're noisy in search)
    body = re.sub(r"```.*?```", " ", body, flags=re.DOTALL)
    # Inline code
    body = re.sub(r"`([^`]*)`", r"\1", body)
    # Links: [text](url) → text
    body = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", body)
    # Wikilinks: [[name]] → name
    body = re.sub(r"\[\[([^\]]*)\]\]", r"\1", body)
    # Headings: strip leading #
    body = re.sub(r"^#+\s*", "", body, flags=re.MULTILINE)
    # Bold/italic marks
    body = re.sub(r"\*\*([^*]*)\*\*", r"\1", body)
    body = re.sub(r"\*([^*]*)\*", r"\1", body)
    # HTML comments
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    # Collapse whitespace
    body = re.sub(r"\s+", " ", body).strip()
    return body


# ─── helpers for frontmatter consumers ─────────────────────────────────────

def get_tools_list(meta: dict[str, Any]) -> list[str]:
    tools = meta.get("tools_used", [])
    if isinstance(tools, str):
        return [t.strip() for t in tools.strip("[]").split(",") if t.strip()]
    return list(tools) if tools else []


def short_started(meta: dict[str, Any]) -> str:
    s = str(meta.get("started", ""))
    return s[:16].replace("T", " ")


# ─── freshness (content staleness) ────────────────────────────────────────
# Cached once per build so every page sees the same "now" and the same
# thresholds. Populated lazily by render_freshness().
_FRESHNESS_CONFIG: Optional[tuple[int, int]] = None
_BUILD_NOW: Optional[datetime] = None


def render_freshness(meta: dict[str, Any]) -> str:
    """Render a freshness badge for a page's frontmatter using cached config.

    Thresholds come from ``config.json`` (freshness.green_days /
    yellow_days) or the module defaults. Build-time "now" is cached the
    first call so the whole site renders with one consistent clock.
    """
    global _FRESHNESS_CONFIG, _BUILD_NOW
    if _FRESHNESS_CONFIG is None:
        _FRESHNESS_CONFIG = load_freshness_config()
    if _BUILD_NOW is None:
        _BUILD_NOW = datetime.now(timezone.utc).replace(tzinfo=None)
    green, yellow = _FRESHNESS_CONFIG
    return freshness_badge(meta, now=_BUILD_NOW, green_days=green, yellow_days=yellow)


# ─── html template helpers ─────────────────────────────────────────────────

# v0.5: highlight.js for client-side syntax highlighting. Two themes so the
# switcher can swap between light/dark without a network round-trip. Pinned
# to a major version for stability, served from jsdelivr.
HLJS_VERSION = "11.9.0"
HLJS_LIGHT_CSS = (
    f"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@{HLJS_VERSION}"
    "/build/styles/github.min.css"
)
HLJS_DARK_CSS = (
    f"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@{HLJS_VERSION}"
    "/build/styles/github-dark.min.css"
)
HLJS_SCRIPT = (
    f"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@{HLJS_VERSION}"
    "/build/highlight.min.js"
)


def _hljs_head_tags() -> str:
    """Return the `<link>` tags for highlight.js themes. The dark theme is
    loaded with ``disabled`` and the light theme is the default — the runtime
    swaps the ``disabled`` flag when the theme toggles, so code blocks stay in
    sync with the rest of the page."""
    return (
        f'  <link id="hljs-light" rel="stylesheet" href="{HLJS_LIGHT_CSS}">\n'
        f'  <link id="hljs-dark" rel="stylesheet" href="{HLJS_DARK_CSS}" disabled>\n'
    )


def page_head(title: str, description: str, css_prefix: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
{_hljs_head_tags()}  <link rel="stylesheet" href="{css_prefix}style.css">
</head>
<body>
<a href="#main-content" class="skip-link">Skip to content</a>
<div class="progress-bar" id="progress-bar"></div>
"""


def page_head_article(
    title: str,
    description: str,
    css_prefix: str = "",
    canonical: str = "",
    date: str = "",
    metadata_comment: str = "",
) -> str:
    """v0.4: Extended page head for session (Article) pages with schema.org
    microdata, canonical link, and an AI-readable metadata HTML comment."""
    canonical_tag = ""
    if canonical:
        canonical_tag = f'  <link rel="canonical" href="{html.escape(canonical)}">\n'
    og_tags = f"""  <meta property="og:type" content="article">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(description)}">
"""
    if date:
        og_tags += f'  <meta property="article:published_time" content="{html.escape(date)}">\n'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
{canonical_tag}{og_tags}  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
{_hljs_head_tags()}  <link rel="stylesheet" href="{css_prefix}style.css">
</head>
<body>
{metadata_comment}<a href="#main-content" class="skip-link">Skip to content</a>
<div class="progress-bar" id="progress-bar"></div>
"""


def _build_metadata_comment(
    meta: dict[str, Any],
    slug: str,
    project_slug: str,
    reading_min: int,
    html_stem: str = "",
) -> str:
    """An HTML comment at the top of every session page that AI agents can
    parse without needing to fetch the separate .json sibling."""
    fields = [
        f"slug: {slug}",
        f"project: {project_slug}",
    ]
    for key in ("date", "started", "ended", "model", "gitBranch", "permissionMode", "user_messages", "tool_calls"):
        val = meta.get(key)
        if val is not None:
            fields.append(f"{key}: {val}")
    tools = get_tools_list(meta)
    if tools:
        fields.append(f"tools_used: [{', '.join(tools)}]")
    fields.append(f"reading_min: {reading_min}")
    sibling_stem = html_stem or slug
    fields.append(f"txt_sibling: {sibling_stem}.txt")
    fields.append(f"json_sibling: {sibling_stem}.json")
    body = "\n".join(fields)
    return f"<!-- llmwiki:metadata\n{body}\n-->\n"


def nav_bar(active: str, link_prefix: str = "") -> str:
    def link(href: str, label: str, key: str) -> str:
        cls = ' class="active"' if key == active else ""
        return f'<a href="{link_prefix}{href}"{cls}>{label}</a>'

    return f"""<header class="nav">
  <div class="nav-inner">
    <a href="{link_prefix}index.html" class="nav-brand">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
      LLM Wiki
    </a>
    <nav class="nav-links">
      {link("index.html", "Home", "home")}
      {link("projects/index.html", "Projects", "projects")}
      {link("sessions/index.html", "Sessions", "sessions")}
      {link("models/index.html", "Models", "models")}
      {link("vs/index.html", "Compare", "vs")}
      {link("graph.html", "Graph", "graph")}
      {link("docs/index.html", "Docs", "docs")}
      {link("prototypes/index.html", "Prototypes", "prototypes")}
      {link("changelog.html", "Changelog", "changelog")}
      <button class="nav-search-btn" id="open-palette" aria-label="Open command palette">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <span>Search</span>
        <kbd>⌘K</kbd>
      </button>
      <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark mode">
        <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
      </button>
    </nav>
  </div>
</header>
"""


def breadcrumbs_bar(crumbs: list[tuple[str, str]], link_prefix: str = "") -> str:
    if not crumbs:
        return ""
    parts = []
    for i, (label, href) in enumerate(crumbs):
        if href:
            parts.append(f'<a href="{link_prefix}{html.escape(href)}">{html.escape(label)}</a>')
        else:
            parts.append(f'<span aria-current="page">{html.escape(label)}</span>')
    sep = ' <span class="crumb-sep">›</span> '
    return f'<nav class="breadcrumbs" aria-label="Breadcrumb">{sep.join(parts)}</nav>'


def hero(title: str, subtitle: str, size: str = "", subtitle_is_html: bool = False) -> str:
    cls = f"hero {size}".strip()
    sub = subtitle if subtitle_is_html else html.escape(subtitle)
    return f"""<main id="main-content">
<section class="{cls}">
  <div class="container">
    <h1>{html.escape(title)}</h1>
    <p class="hero-sub">{sub}</p>
  </div>
</section>
"""


def page_foot(js_prefix: str = "") -> str:
    return f"""<footer class="footer">
  <div class="container">
    <p class="muted">llmwiki · <a href="{js_prefix}index.html">home</a> · press <kbd>?</kbd> for shortcuts</p>
  </div>
</footer>
<nav class="mobile-bottom-nav" aria-label="Mobile navigation">
  <a href="{js_prefix}index.html" class="mbn-link" data-page="home">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
    <span>Home</span>
  </a>
  <a href="{js_prefix}projects/index.html" class="mbn-link" data-page="projects">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
    <span>Projects</span>
  </a>
  <a href="{js_prefix}sessions/index.html" class="mbn-link" data-page="sessions">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
    <span>Sessions</span>
  </a>
  <button type="button" class="mbn-link" id="mbn-search" aria-label="Search">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <span>Search</span>
  </button>
  <button type="button" class="mbn-link" id="mbn-theme" aria-label="Toggle theme">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    <span>Theme</span>
  </button>
</nav>
<div id="palette" class="palette" aria-hidden="true">
  <div class="palette-backdrop" id="palette-backdrop"></div>
  <div class="palette-modal" role="dialog" aria-modal="true" aria-label="Command palette">
    <div class="palette-header">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input type="text" id="palette-input" placeholder="Search… or type:session project:llm-wiki date:>2026-03 sort:date" autocomplete="off" spellcheck="false">
      <kbd>ESC</kbd>
    </div>
    <ul class="palette-results" id="palette-results"></ul>
    <div class="palette-footer muted">
      <span><kbd>↑↓</kbd> navigate</span>
      <span><kbd>↵</kbd> open</span>
      <span><kbd>ESC</kbd> close</span>
    </div>
  </div>
</div>
<div id="help-dialog" class="help-dialog" aria-hidden="true">
  <div class="palette-backdrop" id="help-backdrop"></div>
  <div class="help-modal">
    <h2>Keyboard shortcuts</h2>
    <table>
      <tr><td><kbd>⌘K</kbd> / <kbd>Ctrl+K</kbd></td><td>Open command palette</td></tr>
      <tr><td><kbd>/</kbd></td><td>Focus search</td></tr>
      <tr><td><kbd>g h</kbd></td><td>Go to home</td></tr>
      <tr><td><kbd>g p</kbd></td><td>Go to projects</td></tr>
      <tr><td><kbd>g s</kbd></td><td>Go to sessions</td></tr>
      <tr><td><kbd>j</kbd> / <kbd>k</kbd></td><td>Next / prev row (tables)</td></tr>
      <tr><td><kbd>?</kbd></td><td>Show this help</td></tr>
      <tr><td><kbd>Esc</kbd></td><td>Close dialogs</td></tr>
    </table>
    <h3>Structured queries</h3>
    <p class="muted" style="font-size: 0.82rem; margin: 4px 0 8px;">Mix key:value filters with free text in the palette:</p>
    <table>
      <tr><td><code>type:session</code></td><td>Only session pages</td></tr>
      <tr><td><code>project:llm-wiki</code></td><td>Filter by project name (substring)</td></tr>
      <tr><td><code>model:claude</code></td><td>Filter by model name (substring)</td></tr>
      <tr><td><code>date:&gt;2026-03-01</code></td><td>Sessions after a date</td></tr>
      <tr><td><code>date:&lt;2026-04-01</code></td><td>Sessions before a date</td></tr>
      <tr><td><code>tags:rust</code></td><td>Pages mentioning a tag/topic</td></tr>
      <tr><td><code>sort:date</code></td><td>Sort results by date (newest first)</td></tr>
    </table>
    <p class="muted" style="font-size: 0.82rem; margin-top: 6px;">Example: <code>type:session project:llm-wiki date:&gt;2026-04 sort:date</code></p>
    <button class="btn" id="help-close">Close</button>
  </div>
</div>
<script src="{js_prefix}search-index.json" type="application/json" id="search-index-hint"></script>
<script>window.LLMWIKI_INDEX_URL = "{js_prefix}search-index.json";</script>
<script src="{HLJS_SCRIPT}" defer></script>
<script>
  // v0.5: Run highlight.js once the CDN script lands. Defer keeps it out of
  // the critical path; the DOMContentLoaded fallback covers the case where
  // hljs arrives before/after DOM ready depending on cache state.
  function __llmwikiHljsInit() {{
    if (window.hljs) {{ window.hljs.highlightAll(); }}
    else {{ window.addEventListener('load', function() {{ if (window.hljs) window.hljs.highlightAll(); }}); }}
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', __llmwikiHljsInit);
  }} else {{
    __llmwikiHljsInit();
  }}
</script>
<script src="{js_prefix}script.js"></script>
</body>
</html>
"""


# ─── page renderers ────────────────────────────────────────────────────────

def calc_reading_time(body: str, wpm: int = 225) -> int:
    """Estimate reading time in minutes from a markdown body."""
    words = len(re.findall(r"\w+", body))
    return max(1, round(words / wpm))


def render_session(
    path: Path,
    meta: dict[str, Any],
    body: str,
    out_dir: Path,
    project_slug: str,
) -> Path:
    slug = meta.get("slug", path.stem)
    date = meta.get("date", "")
    title_raw = meta.get("title", f"Session: {slug}")

    body = strip_leading_h1(body)
    body_html = md_to_html(body)
    raw_md_for_copy = html.escape(body)
    reading_min = calc_reading_time(body)

    bits: list[str] = []
    if meta.get("project"):
        bits.append(
            f'<a href="../../projects/{html.escape(str(meta["project"]))}.html">{html.escape(str(meta["project"]))}</a>'
        )
    # Agent badge — shows Claude / Codex / Copilot / Cursor / Gemini
    bits.append(render_agent_badge(meta))
    if meta.get("gitBranch"):
        bits.append(f'branch <code>{html.escape(str(meta["gitBranch"]))}</code>')
    if meta.get("model"):
        bits.append(f'<code>{html.escape(str(meta["model"]))}</code>')
    if meta.get("started"):
        bits.append(f'<span class="muted">{html.escape(short_started(meta))}</span>')
    if meta.get("user_messages"):
        bits.append(f'{html.escape(str(meta["user_messages"]))} msgs')
    if meta.get("tool_calls"):
        bits.append(f'{html.escape(str(meta["tool_calls"]))} tools')
    bits.append(f'<span class="muted">{reading_min} min read</span>')
    bits.append(render_freshness(meta))
    meta_strip = " · ".join(bits) if bits else ""

    tools_list = get_tools_list(meta)
    tools_preview = ""
    if tools_list:
        preview = ", ".join(tools_list[:6])
        if len(tools_list) > 6:
            preview += f", +{len(tools_list) - 6} more"
        tools_preview = f'<div class="meta-tools muted">tools: {html.escape(preview)}</div>'

    # v0.8 (#65): horizontal bar chart of tool calls in this session.
    # Uses the `tool_counts` JSON dict from frontmatter (#63). Empty
    # sessions (no recorded calls) render nothing.
    tool_chart_svg = render_session_tool_chart(meta)
    tool_chart_block = ""
    if tool_chart_svg:
        tool_chart_block = (
            '<div class="tool-chart-card">'
            '<div class="tool-chart-label muted">Tool calls</div>'
            f'{tool_chart_svg}'
            '</div>'
        )

    # v0.8 (#66): session token-usage card. Input / cache_creation /
    # cache_read / output plus a cache-hit-ratio tier badge. Sessions
    # missing token_totals (older converter output) render nothing.
    token_card_block = render_session_token_card(meta)

    # IMPORTANT: The HTML file is named `<path.stem>.html` (e.g. date-slug),
    # NOT `<slug>.html`. The siblings + canonical must use path.stem.
    html_stem = path.stem
    raw_md_path = f"../../sources/{project_slug}/{path.name}"
    actions_html = f"""<div class="session-actions">
  <button class="btn btn-primary" onclick="copyMarkdown(this)">Copy as markdown</button>
  <a class="btn" href="../../projects/{html.escape(project_slug)}.html">← {html.escape(project_slug)}</a>
  <a class="btn" href="{html.escape(raw_md_path)}" download>Download .md</a>
  <a class="btn" href="{html.escape(html_stem + '.txt')}" title="plain-text sibling for AI agents">.txt</a>
  <a class="btn" href="{html.escape(html_stem + '.json')}" title="structured JSON sibling for AI agents">.json</a>
  <textarea class="md-source" hidden>{raw_md_for_copy}</textarea>
</div>"""

    crumbs = [
        ("Home", "index.html"),
        ("Projects", "projects/index.html"),
        (project_slug, f"projects/{project_slug}.html"),
        (str(slug), ""),
    ]
    breadcrumbs = breadcrumbs_bar(crumbs, link_prefix="../../")

    # v0.4: machine-readable metadata appendix (HTML comment that AI agents
    # scraping HTML can parse without fetching the .json sibling).
    metadata_comment = _build_metadata_comment(meta, slug, project_slug, reading_min, html_stem=html_stem)

    # v0.4: page_head with schema.org article microdata + canonical link.
    # Canonical is relative to the current page (same dir) so the link checker
    # resolves it correctly whether served from a subdomain root or any path.
    page = (
        page_head_article(
            title=f"{title_raw} — LLM Wiki",
            description=f"Session transcript from {meta.get('project', '')} on {date}",
            css_prefix="../../",
            canonical=f"{html_stem}.html",
            date=str(meta.get("started") or date),
            metadata_comment=metadata_comment,
        )
        + nav_bar("sessions", link_prefix="../../")
        + hero(str(title_raw), meta_strip, size="hero-sm", subtitle_is_html=True)
        + f'<section class="section">\n  <div class="container">\n{breadcrumbs}\n{tools_preview}\n{actions_html}\n{tool_chart_block}\n{token_card_block}\n    <article class="content" itemscope itemtype="https://schema.org/Article">\n'
        + f'<meta itemprop="headline" content="{html.escape(str(title_raw))}">\n'
        + f'<meta itemprop="datePublished" content="{html.escape(str(meta.get("started") or date))}">\n'
        + f'<meta itemprop="inLanguage" content="en">\n'
        + body_html
        + '\n    </article>\n  </div>\n</section>\n</main>\n'
        + page_foot(js_prefix="../../")
    )

    out_path = out_dir / "sessions" / project_slug / f"{path.stem}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_project_page(
    project_slug: str,
    sessions: list[tuple[Path, dict[str, Any], str]],
    out_dir: Path,
) -> Path:
    main_sessions = [s for s in sessions if "subagent" not in s[0].name]
    subagent_sessions = [s for s in sessions if s not in main_sessions]

    def card(p: Path, meta: dict[str, Any]) -> str:
        slug = meta.get("slug", p.stem)
        date = meta.get("date", "")
        model = meta.get("model", "")
        umsgs = meta.get("user_messages", "")
        tcalls = meta.get("tool_calls", "")
        href = f"../sessions/{project_slug}/{p.stem}.html"
        badge = render_freshness(meta)
        return f"""  <a class="card" href="{href}">
    <div class="card-title">{html.escape(str(slug))}</div>
    <div class="card-meta">{html.escape(str(date))} · {html.escape(str(model))}</div>
    <div class="card-stats muted">{html.escape(str(umsgs))} messages · {html.escape(str(tcalls))} tool calls</div>
    <div class="card-badge">{badge}</div>
  </a>"""

    cards_main = "\n".join(card(p, m) for p, m, _ in main_sessions)
    cards_sub = "\n".join(card(p, m) for p, m, _ in subagent_sessions)

    sub_section = ""
    if subagent_sessions:
        sub_section = (
            '<details class="sub-section"><summary>Sub-agent runs ('
            + str(len(subagent_sessions))
            + ")</summary>\n<div class=\"card-grid\">\n"
            + cards_sub
            + "\n</div>\n</details>\n"
        )

    crumbs = breadcrumbs_bar(
        [("Home", "index.html"), ("Projects", "projects/index.html"), (project_slug, "")],
        link_prefix="../",
    )

    # v0.8 (#64, #72): per-project 365-day heatmap — same window as the
    # aggregate on the home page, but filtered to just this project's
    # sessions. Sparse projects (only a handful of sessions) still render
    # the full grid with the rest as level-0 cells, so the shape matches.
    proj_entries = [m for _, m, _ in sessions]
    proj_counts = collect_session_counts(proj_entries, project_slug=project_slug)
    proj_heatmap = render_heatmap(proj_counts, title_prefix=f"{project_slug} activity")
    heatmap_block = f"""<section class="section heatmap-section">
  <div class="container">
    <div class="activity-heatmap">
      <div class="heatmap-label muted">Activity · last 365 days · {html.escape(project_slug)}</div>
      {proj_heatmap}
    </div>
  </div>
</section>"""

    # v0.8 (#65): aggregate tool-call bar chart across all sessions in
    # this project. Projects with no recorded tool calls render nothing.
    proj_tool_chart = render_project_tool_chart(proj_entries, project_slug)
    tool_chart_block = ""
    if proj_tool_chart:
        tool_chart_block = f"""<section class="section tool-chart-section">
  <div class="container">
    <div class="tool-chart-card">
      <div class="tool-chart-label muted">Tool calls · {html.escape(project_slug)} aggregate</div>
      {proj_tool_chart}
    </div>
  </div>
</section>"""

    # v0.8 (#66): project token timeline card (log-scale area chart of
    # total tokens per session date + aggregate cache hit ratio in the
    # header). Empty for projects without any token data.
    proj_token_card_html = render_project_token_card(proj_entries, project_slug)
    token_timeline_block = ""
    if proj_token_card_html:
        token_timeline_block = f"""<section class="section token-timeline-section">
  <div class="container">
    {proj_token_card_html}
  </div>
</section>"""

    # Project topics strip — renders below the hero, above the heatmap.
    # Explicit profile via wiki/projects/<slug>.md wins over the
    # session-tag fallback. Projects with no topics render an empty
    # strip (no chip row at all).
    proj_profile = load_project_profile(PROJECTS_META_DIR, project_slug)
    proj_topics = get_project_topics(PROJECTS_META_DIR, project_slug, proj_entries)
    topics_html = render_topic_chips(
        proj_topics, max_visible=12, classname="project-topics project-hero-topics"
    )
    description_html = ""
    if proj_profile and proj_profile.get("description"):
        description_html = (
            f'<p class="project-description muted">'
            f'{html.escape(proj_profile["description"])}</p>'
        )
    homepage_html = ""
    if proj_profile and proj_profile.get("homepage"):
        hp = proj_profile["homepage"]
        homepage_html = (
            f'<a class="project-homepage" href="{html.escape(hp)}" '
            f'rel="noopener">{html.escape(hp)} ↗</a>'
        )
    topics_strip = ""
    if topics_html or description_html or homepage_html:
        topics_strip = (
            '<section class="section project-topics-section">\n'
            '  <div class="container">\n'
            f'    {description_html}\n'
            f'    {topics_html}\n'
            f'    {homepage_html}\n'
            '  </div>\n'
            '</section>\n'
        )

    body = f"""{topics_strip}
{heatmap_block}
{tool_chart_block}
{token_timeline_block}
<section class="section">
  <div class="container">
    {crumbs}
    <h2>Main sessions ({len(main_sessions)})</h2>
    <div class="card-grid">
{cards_main}
    </div>
    {sub_section}
  </div>
</section>
</main>
"""

    page = (
        page_head(
            f"{project_slug} — LLM Wiki",
            f"{len(sessions)} Claude Code sessions from {project_slug}",
            css_prefix="../",
        )
        + nav_bar("projects", link_prefix="../")
        + hero(
            project_slug,
            f"{len(main_sessions)} main sessions · {len(subagent_sessions)} sub-agent runs",
        )
        + body
        + page_foot(js_prefix="../")
    )

    out_path = out_dir / "projects" / f"{project_slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_projects_index(
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    out_dir: Path,
) -> Path:
    cards = []
    for project, sessions in sorted(groups.items(), key=lambda x: -len(x[1])):
        main_count = sum(1 for p, _, _ in sessions if "subagent" not in p.name)
        sub_count = len(sessions) - main_count
        # Freshness reflects the newest session in the project.
        newest_meta = max(
            (m for _, m, _ in sessions),
            key=lambda m: str(m.get("ended") or m.get("started") or m.get("date") or ""),
            default={},
        )
        badge = render_freshness(newest_meta)
        cards.append(
            f"""  <a class="card" href="{html.escape(project)}.html">
    <div class="card-title">{html.escape(project)}</div>
    <div class="card-meta">{main_count} main · {sub_count} sub-agent</div>
    <div class="card-badge">{badge}</div>
  </a>"""
        )

    crumbs = breadcrumbs_bar(
        [("Home", "index.html"), ("Projects", "")], link_prefix="../"
    )

    body = f"""<section class="section">
  <div class="container">
    {crumbs}
    <div class="card-grid">
{chr(10).join(cards)}
    </div>
  </div>
</section>
</main>
"""

    page = (
        page_head("Projects — LLM Wiki", "All projects with Claude Code session history", css_prefix="../")
        + nav_bar("projects", link_prefix="../")
        + hero("Projects", f"{len(groups)} projects")
        + body
        + page_foot(js_prefix="../")
    )

    out_path = out_dir / "projects" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_sessions_index(
    sources: list[tuple[Path, dict[str, Any], str]],
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    out_dir: Path,
) -> Path:
    rows = []

    def key(t: tuple[Path, dict[str, Any], str]) -> str:
        return str(t[1].get("started", "")) or str(t[0].name)

    for p, meta, _ in sorted(sources, key=key, reverse=True):
        project = meta.get("project", p.parent.name)
        slug = meta.get("slug", p.stem)
        date = meta.get("date", "")
        model = meta.get("model", "")
        umsgs = meta.get("user_messages", "")
        tcalls = meta.get("tool_calls", "")
        href = f"{project}/{p.stem}.html"
        rows.append(
            f"""        <tr data-project="{html.escape(str(project))}" data-model="{html.escape(str(model))}" data-date="{html.escape(str(date))}" data-slug="{html.escape(str(slug))}">
          <td><a href="{html.escape(str(href))}">{html.escape(str(slug))}</a></td>
          <td>{render_agent_badge(meta)}</td>
          <td><a href="../projects/{html.escape(str(project))}.html">{html.escape(str(project))}</a></td>
          <td>{html.escape(str(date))}</td>
          <td><code>{html.escape(str(model))}</code></td>
          <td class="num">{html.escape(str(umsgs))}</td>
          <td class="num">{html.escape(str(tcalls))}</td>
        </tr>"""
        )

    project_options = "\n".join(
        f'        <option value="{html.escape(p)}">{html.escape(p)}</option>'
        for p in sorted(groups.keys())
    )

    models = sorted(
        {str(m.get("model", "")) for _, m, _ in sources if m.get("model")}
    )
    model_options = "\n".join(
        f'        <option value="{html.escape(m)}">{html.escape(m)}</option>'
        for m in models
    )

    crumbs = breadcrumbs_bar(
        [("Home", "index.html"), ("Sessions", "")], link_prefix="../"
    )

    body = f"""<section class="section">
  <div class="container">
    {crumbs}
    <div class="filter-bar">
      <label>Project
        <select id="filter-project">
          <option value="">All projects</option>
{project_options}
        </select>
      </label>
      <label>Model
        <select id="filter-model">
          <option value="">All models</option>
{model_options}
        </select>
      </label>
      <label>From
        <input type="date" id="filter-date-from">
      </label>
      <label>To
        <input type="date" id="filter-date-to">
      </label>
      <input type="text" id="filter-text" placeholder="Filter by slug…">
      <button class="btn" id="filter-clear">Clear</button>
      <span class="filter-count muted" id="filter-count"></span>
    </div>
    <div class="table-wrap">
    <table class="sessions-table">
      <thead>
        <tr><th>Session</th><th>Agent</th><th>Project</th><th>Date</th><th>Model</th><th>Msgs</th><th>Tools</th></tr>
      </thead>
      <tbody id="sessions-tbody">
{chr(10).join(rows)}
      </tbody>
    </table>
    </div>
  </div>
</section>
</main>
"""

    page = (
        page_head("Sessions — LLM Wiki", "All Claude Code sessions, newest first", css_prefix="../")
        + nav_bar("sessions", link_prefix="../")
        + hero("All sessions", f"{len(sources)} sessions total")
        + body
        + page_foot(js_prefix="../")
    )

    out_path = out_dir / "sessions" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_index(
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    all_sources: list[tuple[Path, dict[str, Any], str]],
    out_dir: Path,
    synthesis: Optional[str] = None,
) -> Path:
    total = len(all_sources)
    mains = sum(1 for p, _, _ in all_sources if "subagent" not in p.name)
    subs = total - mains

    synth_block = ""
    if synthesis:
        synth_block = f"""<section class="section">
  <div class="container">
    <div class="synthesis">
      <h2>Overview</h2>
      {md_to_html(synthesis)}
    </div>
  </div>
</section>"""

    # v0.8 (#64, #72): aggregate 365-day GitHub-style heatmap. Counts all
    # main sessions across all projects. Rendered as a pure-SVG block just
    # above the projects grid so the landing page gives a glanceable
    # "last year of activity" view.
    heatmap_entries = [m for _, m, _ in all_sources]
    heatmap_counts = collect_session_counts(heatmap_entries)
    heatmap_svg = render_heatmap(heatmap_counts, title_prefix="Activity")
    heatmap_block = f"""<section class="section heatmap-section">
  <div class="container">
    <div class="activity-heatmap">
      <div class="heatmap-label muted">Activity · last 365 days</div>
      {heatmap_svg}
    </div>
  </div>
</section>"""

    # v0.8 (#66): site-wide token summary stats — four cards showing
    # total tokens processed, average per session, best cache hit project,
    # heaviest project. Empty if no session has token_totals data.
    metas_by_project: dict[str, list[dict[str, Any]]] = {}
    for project, sessions in groups.items():
        metas_by_project[project] = [m for _, m, _ in sessions]
    token_stats_block = render_site_token_stats(metas_by_project, link_prefix="")

    # v0.7 (#56): "Recently updated" list of model entities whose
    # changelog has an entry in the last 30 days. Empty if no model
    # pages exist or none have a recent changelog entry.
    from llmwiki.models_page import discover_model_entities_with_meta as _dm
    model_entries_meta = _dm(REPO_ROOT / "wiki" / "entities")
    recent_updates = find_recently_updated(
        [(p.stem, m) for p, m, _, _, _ in model_entries_meta]
    )
    recent_block_inner = render_recently_updated(
        recent_updates, link_prefix="models/"
    )
    # G-18 (#304): when no model-changelog activity exists, fall back
    # to the last 10 entries from wiki/log.md so the card isn't empty
    # on corpora without model pages (the overwhelmingly common case).
    if not recent_block_inner:
        log_events = _recent_log_events(
            REPO_ROOT / "wiki" / "log.md", limit=10
        )
        recent_block_inner = render_recent_activity(log_events)
    recent_block = (
        f'<section class="section recently-updated-section">\n'
        f'  <div class="container">\n'
        f'    {recent_block_inner}\n'
        f'  </div>\n'
        f'</section>\n'
    ) if recent_block_inner else ""

    cards = []
    for project, sessions in sorted(groups.items(), key=lambda x: -len(x[1])):
        main_count = sum(1 for p, _, _ in sessions if "subagent" not in p.name)
        # Project topics — explicit profile in wiki/projects/<slug>.md
        # takes precedence, falls back to aggregated session tags with
        # noise filtered out. Rendered as chips below the card meta.
        proj_metas = [m for _, m, _ in sessions]
        topics = get_project_topics(PROJECTS_META_DIR, project, proj_metas)
        topics_html = render_topic_chips(topics, max_visible=4,
                                         classname="project-topics card-topics")
        cards.append(
            f"""  <a class="card card-project" href="projects/{html.escape(project)}.html">
    <div class="card-title">{html.escape(project)}</div>
    <div class="card-meta">{main_count} main · {len(sessions) - main_count} sub-agent</div>
    {topics_html}
  </a>"""
        )

    body = f"""{heatmap_block}
{token_stats_block}
{recent_block}
<section class="section">
  <div class="container">
    <h2>Projects</h2>
    <div class="card-grid">
{chr(10).join(cards)}
    </div>
  </div>
</section>
</main>
"""

    page = (
        page_head("LLM Wiki", "Karpathy-style knowledge base from Claude Code sessions", css_prefix="")
        + nav_bar("home", link_prefix="")
        + hero(
            "LLM Wiki",
            f"{mains} main sessions · {subs} sub-agent runs · {len(groups)} projects",
        )
        + synth_block
        + body
        + page_foot(js_prefix="")
    )

    out_path = out_dir / "index.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


# ─── changelog page ────────────────────────────────────────────────────────

def render_changelog(out_dir: Path) -> Optional[Path]:
    """Render ``CHANGELOG.md`` (repo root) to ``site/changelog.html``.

    Returns None if CHANGELOG.md is missing. Shown as its own top-level page
    so visitors can see what's new / what shipped without clicking through to
    GitHub. Keep-a-changelog headings become an in-page TOC via the existing
    `toc` markdown extension.
    """
    src = REPO_ROOT / "CHANGELOG.md"
    if not src.exists():
        return None
    raw = src.read_text(encoding="utf-8")

    # Pull the top H1 ("Changelog") and use it as the hero title; render
    # everything else as the body. Strip the leading H1 line to avoid a
    # duplicate title.
    body_md = raw
    lines = raw.splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        body_md = "\n".join(lines[1:]).lstrip("\n")

    content_html = md_to_html(body_md)

    body = f"""<section class="section changelog-body">
  <div class="container narrow">
    <article class="article">
      {content_html}
    </article>
  </div>
</section>
</main>
"""

    page = (
        page_head(
            "Changelog — LLM Wiki",
            "Release notes for llmwiki — features, fixes, and version history.",
            css_prefix="",
        )
        + nav_bar("changelog", link_prefix="")
        + hero(
            "Changelog",
            "Every release, every fix. Keep-a-changelog format, semver.",
        )
        + body
        + page_foot(js_prefix="")
    )

    out_path = out_dir / "changelog.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


# ─── v0.7 (#55) models section ─────────────────────────────────────────────

def render_models_section(out_dir: Path) -> tuple[Optional[Path], int]:
    """Discover `wiki/entities/*.md` pages with `entity_kind: ai-model`,
    render one detail page per model + a sortable `/models/index.html`.

    Returns `(index_path_or_None, model_count)`. If there's no
    `wiki/entities/` directory OR no model pages there, we still write
    an empty-state index so the nav link doesn't 404.
    """
    entities_dir = REPO_ROOT / "wiki" / "entities"
    entries_with_meta = discover_model_entities_with_meta(entities_dir)
    # Backwards-compatible list without meta for render_models_index.
    entries = [
        (path, profile, warnings, body)
        for path, _meta, profile, warnings, body in entries_with_meta
    ]
    models_out = out_dir / "models"
    models_out.mkdir(parents=True, exist_ok=True)

    # Index page — always write it so the nav link resolves.
    index_body = render_models_index(entries)
    index_page = (
        page_head(
            "Models — LLM Wiki",
            "Directory of AI-model entities tracked by the wiki with pricing, "
            "context windows, and benchmark scores.",
            css_prefix="../",
        )
        + nav_bar("models", link_prefix="../")
        + hero("Models", f"{len(entries)} model entities tracked")
        + index_body
        + "</main>\n"
        + page_foot(js_prefix="../")
    )
    index_path = models_out / "index.html"
    index_path.write_text(index_page, encoding="utf-8")

    # Per-model detail page — info card + body markdown rendered normally.
    for path, meta, profile, warnings, body in entries_with_meta:
        slug = path.stem
        title = profile.get("title", slug)
        info_card = render_model_info_card(profile)

        # v0.7 (#56): changelog timeline + pricing sparkline below the
        # info card. The sparkline only shows if there are ≥2 dated
        # input-price changes in the changelog.
        changelog_entries, changelog_warnings = parse_changelog(meta)
        warnings = list(warnings) + changelog_warnings
        timeline_html = render_changelog_timeline(changelog_entries)
        timeline_block = ""
        if timeline_html:
            price_pts = extract_price_points(
                changelog_entries, field_suffix="pricing.input_per_1m"
            )
            sparkline = render_price_sparkline(price_pts)
            sparkline_block = (
                f'<div class="timeline-sparkline">'
                f'<span class="muted">Input pricing trend</span> {sparkline}'
                f'</div>'
                if sparkline else ""
            )
            timeline_block = (
                '<div class="timeline-card">'
                '<div class="timeline-card-title">Changelog</div>'
                + sparkline_block
                + timeline_html
                + '</div>'
            )

        body_html = md_to_html(body)
        warnings_html = ""
        if warnings:
            items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
            warnings_html = (
                '<details class="model-warnings"><summary>Schema warnings '
                f'({len(warnings)})</summary><ul>{items}</ul></details>'
            )
        page = (
            page_head(
                f"{title} — LLM Wiki",
                f"AI-model entity: {title}",
                css_prefix="../",
            )
            + nav_bar("models", link_prefix="../")
            + hero(title, profile.get("provider", ""))
            + f'<section class="section">\n  <div class="container narrow">\n'
            + info_card
            + timeline_block
            + warnings_html
            + f'    <article class="article content">\n      {body_html}\n    </article>\n'
            + '  </div>\n</section>\n</main>\n'
            + page_foot(js_prefix="../")
        )
        (models_out / f"{slug}.html").write_text(page, encoding="utf-8")

    return index_path, len(entries)


# ─── v0.7 (#58) auto-generated vs-comparison pages ────────────────────────

def render_vs_section(
    out_dir: Path,
    max_pairs: int = 500,
    min_shared_fields: int = 3,
) -> tuple[Optional[Path], int]:
    """Generate `/vs/<slug_a>-vs-<slug_b>.html` for every pair of
    comparable model entities + an index at `/vs/index.html`.

    Honors user overrides under `wiki/vs/<slug>.md` — a hand-written
    comparison replaces the auto-gen for that URL. Returns
    `(index_path, pair_count)`. Always writes the index so the nav
    link resolves even when no entities exist.
    """
    entities_dir = REPO_ROOT / "wiki" / "entities"
    overrides_dir = REPO_ROOT / "wiki" / "vs"
    entries = discover_model_entities(entities_dir)
    # Strip down to (path, profile) for compare.generate_pairs
    pair_entries = [(p, profile) for p, profile, _w, _b in entries]
    pairs = generate_pairs(
        pair_entries,
        min_shared_fields=min_shared_fields,
        max_pairs=max_pairs,
    )

    vs_out = out_dir / "vs"
    vs_out.mkdir(parents=True, exist_ok=True)

    # Index
    index_body = render_comparisons_index(pairs)
    index_page = (
        page_head(
            "Model comparisons — LLM Wiki",
            "Auto-generated side-by-side comparisons of AI-model entities.",
            css_prefix="../",
        )
        + nav_bar("vs", link_prefix="../")
        + hero("Model comparisons", f"{len(pairs)} auto-generated pairs")
        + index_body
        + "</main>\n"
        + page_foot(js_prefix="../")
    )
    index_path = vs_out / "index.html"
    index_path.write_text(index_page, encoding="utf-8")

    # User overrides replace the auto-gen for matching slugs
    overrides = discover_user_overrides(overrides_dir)

    for pair in pairs:
        slug = pair_slug(pair)
        if slug in overrides:
            # User override — render the raw body through md_to_html
            body_html = md_to_html(overrides[slug])
            article_body = (
                '<section class="section"><div class="container narrow">'
                f'<article class="article content">{body_html}</article>'
                '</div></section>'
            )
        else:
            # Auto-gen — three structured sections
            comparison_body = render_comparison_body(pair)
            article_body = (
                '<section class="section"><div class="container narrow">'
                f'{comparison_body}'
                '</div></section>'
            )

        title = f"{pair['title_a']} vs {pair['title_b']}"
        page = (
            page_head(
                f"{title} — LLM Wiki",
                f"Side-by-side comparison of {title}.",
                css_prefix="../",
            )
            + nav_bar("vs", link_prefix="../")
            + hero(title, f"{pair['score']} shared structured fields")
            + article_body
            + "</main>\n"
            + page_foot(js_prefix="../")
        )
        (vs_out / f"{slug}.html").write_text(page, encoding="utf-8")

    return index_path, len(pairs)


# ─── search index ──────────────────────────────────────────────────────────

def build_search_index(
    sources: list[tuple[Path, dict[str, Any], str]],
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    out_dir: Path,
    *,
    search_mode: str = "auto",
) -> Path:
    """Build a chunked search index for lazy loading (#47).

    Writes:
      search-index.json          — meta entries (projects + pages) + _chunks manifest
                                  + _mode + _tree_eligible_ratio (#53)
      search-chunks/<project>.json — session entries per project, each
                                    carrying heading_max_depth + count_by_depth

    `search_mode` accepts ``auto`` (default, heuristic), ``tree``, or
    ``flat`` — matches the `llmwiki build --search-mode` flag.
    """
    from llmwiki.search_tree import (
        annotate_entry_headings,
        decide_search_mode,
        search_index_footer_badge,
    )
    # ── session entries grouped by project ──
    from llmwiki.search_facets import enrich_entry
    chunks: dict[str, list[dict[str, Any]]] = {}
    for p, meta, body in sources:
        project = str(meta.get("project") or p.parent.name)
        slug = str(meta.get("slug", p.stem))
        plain = md_to_plain_text(body)[:1200]
        entry = {
            "id": f"session:{project}/{p.stem}",
            "url": f"sessions/{project}/{p.stem}.html",
            "title": slug,
            "type": "session",
            "project": project,
            "date": str(meta.get("date", "")),
            "model": str(meta.get("model", "")),
            "body": plain,
        }
        # v1.0 (#161): enrich with facet fields.
        enrich_entry(entry, meta)
        # v1.2 (#53): inject heading depth so the client can tree-walk.
        annotate_entry_headings(entry, body)
        chunks.setdefault(project, []).append(entry)

    # ── write per-project chunks ──
    chunks_dir = out_dir / "search-chunks"
    chunks_dir.mkdir(exist_ok=True)
    chunk_manifest: list[str] = []
    total_chunk_bytes = 0
    for project_slug, entries in sorted(chunks.items()):
        chunk_path = chunks_dir / f"{project_slug}.json"
        data = json.dumps(entries, ensure_ascii=False)
        chunk_path.write_text(data, encoding="utf-8")
        chunk_manifest.append(f"search-chunks/{project_slug}.json")
        total_chunk_bytes += len(data.encode("utf-8"))

    # ── meta index: projects + static pages + chunk manifest ──
    meta_entries: list[dict[str, Any]] = []

    for project, sessions in groups.items():
        meta_entries.append(
            {
                "id": f"project:{project}",
                "url": f"projects/{project}.html",
                "title": project,
                "type": "project",
                "project": project,
                "date": "",
                "model": "",
                "body": f"{len(sessions)} sessions",
            }
        )

    meta_entries.append(
        {"id": "home", "url": "index.html", "title": "Home", "type": "page",
         "project": "", "date": "", "model": "", "body": "overview index"}
    )
    meta_entries.append(
        {"id": "projects-index", "url": "projects/index.html", "title": "Projects",
         "type": "page", "project": "", "date": "", "model": "", "body": "all projects"}
    )
    meta_entries.append(
        {"id": "sessions-index", "url": "sessions/index.html", "title": "All sessions",
         "type": "page", "project": "", "date": "", "model": "", "body": "sortable sessions table"}
    )

    # v1.0 (#161): aggregate facet counts across all session chunks so the
    # client can render filter checkboxes without scanning the full index.
    from llmwiki.search_facets import aggregate_facets
    all_entries: list[dict[str, Any]] = []
    for chunk_entries in chunks.values():
        all_entries.extend(chunk_entries)
    facets = aggregate_facets(all_entries)

    # v1.2 (#53): decide tree vs flat across *all* entries, surface
    # the ratio so the client can show it in the palette footer.
    mode, tree_ratio = decide_search_mode(all_entries, override=search_mode)
    mode_badge = search_index_footer_badge(mode, tree_ratio)

    index_obj = {
        "entries": meta_entries,
        "_chunks": chunk_manifest,
        "_facets": facets,
        "_mode": mode,
        "_tree_eligible_ratio": round(tree_ratio, 4),
        "_mode_badge": mode_badge,
    }
    out_path = out_dir / "search-index.json"
    out_path.write_text(json.dumps(index_obj, ensure_ascii=False), encoding="utf-8")

    meta_kb = len(json.dumps(index_obj).encode("utf-8")) // 1024
    chunks_kb = total_chunk_bytes // 1024
    print(
        f"  wrote search-index.json ({meta_kb} KB meta) + "
        f"{len(chunk_manifest)} chunks ({chunks_kb} KB total) · {mode_badge}"
    )

    return out_path


# ─── css + js constants ────────────────────────────────────────────────────

# ─── css + js ────────────────────────────────────────────────────────────
# CSS + JS constants live in llmwiki/render/ since v1.1 (#217). Re-export
# here for backwards compatibility — any external caller still doing
# `from llmwiki.build import CSS` keeps working.
from llmwiki.render.css import CSS  # noqa: F401 (re-exported)
from llmwiki.render.js import JS  # noqa: F401 (re-exported)



# ─── claude synthesis (optional) ───────────────────────────────────────────

def synthesize_overview(
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    claude_path: str,
) -> Optional[str]:
    if not Path(claude_path).exists():
        print(f"  warning: claude CLI not found at {claude_path}", file=sys.stderr)
        return None

    lines: list[str] = [
        "You are writing a short (200-300 word) overview for a personal knowledge-base",
        "landing page. Below is a JSON summary of the user's Claude Code session history",
        "across multiple projects. Write 2-3 paragraphs of prose in markdown that:",
        "  1. Names the main projects and what each is about (infer from session slugs and tool usage)",
        "  2. Highlights the busiest project(s) and the overall scale of the work",
        "  3. Is written in third person, referring to the user as 'the developer'",
        "Do NOT use bullet points. Just 2-3 short paragraphs of prose.",
        "",
        "Data:",
        "",
    ]
    brief: dict[str, Any] = {}
    for project, sessions in sorted(groups.items()):
        brief[project] = {
            "session_count": len(sessions),
            "main_sessions": sum(1 for p, _, _ in sessions if "subagent" not in p.name),
            "dates": sorted({str(m.get("date", "")) for _, m, _ in sessions if m.get("date")}),
            "models": sorted({str(m.get("model", "")) for _, m, _ in sessions if m.get("model")}),
            "slugs": [str(m.get("slug", p.stem)) for p, m, _ in sessions[:8]],
        }
    prompt = "\n".join(lines) + json.dumps(brief, indent=2)

    print("  calling claude CLI for overview synthesis…")
    try:
        result = subprocess.run(
            [claude_path, "-p", prompt, "--model", "claude-haiku-4-5-20251001"],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("  warning: claude CLI timed out after 120s", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  warning: claude CLI failed: {e}", file=sys.stderr)
        return None
    if result.returncode != 0:
        print(f"  warning: claude CLI exited {result.returncode}", file=sys.stderr)
        return None
    return result.stdout.strip() or None


# ─── main ──────────────────────────────────────────────────────────────────

def build_site(
    out_dir: Path = DEFAULT_OUT_DIR,
    synthesize: bool = False,
    claude_path: str = "/usr/local/bin/claude",
    search_mode: str = "auto",
) -> int:
    if not RAW_SESSIONS.exists():
        print(
            f"error: {RAW_SESSIONS} does not exist. Run `llmwiki init` + `llmwiki sync` first.",
            file=sys.stderr,
        )
        return 2

    print(f"==> scanning {RAW_SESSIONS}")
    sources = discover_sources(RAW_SESSIONS)
    if not sources:
        print("  no sources found.", file=sys.stderr)
        return 2
    print(f"  found {len(sources)} source markdowns")
    groups = group_by_project(sources)
    print(f"  grouped into {len(groups)} projects")

    # Reset output dir (clear contents only — the HTTP server may be cwd'd here)
    if out_dir.exists():
        for child in out_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass
    else:
        out_dir.mkdir(parents=True)

    # CSS + JS
    (out_dir / "style.css").write_text(CSS, encoding="utf-8")
    (out_dir / "script.js").write_text(JS, encoding="utf-8")
    print("  wrote style.css, script.js")

    # Copy raw markdown files for "Download .md" links
    sources_out = out_dir / "sources"
    if sources_out.exists():
        shutil.rmtree(sources_out)
    shutil.copytree(RAW_SESSIONS, sources_out)
    print(f"  copied raw .md sources to sources/")

    # v0.7 (#96): copy downloaded image assets into site/assets/
    raw_assets = RAW_DIR / "assets"
    if raw_assets.exists() and any(raw_assets.iterdir()):
        site_assets = out_dir / "assets"
        if site_assets.exists():
            shutil.rmtree(site_assets)
        shutil.copytree(raw_assets, site_assets)
        asset_count = sum(1 for _ in site_assets.iterdir() if _.is_file())
        print(f"  copied {asset_count} image assets to assets/")

    # Synthesis
    synthesis = None
    if synthesize:
        synthesis = synthesize_overview(groups, claude_path)
        if synthesis:
            print(f"  synthesis: {len(synthesis)} chars")

    # Render pages
    n_sessions = 0
    for path, meta, body in sources:
        project = str(meta.get("project") or path.parent.name)
        render_session(path, meta, body, out_dir, project)
        n_sessions += 1
    print(f"  wrote {n_sessions} session pages")

    for project, sessions in groups.items():
        render_project_page(project, sessions, out_dir)
    print(f"  wrote {len(groups)} project pages")

    render_projects_index(groups, out_dir)
    render_sessions_index(sources, groups, out_dir)
    render_index(groups, sources, out_dir, synthesis=synthesis)
    cl_path = render_changelog(out_dir)
    # v0.7 (#55): models section — sortable index + per-model detail pages.
    models_index_path, model_count = render_models_section(out_dir)
    # v0.7 (#58): auto-generated vs-comparison pages + index.
    vs_index_path, pair_count = render_vs_section(out_dir)
    print(
        "  wrote index.html, projects/index.html, sessions/index.html"
        + (", changelog.html" if cl_path else "")
        + f", models/index.html ({model_count} models)"
        + f", vs/index.html ({pair_count} comparisons)"
    )

    # Search index (chunked — #47) + tree/flat auto-routing (#53)
    idx_path = build_search_index(sources, groups, out_dir, search_mode=search_mode)

    # v0.4: AI-consumable exports (llms.txt, llms-full.txt, graph.jsonld,
    # sitemap.xml, rss.xml, robots.txt, ai-readme.md)
    try:
        from llmwiki.exporters import export_all
        ai_paths = export_all(out_dir, groups, sources)
        print(f"  wrote {len(ai_paths)} AI-consumable exports: {', '.join(sorted(ai_paths.keys()))}")
    except Exception as e:
        print(f"  warning: AI exports failed: {e}", file=sys.stderr)

    # v1.1 (#118): copy the interactive knowledge graph into the site
    # so the "Graph" nav link works without a separate `llmwiki graph` step.
    try:
        from llmwiki.graph import copy_to_site as copy_graph_to_site
        graph_path = copy_graph_to_site(out_dir)
        if graph_path:
            print(f"  wrote {graph_path.relative_to(out_dir.parent)} (interactive graph viewer)")
    except Exception as e:
        print(f"  warning: graph viewer copy failed: {e}", file=sys.stderr)

    # v1.2 (#114): publish the prototype hub (review-ready UI states)
    # under site/prototypes/ for UX iteration.
    try:
        from llmwiki.prototypes import build_prototype_hub
        proto_index = build_prototype_hub(out_dir)
        print(f"  wrote {proto_index.relative_to(out_dir.parent)} (6 prototype states)")
    except Exception as e:
        print(f"  warning: prototype hub build failed: {e}", file=sys.stderr)

    # v1.2 (#265): compile the editorial docs (tutorials + hub) under
    # site/docs/. Only pages with `docs_shell: true` in frontmatter
    # are included — reference docs that stay GitHub-rendered aren't
    # touched.
    try:
        from llmwiki.docs_pages import compile_docs_site
        docs_dir = REPO_ROOT / "docs"

        # nav_builder gets called per-page with the right link_prefix so
        # the nav bar's hrefs resolve from whatever depth the page sits at.
        def _docs_nav(link_prefix: str) -> str:
            return nav_bar(active="docs", link_prefix=link_prefix)

        docs_written = compile_docs_site(
            docs_dir,
            out_dir,
            md_to_html=md_to_html,
            page_head=page_head,
            nav_builder=_docs_nav,
        )
        if docs_written:
            print(
                f"  wrote site/docs/ ({len(docs_written)} editorial pages: "
                "hub + tutorials + style guide)"
            )
    except Exception as e:
        print(f"  warning: docs compile failed: {e}", file=sys.stderr)

    # v0.4: Per-page sibling .txt and .json
    try:
        from llmwiki.exporters import write_page_txt, write_page_json
        n_siblings = 0
        for path, meta, body in sources:
            project = str(meta.get("project") or path.parent.name)
            slug = str(meta.get("slug", path.stem))
            html_path = out_dir / "sessions" / project / f"{path.stem}.html"
            if html_path.exists():
                body_stripped = strip_leading_h1(body)
                wikilinks_out = [m for m in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", body_stripped)]
                write_page_txt(html_path, body_stripped)
                # Inject slug/title back into meta if missing
                meta_copy = dict(meta)
                meta_copy.setdefault("slug", slug)
                meta_copy.setdefault("project", project)
                write_page_json(html_path, meta_copy, body_stripped, wikilinks_out)
                n_siblings += 2
        print(f"  wrote {n_siblings} per-page siblings (.txt + .json)")
    except Exception as e:
        print(f"  warning: per-page siblings failed: {e}", file=sys.stderr)

    # v0.4: Build manifest with SHA-256 hashes
    try:
        from llmwiki.manifest import write_manifest
        manifest_path = write_manifest(out_dir)
        print(f"  wrote {manifest_path.relative_to(out_dir.parent) if manifest_path.is_relative_to(out_dir.parent) else manifest_path.name}")
    except Exception as e:
        print(f"  warning: manifest failed: {e}", file=sys.stderr)

    total_files = sum(1 for _ in out_dir.rglob("*.html"))
    total_bytes = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    print(
        f"==> build complete: {total_files} HTML files, {total_bytes / 1024:.0f} KB total"
    )
    print(f"    output: {out_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--synthesize", action="store_true")
    p.add_argument("--claude", type=str, default="/usr/local/bin/claude")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    return build_site(
        out_dir=args.out,
        synthesize=args.synthesize,
        claude_path=args.claude,
    )


if __name__ == "__main__":
    sys.exit(main())

# ─── agent label detection ────────────────────────────────────────────────
# v0.9: Detect which AI agent produced a session from the model name,
# source_file path, or explicit frontmatter field. Returns a short label
# + CSS class for badge rendering.

def detect_agent_label(meta: dict) -> tuple[str, str]:
    """Return (label, css_class) for the agent that produced this session.
    
    Detection order:
    1. Explicit `agent:` frontmatter field (set by adapters)
    2. Model name patterns (claude-* → Claude, gpt-* → Codex/Copilot, etc.)
    3. Source file path patterns (codex → Codex, copilot → Copilot)
    4. Default: "Unknown"
    """
    # 1. Explicit field
    agent = str(meta.get("agent", "")).strip().lower()
    if agent:
        return _agent_map(agent)
    
    # 2. Model name
    model = str(meta.get("model", "")).lower()
    if "claude" in model:
        return ("Claude", "agent-claude")
    if "gpt" in model or "o1" in model or "o3" in model or "o4" in model:
        return ("Codex", "agent-codex")
    if "gemini" in model:
        return ("Gemini", "agent-gemini")
    if "copilot" in model:
        return ("Copilot", "agent-copilot")
    
    # 3. Source file path
    source = str(meta.get("source_file", "")).lower()
    if "codex" in source or ".codex" in source:
        return ("Codex", "agent-codex")
    if "copilot" in source:
        return ("Copilot", "agent-copilot")
    if "cursor" in source:
        return ("Cursor", "agent-cursor")
    if "gemini" in source:
        return ("Gemini", "agent-gemini")
    if "claude" in source or ".claude" in source:
        return ("Claude", "agent-claude")
    
    # 4. Tags fallback
    tags = meta.get("tags", [])
    if isinstance(tags, list):
        tag_str = " ".join(str(t).lower() for t in tags)
    else:
        tag_str = str(tags).lower()
    if "codex" in tag_str:
        return ("Codex", "agent-codex")
    if "copilot" in tag_str:
        return ("Copilot", "agent-copilot")
    if "claude" in tag_str:
        return ("Claude", "agent-claude")
    
    return ("Agent", "agent-unknown")


def _agent_map(agent: str) -> tuple[str, str]:
    """Map an explicit agent name to (label, css_class)."""
    m = {
        "claude": ("Claude", "agent-claude"),
        "claude-code": ("Claude", "agent-claude"),
        "codex": ("Codex", "agent-codex"),
        "codex-cli": ("Codex", "agent-codex"),
        "copilot": ("Copilot", "agent-copilot"),
        "copilot-chat": ("Copilot", "agent-copilot"),
        "copilot-cli": ("Copilot", "agent-copilot"),
        "cursor": ("Cursor", "agent-cursor"),
        "gemini": ("Gemini", "agent-gemini"),
        "gemini-cli": ("Gemini", "agent-gemini"),
        "obsidian": ("Obsidian", "agent-obsidian"),
        "pdf": ("PDF", "agent-pdf"),
    }
    return m.get(agent, (agent.title(), "agent-unknown"))


def render_agent_badge(meta: dict) -> str:
    """Render an inline agent badge chip."""
    label, css_class = detect_agent_label(meta)
    return f'<span class="agent-badge {html.escape(css_class)}">{html.escape(label)}</span>'

# Inject agent badge CSS into the CSS constant
# (This is appended at the module level — it'll be picked up on next build)
