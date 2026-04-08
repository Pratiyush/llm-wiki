"""llmwiki — static HTML site builder.

Reads converted markdown sources under `raw/` and produces a complete static
site under `site/` with:

- Home + projects index + sessions index + per-project + per-session pages
- Inter + JetBrains Mono typography, purple accent (#7C3AED)
- Light / dark theme toggle (data-theme + system preference + localStorage)
- Global search index (site/search-index.json) — client-side fuzzy matcher
- Cmd+K command palette (vanilla JS, no framework)
- Keyboard shortcuts: /, g h, g p, g s, j/k, ?
- Pygments syntax highlighting (via codehilite) — optional dep
- Collapsible tool-result sections (<details>) for long outputs
- Copy-as-markdown + copy-code buttons (Clipboard API + execCommand fallback)
- Breadcrumbs + reading progress bar
- Filter bar on the sessions table
- Mobile-responsive, print-friendly
- ARIA focus rings and prefers-reduced-motion support

Stdlib + `markdown` (required) + `pygments` (optional for highlighting).
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
from pathlib import Path
from typing import Any, Optional

import markdown

from llmwiki import REPO_ROOT

# ─── paths ─────────────────────────────────────────────────────────────────

RAW_DIR = REPO_ROOT / "raw"
RAW_SESSIONS = RAW_DIR / "sessions"
DEFAULT_OUT_DIR = REPO_ROOT / "site"

# ─── pygments detection ────────────────────────────────────────────────────

try:
    import pygments  # noqa: F401
    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False


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


def md_to_html(body: str) -> str:
    body = normalize_markdown(body)
    extensions = ["fenced_code", "tables", "toc", "sane_lists"]
    ext_configs: dict[str, dict[str, Any]] = {
        "toc": {"permalink": True, "toc_depth": "2-3"},
    }
    if HAS_PYGMENTS:
        extensions.append("codehilite")
        ext_configs["codehilite"] = {
            "css_class": "codehilite",
            "linenums": False,
            "guess_lang": True,
        }
    md = markdown.Markdown(extensions=extensions, extension_configs=ext_configs)
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


# ─── html template helpers ─────────────────────────────────────────────────

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
  <link rel="stylesheet" href="{css_prefix}style.css">
</head>
<body>
<div class="progress-bar" id="progress-bar"></div>
"""


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
    return f"""<main>
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
<div id="palette" class="palette" aria-hidden="true">
  <div class="palette-backdrop" id="palette-backdrop"></div>
  <div class="palette-modal" role="dialog" aria-modal="true" aria-label="Command palette">
    <div class="palette-header">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input type="text" id="palette-input" placeholder="Jump to a page or search the wiki…" autocomplete="off" spellcheck="false">
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
    <button class="btn" id="help-close">Close</button>
  </div>
</div>
<script src="{js_prefix}search-index.json" type="application/json" id="search-index-hint"></script>
<script>window.LLMWIKI_INDEX_URL = "{js_prefix}search-index.json";</script>
<script src="{js_prefix}script.js"></script>
</body>
</html>
"""


# ─── page renderers ────────────────────────────────────────────────────────

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

    bits: list[str] = []
    if meta.get("project"):
        bits.append(
            f'<a href="../../projects/{html.escape(str(meta["project"]))}.html">{html.escape(str(meta["project"]))}</a>'
        )
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
    meta_strip = " · ".join(bits) if bits else ""

    tools_list = get_tools_list(meta)
    tools_preview = ""
    if tools_list:
        preview = ", ".join(tools_list[:6])
        if len(tools_list) > 6:
            preview += f", +{len(tools_list) - 6} more"
        tools_preview = f'<div class="meta-tools muted">tools: {html.escape(preview)}</div>'

    raw_md_path = f"../../sources/{project_slug}/{path.name}"
    actions_html = f"""<div class="session-actions">
  <button class="btn btn-primary" onclick="copyMarkdown(this)">Copy as markdown</button>
  <a class="btn" href="../../projects/{html.escape(project_slug)}.html">← {html.escape(project_slug)}</a>
  <a class="btn" href="{html.escape(raw_md_path)}" download>Download .md</a>
  <textarea class="md-source" hidden>{raw_md_for_copy}</textarea>
</div>"""

    crumbs = [
        ("Home", "index.html"),
        ("Projects", "projects/index.html"),
        (project_slug, f"projects/{project_slug}.html"),
        (str(slug), ""),
    ]
    breadcrumbs = breadcrumbs_bar(crumbs, link_prefix="../../")

    page = (
        page_head(
            f"{title_raw} — LLM Wiki",
            f"Session transcript from {meta.get('project', '')} on {date}",
            css_prefix="../../",
        )
        + nav_bar("sessions", link_prefix="../../")
        + hero(str(title_raw), meta_strip, size="hero-sm", subtitle_is_html=True)
        + f'<section class="section">\n  <div class="container">\n{breadcrumbs}\n{tools_preview}\n{actions_html}\n    <article class="content">\n'
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
        return f"""  <a class="card" href="{href}">
    <div class="card-title">{html.escape(str(slug))}</div>
    <div class="card-meta">{html.escape(str(date))} · {html.escape(str(model))}</div>
    <div class="card-stats muted">{html.escape(str(umsgs))} messages · {html.escape(str(tcalls))} tool calls</div>
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

    body = f"""<section class="section">
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
        cards.append(
            f"""  <a class="card" href="{html.escape(project)}.html">
    <div class="card-title">{html.escape(project)}</div>
    <div class="card-meta">{main_count} main · {sub_count} sub-agent</div>
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
        <tr><th>Session</th><th>Project</th><th>Date</th><th>Model</th><th>Msgs</th><th>Tools</th></tr>
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

    cards = []
    for project, sessions in sorted(groups.items(), key=lambda x: -len(x[1])):
        main_count = sum(1 for p, _, _ in sessions if "subagent" not in p.name)
        cards.append(
            f"""  <a class="card" href="projects/{html.escape(project)}.html">
    <div class="card-title">{html.escape(project)}</div>
    <div class="card-meta">{main_count} main · {len(sessions) - main_count} sub-agent</div>
  </a>"""
        )

    body = f"""<section class="section">
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


# ─── search index ──────────────────────────────────────────────────────────

def build_search_index(
    sources: list[tuple[Path, dict[str, Any], str]],
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    out_dir: Path,
) -> Path:
    entries: list[dict[str, Any]] = []

    # Add each session
    for p, meta, body in sources:
        project = str(meta.get("project") or p.parent.name)
        slug = str(meta.get("slug", p.stem))
        plain = md_to_plain_text(body)[:1200]
        entries.append(
            {
                "id": f"session:{project}/{p.stem}",
                "url": f"sessions/{project}/{p.stem}.html",
                "title": slug,
                "type": "session",
                "project": project,
                "date": str(meta.get("date", "")),
                "model": str(meta.get("model", "")),
                "body": plain,
            }
        )

    # Add each project page
    for project, sessions in groups.items():
        entries.append(
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

    # Add the top-level pages
    entries.append(
        {
            "id": "home",
            "url": "index.html",
            "title": "Home",
            "type": "page",
            "project": "",
            "date": "",
            "model": "",
            "body": "overview index",
        }
    )
    entries.append(
        {
            "id": "projects-index",
            "url": "projects/index.html",
            "title": "Projects",
            "type": "page",
            "project": "",
            "date": "",
            "model": "",
            "body": "all projects",
        }
    )
    entries.append(
        {
            "id": "sessions-index",
            "url": "sessions/index.html",
            "title": "All sessions",
            "type": "page",
            "project": "",
            "date": "",
            "model": "",
            "body": "sortable sessions table",
        }
    )

    out_path = out_dir / "search-index.json"
    out_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return out_path


# ─── css + js constants ────────────────────────────────────────────────────

CSS = """/* llmwiki — god-level docs style */
:root {
  --bg: #ffffff;
  --bg-alt: #f8fafc;
  --bg-card: #ffffff;
  --bg-code: #f1f5f9;
  --text: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --border: #e2e8f0;
  --accent: #7C3AED;
  --accent-light: #a78bfa;
  --accent-bg: #f5f3ff;
  --radius: 8px;
  --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
  --shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.04);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0c0a1d;
    --bg-alt: #110f26;
    --bg-card: #16142d;
    --bg-code: #1a1836;
    --text: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --border: #2d2b4a;
    --accent-bg: #1e1a3a;
    --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
  }
}
:root[data-theme="dark"] {
  --bg: #0c0a1d;
  --bg-alt: #110f26;
  --bg-card: #16142d;
  --bg-code: #1a1836;
  --text: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --border: #2d2b4a;
  --accent-bg: #1e1a3a;
  --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }
body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.7; -webkit-font-smoothing: antialiased; overflow-wrap: break-word; word-wrap: break-word; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
.container { max-width: 1080px; margin: 0 auto; padding: 0 24px; }
.muted { color: var(--text-muted); }
kbd { display: inline-block; padding: 2px 6px; font-family: var(--mono); font-size: 0.72rem; color: var(--text-secondary); background: var(--bg-code); border: 1px solid var(--border); border-radius: 4px; line-height: 1; }

/* Reading progress bar */
.progress-bar { position: fixed; top: 0; left: 0; height: 3px; width: 0%; background: var(--accent); z-index: 200; transition: width 0.1s; }

/* Nav */
.nav { position: sticky; top: 0; z-index: 100; background: var(--bg); border-bottom: 1px solid var(--border); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); }
.nav-inner { max-width: 1080px; margin: 0 auto; padding: 0 24px; height: 56px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.nav-brand { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 0.95rem; color: var(--text); text-decoration: none; flex-shrink: 0; }
.nav-brand:hover { text-decoration: none; }
.nav-links { display: flex; align-items: center; gap: 20px; }
.nav-links a { color: var(--text-secondary); font-size: 0.9rem; font-weight: 500; text-decoration: none; }
.nav-links a:hover { color: var(--text); text-decoration: none; }
.nav-links a.active { color: var(--accent); }

.nav-search-btn { display: flex; align-items: center; gap: 8px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; font-family: var(--font); color: var(--text-secondary); cursor: pointer; font-size: 0.82rem; transition: all 0.15s; }
.nav-search-btn:hover { border-color: var(--accent); color: var(--accent); }
.nav-search-btn svg { flex-shrink: 0; }
@media (max-width: 720px) { .nav-search-btn span, .nav-search-btn kbd { display: none; } }

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
.hero { padding: 56px 0 40px; background: var(--bg-alt); border-bottom: 1px solid var(--border); }
.hero-sm { padding: 32px 0 24px; }
.hero h1 { font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; color: var(--text); margin-bottom: 8px; overflow-wrap: break-word; }
.hero .hero-sub { color: var(--text-secondary); font-size: 0.9rem; line-height: 1.6; overflow-wrap: break-word; }
.hero .hero-sub code { font-family: var(--mono); background: var(--bg-card); padding: 1px 6px; border-radius: 4px; font-size: 0.82rem; border: 1px solid var(--border); }
.hero .hero-sub a { color: var(--accent); font-weight: 500; }

/* Breadcrumbs */
.breadcrumbs { font-size: 0.82rem; color: var(--text-muted); margin-bottom: 16px; }
.breadcrumbs a { color: var(--text-secondary); }
.breadcrumbs a:hover { color: var(--accent); text-decoration: none; }
.breadcrumbs .crumb-sep { margin: 0 6px; color: var(--text-muted); }
.breadcrumbs [aria-current="page"] { color: var(--text); font-weight: 500; }

/* Section */
.section { padding: 28px 0 56px; }
.section h2 { font-size: 1.5rem; font-weight: 700; margin: 24px 0 16px; color: var(--text); }
.section h3 { font-size: 1.15rem; font-weight: 600; margin: 20px 0 10px; color: var(--text); }

.meta-tools { font-size: 0.82rem; margin-bottom: 12px; overflow-wrap: break-word; }

/* Actions strip */
.session-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
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

/* Pygments codehilite */
.codehilite { background: var(--bg-code); border-radius: var(--radius); border: 1px solid var(--border); margin: 16px 0; overflow-x: auto; }
.codehilite pre { border: none; margin: 0; }
.codehilite .k, .codehilite .kd, .codehilite .kn { color: #7C3AED; font-weight: 600; } /* keyword */
.codehilite .s, .codehilite .s1, .codehilite .s2 { color: #059669; } /* string */
.codehilite .c, .codehilite .c1, .codehilite .cm { color: #64748b; font-style: italic; } /* comment */
.codehilite .n, .codehilite .nx { color: var(--text); } /* name */
.codehilite .nf, .codehilite .na { color: #2563eb; } /* function, attr */
.codehilite .mi, .codehilite .mf { color: #d97706; } /* number */
.codehilite .o, .codehilite .p { color: var(--text-secondary); } /* operator */
:root[data-theme="dark"] .codehilite .s, :root[data-theme="dark"] .codehilite .s1, :root[data-theme="dark"] .codehilite .s2 { color: #34d399; }
:root[data-theme="dark"] .codehilite .nf, :root[data-theme="dark"] .codehilite .na { color: #60a5fa; }
:root[data-theme="dark"] .codehilite .mi, :root[data-theme="dark"] .codehilite .mf { color: #fbbf24; }

/* Cards */
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin: 16px 0; }
.card { display: block; padding: 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); text-decoration: none; color: var(--text); transition: all 0.15s; }
.card:hover { border-color: var(--accent); text-decoration: none; transform: translateY(-1px); box-shadow: var(--shadow); }
.card-title { font-weight: 600; font-size: 0.95rem; margin-bottom: 4px; color: var(--text); }
.card-meta { font-size: 0.82rem; color: var(--text-secondary); }
.card-stats { font-size: 0.78rem; margin-top: 6px; }

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

/* Print */
@media print {
  .nav, .footer, .palette, .help-dialog, .session-actions, .filter-bar, .progress-bar, .nav-search-btn, .theme-toggle, .copy-code-btn { display: none !important; }
  body { background: #fff; color: #000; }
  .content { font-size: 11pt; }
  a { color: #000; text-decoration: underline; }
}
"""

JS = r"""// llmwiki viewer — theme + copy + search palette + keyboard shortcuts + progress bar + filter bar
// Vanilla JS, no framework.

// ─── Theme toggle ─────────────────────────────────────────────────────────
(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem("llmwiki-theme");
  if (saved === "dark" || saved === "light") root.setAttribute("data-theme", saved);
  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const current = root.getAttribute("data-theme");
      const next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem("llmwiki-theme", next);
    });
  });
})();

// ─── Reading progress bar ────────────────────────────────────────────────
(function () {
  const bar = document.getElementById("progress-bar");
  if (!bar) return;
  function update() {
    const h = document.documentElement;
    const scrolled = h.scrollTop || document.body.scrollTop;
    const height = (h.scrollHeight || document.body.scrollHeight) - h.clientHeight;
    const pct = height > 0 ? (scrolled / height) * 100 : 0;
    bar.style.width = Math.min(100, Math.max(0, pct)) + "%";
  }
  window.addEventListener("scroll", update, { passive: true });
  update();
})();

// ─── Copy-as-markdown (inline handler) ───────────────────────────────────
function copyMarkdown(btn) {
  const ta = btn.parentElement.querySelector(".md-source");
  if (!ta) return;
  const text = ta.value.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  const finish = function (ok) {
    btn.textContent = ok ? "Copied!" : "Failed";
    btn.classList.add("copied");
    setTimeout(function () { btn.textContent = "Copy as markdown"; btn.classList.remove("copied"); }, 1800);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () { finish(true); }, function () { finish(false); });
  } else {
    const tmp = document.createElement("textarea");
    tmp.value = text; tmp.style.position = "fixed"; tmp.style.left = "-9999px";
    document.body.appendChild(tmp); tmp.select();
    try { document.execCommand("copy"); finish(true); } catch (e) { finish(false); }
    document.body.removeChild(tmp);
  }
}

// ─── Copy-code buttons on every <pre> ────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".content pre").forEach(function (pre) {
    if (pre.parentElement && pre.parentElement.classList.contains("code-wrap")) return;
    const wrap = document.createElement("div"); wrap.className = "code-wrap";
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);
    const btn = document.createElement("button");
    btn.className = "copy-code-btn"; btn.type = "button"; btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      const code = pre.querySelector("code");
      const text = code ? code.innerText : pre.innerText;
      const finish = function (ok) {
        btn.textContent = ok ? "Copied!" : "Failed"; btn.classList.add("copied");
        setTimeout(function () { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 1500);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { finish(true); }, function () { finish(false); });
      } else {
        const tmp = document.createElement("textarea");
        tmp.value = text; tmp.style.position = "fixed"; tmp.style.left = "-9999px";
        document.body.appendChild(tmp); tmp.select();
        try { document.execCommand("copy"); finish(true); } catch (e) { finish(false); }
        document.body.removeChild(tmp);
      }
    });
    wrap.appendChild(btn);
  });
});

// ─── Auto-collapse long tool results into <details> ──────────────────────
document.addEventListener("DOMContentLoaded", function () {
  // Wrap long <pre> outputs and long paragraph lists under "Tool results:"
  const markers = document.querySelectorAll(".content p strong");
  markers.forEach(function (s) {
    const text = (s.textContent || "").trim();
    if (text !== "Tool results:") return;
    const p = s.closest("p");
    if (!p) return;
    // Check if the next sibling has very long text
    let next = p.nextElementSibling;
    if (!next) return;
    const combinedText = (next.innerText || "").trim();
    if (combinedText.length < 500) return;
    // Wrap next element in a <details>
    const det = document.createElement("details");
    det.className = "collapsible-result";
    const sum = document.createElement("summary");
    sum.textContent = "Tool results (" + combinedText.length + " chars) — click to expand";
    det.appendChild(sum);
    next.parentNode.insertBefore(det, next);
    det.appendChild(next);
  });
});

// ─── Command palette (Cmd+K) + search index loader ─────────────────────
(function () {
  let idx = null;
  let idxPromise = null;
  let activeIdx = 0;
  let currentResults = [];

  function loadIndex() {
    if (idx) return Promise.resolve(idx);
    if (idxPromise) return idxPromise;
    const url = window.LLMWIKI_INDEX_URL || "search-index.json";
    idxPromise = fetch(url)
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (data) { idx = data || []; return idx; })
      .catch(function () { idx = []; return idx; });
    return idxPromise;
  }

  function score(entry, query) {
    if (!query) return 0;
    const q = query.toLowerCase();
    const title = (entry.title || "").toLowerCase();
    const project = (entry.project || "").toLowerCase();
    const body = (entry.body || "").toLowerCase();
    let s = 0;
    if (title === q) s += 100;
    else if (title.indexOf(q) === 0) s += 60;
    else if (title.indexOf(q) !== -1) s += 40;
    if (project.indexOf(q) !== -1) s += 20;
    if (body.indexOf(q) !== -1) s += 10;
    // Token match
    const tokens = q.split(/\s+/).filter(Boolean);
    let allMatch = true;
    tokens.forEach(function (t) {
      if (title.indexOf(t) === -1 && project.indexOf(t) === -1 && body.indexOf(t) === -1) allMatch = false;
    });
    if (allMatch && tokens.length > 1) s += 30;
    return s;
  }

  function search(query) {
    if (!idx) return [];
    if (!query) return idx.slice(0, 10);
    return idx
      .map(function (e) { return { entry: e, score: score(e, query) }; })
      .filter(function (r) { return r.score > 0; })
      .sort(function (a, b) { return b.score - a.score; })
      .slice(0, 15)
      .map(function (r) { return r.entry; });
  }

  function renderResults(results) {
    const ul = document.getElementById("palette-results");
    if (!ul) return;
    currentResults = results;
    activeIdx = 0;
    ul.innerHTML = results.map(function (r, i) {
      const meta = [r.project, r.date, r.model].filter(Boolean).join(" · ");
      return '<li data-i="' + i + '" class="' + (i === 0 ? 'active' : '') + '">' +
        '<span class="result-type">' + (r.type || 'page') + '</span>' +
        '<span class="result-title">' + escapeHtml(r.title) + '</span>' +
        (meta ? '<div class="result-meta">' + escapeHtml(meta) + '</div>' : '') +
        '</li>';
    }).join("");
    ul.querySelectorAll("li").forEach(function (li) {
      li.addEventListener("click", function () {
        const i = parseInt(li.getAttribute("data-i"));
        openResult(i);
      });
    });
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function openResult(i) {
    if (!currentResults[i]) return;
    const pageUrl = window.LLMWIKI_INDEX_URL || "";
    // Compute base dir from current page URL
    const pathPrefix = pageUrl.substring(0, pageUrl.lastIndexOf("/") + 1) || "";
    window.location.href = pathPrefix + currentResults[i].url;
  }

  function openPalette() {
    const p = document.getElementById("palette");
    if (!p) return;
    p.setAttribute("aria-hidden", "false");
    const input = document.getElementById("palette-input");
    if (input) { input.value = ""; input.focus(); }
    loadIndex().then(function () { renderResults(search("")); });
  }

  function closePalette() {
    const p = document.getElementById("palette");
    if (!p) return;
    p.setAttribute("aria-hidden", "true");
  }

  function openHelp() {
    const d = document.getElementById("help-dialog");
    if (d) d.setAttribute("aria-hidden", "false");
  }
  function closeHelp() {
    const d = document.getElementById("help-dialog");
    if (d) d.setAttribute("aria-hidden", "true");
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Wire up buttons
    const openBtn = document.getElementById("open-palette");
    if (openBtn) openBtn.addEventListener("click", openPalette);

    const backdrop = document.getElementById("palette-backdrop");
    if (backdrop) backdrop.addEventListener("click", closePalette);

    const input = document.getElementById("palette-input");
    if (input) {
      input.addEventListener("input", function () { renderResults(search(input.value)); });
      input.addEventListener("keydown", function (e) {
        const items = document.querySelectorAll("#palette-results li");
        if (e.key === "ArrowDown") { e.preventDefault(); activeIdx = Math.min(items.length - 1, activeIdx + 1); updateActive(); }
        else if (e.key === "ArrowUp") { e.preventDefault(); activeIdx = Math.max(0, activeIdx - 1); updateActive(); }
        else if (e.key === "Enter") { e.preventDefault(); openResult(activeIdx); }
      });
    }

    const helpBackdrop = document.getElementById("help-backdrop");
    if (helpBackdrop) helpBackdrop.addEventListener("click", closeHelp);
    const helpClose = document.getElementById("help-close");
    if (helpClose) helpClose.addEventListener("click", closeHelp);
  });

  function updateActive() {
    const items = document.querySelectorAll("#palette-results li");
    items.forEach(function (li, i) { li.classList.toggle("active", i === activeIdx); });
    const active = items[activeIdx];
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  // ─── Keyboard shortcuts ─────────────────────────────────────────────────
  let gPressed = false;
  let gPressedTimer = null;
  document.addEventListener("keydown", function (e) {
    const inInput = e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT");

    // Cmd/Ctrl+K opens palette everywhere
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      openPalette();
      return;
    }
    // Esc closes palette / help / clears focus
    if (e.key === "Escape") {
      const p = document.getElementById("palette");
      const h = document.getElementById("help-dialog");
      if (p && p.getAttribute("aria-hidden") === "false") { closePalette(); return; }
      if (h && h.getAttribute("aria-hidden") === "false") { closeHelp(); return; }
      if (inInput) { e.target.blur(); return; }
    }

    // Shortcuts only work when not typing in an input
    if (inInput) return;

    if (e.key === "/") { e.preventDefault(); openPalette(); return; }
    if (e.key === "?") { e.preventDefault(); openHelp(); return; }

    // g-prefix shortcuts
    if (e.key === "g" && !gPressed) {
      gPressed = true;
      gPressedTimer = setTimeout(function () { gPressed = false; }, 1000);
      return;
    }
    if (gPressed) {
      gPressed = false;
      if (gPressedTimer) clearTimeout(gPressedTimer);
      const rel = window.LLMWIKI_INDEX_URL || "";
      const base = rel.substring(0, rel.lastIndexOf("/") + 1);
      if (e.key === "h") { window.location.href = base + "index.html"; return; }
      if (e.key === "p") { window.location.href = base + "projects/index.html"; return; }
      if (e.key === "s") { window.location.href = base + "sessions/index.html"; return; }
    }

    // j/k on sessions table
    const tbody = document.getElementById("sessions-tbody");
    if (tbody && (e.key === "j" || e.key === "k")) {
      e.preventDefault();
      const visibleRows = Array.from(tbody.querySelectorAll("tr")).filter(function (r) { return !r.hidden; });
      if (!visibleRows.length) return;
      let cur = visibleRows.findIndex(function (r) { return r.classList.contains("selected"); });
      if (cur === -1) cur = 0;
      else cur = e.key === "j" ? Math.min(visibleRows.length - 1, cur + 1) : Math.max(0, cur - 1);
      visibleRows.forEach(function (r) { r.classList.remove("selected"); });
      visibleRows[cur].classList.add("selected");
      visibleRows[cur].scrollIntoView({ block: "nearest" });
      // Enter on selected row navigates
    }
    if (e.key === "Enter" && tbody) {
      const sel = tbody.querySelector("tr.selected a");
      if (sel) { window.location.href = sel.href; }
    }
  });
})();

// ─── Sessions table filter bar ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
  const tbody = document.getElementById("sessions-tbody");
  if (!tbody) return;
  const fProject = document.getElementById("filter-project");
  const fModel = document.getElementById("filter-model");
  const fFrom = document.getElementById("filter-date-from");
  const fTo = document.getElementById("filter-date-to");
  const fText = document.getElementById("filter-text");
  const fClear = document.getElementById("filter-clear");
  const fCount = document.getElementById("filter-count");

  function apply() {
    const p = fProject ? fProject.value : "";
    const m = fModel ? fModel.value : "";
    const from = fFrom ? fFrom.value : "";
    const to = fTo ? fTo.value : "";
    const txt = fText ? fText.value.toLowerCase() : "";
    let shown = 0;
    Array.from(tbody.querySelectorAll("tr")).forEach(function (r) {
      const rp = r.getAttribute("data-project") || "";
      const rm = r.getAttribute("data-model") || "";
      const rd = r.getAttribute("data-date") || "";
      const rs = (r.getAttribute("data-slug") || "").toLowerCase();
      let show = true;
      if (p && rp !== p) show = false;
      if (m && rm !== m) show = false;
      if (from && rd < from) show = false;
      if (to && rd > to) show = false;
      if (txt && rs.indexOf(txt) === -1) show = false;
      r.hidden = !show;
      if (show) shown++;
    });
    if (fCount) fCount.textContent = shown + " shown";
  }

  [fProject, fModel, fFrom, fTo, fText].forEach(function (el) {
    if (el) el.addEventListener("input", apply);
  });
  if (fClear) fClear.addEventListener("click", function () {
    if (fProject) fProject.value = "";
    if (fModel) fModel.value = "";
    if (fFrom) fFrom.value = "";
    if (fTo) fTo.value = "";
    if (fText) fText.value = "";
    apply();
  });
  apply();
});
"""


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
    print("  wrote index.html, projects/index.html, sessions/index.html")

    # Search index
    idx_path = build_search_index(sources, groups, out_dir)
    try:
        idx_size = idx_path.stat().st_size
    except OSError:
        idx_size = 0
    print(f"  wrote search-index.json ({idx_size // 1024} KB)")

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
