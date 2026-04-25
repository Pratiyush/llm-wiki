"""AI-consumable export formats for llmwiki (v0.4+).

Produces standard formats that any AI agent can consume without scraping HTML:

- llms.txt            — short index per https://llmstxt.org
- llms-full.txt       — flattened plain-text dump of every wiki page
- graph.jsonld        — schema.org JSON-LD graph export
- <page>.txt          — sibling plain-text for every HTML page
- <page>.json         — sibling structured JSON for every HTML page
- sitemap.xml         — standard sitemap with lastmod
- rss.xml             — RSS 2.0 feed of newest sessions
- robots.txt          — with sitemap + llms.txt references
- ai-readme.md        — AI-specific entry point under wiki/

Stdlib only. Called from build.py after the HTML site is rendered.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT, __version__

# ─── helpers ──────────────────────────────────────────────────────────────


def _plain_text(markdown_body: str) -> str:
    """Strip markdown to plain text (for llms-full and per-page .txt).

    Fenced code blocks are unwrapped (fences removed, body preserved) so that
    code in transcripts survives into AI-consumable exports. Previously this
    replaced the entire block with a single space, which destroyed the most
    valuable content in coding session transcripts.
    """
    text = markdown_body
    text = re.sub(
        r"```[a-zA-Z0-9_+\-.]*\n?(.*?)```",
        lambda m: m.group(1).rstrip() + "\n",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]*)\*", r"\1", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sha256_16(content: str | bytes) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]


def _page_id(project: str, slug: str) -> str:
    """Stable content-addressable ID for a page. Used in JSON-LD @id and
    cross-reference tables."""
    return f"{project}/{slug}"


def _as_int(value: Any) -> Any:
    """Coerce frontmatter scalars to int where possible; leave other types alone."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s.lstrip("-").isdigit():
            try:
                return int(s)
            except ValueError:
                return value
    return value


def _as_bool(value: Any) -> Any:
    """Coerce frontmatter scalars to bool. Strings like 'false'/'0' map to False.

    Critical because raw YAML-loaded strings like ``"false"`` are truthy in both
    Python and JavaScript, which silently flips downstream boolean checks.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no", ""):
            return False
    return bool(value)


# ─── per-page sibling files (A3 + A4) ────────────────────────────────────


def write_page_txt(page_html_path: Path, markdown_body: str) -> Path:
    """Write a sibling .txt next to <slug>.html."""
    txt_path = page_html_path.with_suffix(".txt")
    txt_path.write_text(_plain_text(markdown_body), encoding="utf-8")
    return txt_path


def write_page_json(
    page_html_path: Path,
    meta: dict[str, Any],
    markdown_body: str,
    wikilinks_out: list[str],
) -> Path:
    """Write a structured JSON sibling next to <slug>.html."""
    data = {
        "id": _page_id(str(meta.get("project", "")), str(meta.get("slug", ""))),
        "slug": meta.get("slug"),
        "title": meta.get("title"),
        "type": meta.get("type"),
        "project": meta.get("project"),
        "date": meta.get("date"),
        "started": meta.get("started"),
        "ended": meta.get("ended"),
        "model": meta.get("model"),
        "cwd": meta.get("cwd"),
        "git_branch": meta.get("gitBranch"),
        "permission_mode": meta.get("permissionMode"),
        "user_messages": _as_int(meta.get("user_messages")),
        "tool_calls": _as_int(meta.get("tool_calls")),
        "tools_used": meta.get("tools_used"),
        "is_subagent": _as_bool(meta.get("is_subagent")),
        "wikilinks_out": sorted(set(wikilinks_out)),
        "body_text": _plain_text(markdown_body),
        "sha256": _sha256_16(markdown_body),
        "source_url": f"sessions/{meta.get('project', '')}/{meta.get('slug', '')}.html",
    }
    # Drop None values so the JSON is clean
    data = {k: v for k, v in data.items() if v is not None}
    json_path = page_html_path.with_suffix(".json")
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return json_path


# ─── llms.txt + llms-full.txt (A1) ───────────────────────────────────────


def write_llms_txt(
    out_dir: Path,
    groups: dict[str, Any],
    total_sessions: int,
) -> Path:
    """Short llms.txt per the llmstxt.org spec.

    Structure:
      # llmwiki
      > one-line description
      ## Projects
      - [Project name](projects/<slug>.html): one-line description
      ## Full content
      - [Flattened plain-text](llms-full.txt)
    """
    lines = [
        "# llmwiki",
        "",
        "> A Karpathy-style LLM Wiki compiled from Claude Code and Codex CLI session transcripts.",
        "",
        f"> Version: llmwiki {__version__} · {total_sessions} sessions across {len(groups)} projects.",
        "",
        "## Home",
        "",
        "- [Home page](index.html): Overview with project cards and living synthesis.",
        "- [All projects](projects/index.html): Browse every project with session counts.",
        "- [All sessions](sessions/index.html): Sortable table of every session.",
        "",
        "## Projects",
        "",
    ]
    for project, sessions in sorted(groups.items()):
        main_count = sum(1 for p, _, _ in sessions if "subagent" not in p.name)
        sub_count = len(sessions) - main_count
        lines.append(
            f"- [{project}](projects/{project}.html): {main_count} main sessions, {sub_count} sub-agent runs."
        )
    lines.extend(
        [
            "",
            "## Full content",
            "",
            "- [Flattened plain-text dump](llms-full.txt): Every wiki page in one file. ~1 token per word, suitable for dropping into an LLM's context.",
            "- [JSON-LD graph](graph.jsonld): Schema.org JSON-LD representation of the wiki's entity/concept/source graph.",
            "- [Sitemap](sitemap.xml): Standard sitemap with lastmod timestamps.",
            "- [RSS feed](rss.xml): Newest sessions first.",
            "",
            "## Machine-readable siblings",
            "",
            "Every HTML page has sibling `.txt` and `.json` files at the same URL:",
            "",
            "- `sessions/<project>/<slug>.html` — human HTML",
            "- `sessions/<project>/<slug>.txt` — plain text of the same content",
            "- `sessions/<project>/<slug>.json` — structured metadata + body",
            "",
            "## AI agent entry point",
            "",
            "- [wiki/ai-readme.md](ai-readme.md): Instructions written specifically for AI agents on how to navigate this wiki.",
            "",
        ]
    )
    out_path = out_dir / "llms.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def write_llms_full_txt(
    out_dir: Path,
    sources: list[tuple[Path, dict[str, Any], str]],
    max_bytes: int = 5 * 1024 * 1024,
) -> Path:
    """Flattened plain-text dump of every page, ordered project → date.

    Caps at max_bytes (default 5 MB) so it stays pasteable into LLM context.
    If the full content exceeds the cap, truncates with a notice.
    """
    lines: list[str] = [
        "llmwiki — full content dump",
        "=" * 60,
        f"llmwiki {__version__}",
        f"Sessions: {len(sources)}",
        "",
    ]
    current_project = None
    for p, meta, body in sorted(
        sources,
        key=lambda t: (str(t[1].get("project", "")), str(t[1].get("started", t[0].name))),
    ):
        project = str(meta.get("project") or p.parent.name)
        if project != current_project:
            current_project = project
            lines.extend(["", f"## Project: {project}", "=" * 60, ""])
        title = str(meta.get("title", meta.get("slug", p.stem)))
        date = str(meta.get("date", ""))
        lines.append(f"### {title}  ({date})")
        lines.append("")
        plain = _plain_text(body)
        # Cap per-session at 2000 chars for the full dump
        if len(plain) > 2000:
            plain = plain[:2000] + f"\n…(truncated, {len(plain) - 2000} more chars — see .txt sibling)"
        lines.append(plain)
        lines.append("")
        # Check running total
        running = sum(len(x) + 1 for x in lines)
        if running > max_bytes:
            lines.append(f"\n…(truncated at {max_bytes} bytes — see sitemap.xml for the full list)")
            break

    out_path = out_dir / "llms-full.txt"
    text = "\n".join(lines)
    out_path.write_text(text[:max_bytes], encoding="utf-8")
    return out_path


# ─── JSON-LD graph (A2) ──────────────────────────────────────────────────


def write_graph_jsonld(
    out_dir: Path,
    groups: dict[str, Any],
    sources: list[tuple[Path, dict[str, Any], str]],
) -> Path:
    """Write schema.org JSON-LD @graph representation."""
    graph: list[dict[str, Any]] = []

    # Top-level CreativeWork for the wiki itself
    graph.append(
        {
            "@id": "llmwiki",
            "@type": "CreativeWork",
            "name": "llmwiki",
            "description": "Karpathy-style LLM Wiki from Claude Code and Codex CLI sessions",
            "creator": {"@type": "Person", "name": "Pratiyush"},
            "license": "https://opensource.org/licenses/MIT",
            "version": __version__,
        }
    )

    # Project nodes
    for project, project_sessions in sorted(groups.items()):
        graph.append(
            {
                "@id": f"project/{project}",
                "@type": "CreativeWork",
                "name": project,
                "isPartOf": {"@id": "llmwiki"},
                "numberOfItems": len(project_sessions),
            }
        )

    # Session nodes
    for p, meta, _body in sources:
        project = str(meta.get("project") or p.parent.name)
        slug = str(meta.get("slug", p.stem))
        node = {
            "@id": f"session/{_page_id(project, slug)}",
            "@type": "CreativeWork",
            "name": meta.get("title") or slug,
            "dateCreated": meta.get("started") or meta.get("date"),
            "isPartOf": {"@id": f"project/{project}"},
            "url": f"sessions/{project}/{slug}.html",
        }
        if meta.get("model"):
            node["creator"] = {"@type": "SoftwareApplication", "name": str(meta["model"])}
        graph.append(node)

    doc = {
        "@context": "https://schema.org",
        "@graph": graph,
    }
    out_path = out_dir / "graph.jsonld"
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


# ─── sitemap.xml (A5) ────────────────────────────────────────────────────


def write_sitemap(
    out_dir: Path,
    groups: dict[str, Any],
    sources: list[tuple[Path, dict[str, Any], str]],
    site_base_url: str = "",
) -> Path:
    """Write a minimal sitemap.xml.

    `site_base_url` is prefixed to every loc — leave empty for relative URLs.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    def url(rel: str, lastmod: str | None = None, priority: str = "0.5") -> str:
        loc = f"{site_base_url.rstrip('/')}/{rel}" if site_base_url else rel
        parts = [f"  <loc>{html.escape(loc)}</loc>"]
        if lastmod:
            parts.append(f"  <lastmod>{html.escape(lastmod)}</lastmod>")
        parts.append(f"  <priority>{priority}</priority>")
        return "<url>\n  " + "\n  ".join(parts) + "\n</url>"

    lines.append(url("index.html", priority="1.0"))
    lines.append(url("projects/index.html", priority="0.9"))
    lines.append(url("sessions/index.html", priority="0.9"))
    for project in sorted(groups.keys()):
        lines.append(url(f"projects/{project}.html", priority="0.8"))
    for p, meta, _ in sources:
        project = str(meta.get("project") or p.parent.name)
        slug = str(meta.get("slug", p.stem))
        started = str(meta.get("started", ""))
        lastmod = started.split("T")[0] if started else None
        lines.append(url(f"sessions/{project}/{slug}.html", lastmod=lastmod, priority="0.6"))
    lines.append("</urlset>")
    out_path = out_dir / "sitemap.xml"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ─── rss.xml (A5) ────────────────────────────────────────────────────────


def write_rss(
    out_dir: Path,
    sources: list[tuple[Path, dict[str, Any], str]],
    site_base_url: str = "",
    limit: int = 50,
) -> Path:
    """Write an RSS 2.0 feed of the newest `limit` sessions."""
    # Sort newest first
    def sort_key(t: tuple[Path, dict[str, Any], str]) -> str:
        return str(t[1].get("started", "")) or str(t[0].name)

    recent = sorted(sources, key=sort_key, reverse=True)[:limit]

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        "  <title>llmwiki</title>",
        f"  <description>Karpathy-style LLM Wiki, newest {limit} sessions</description>",
        f"  <link>{site_base_url or '/'}</link>",
        f"  <generator>llmwiki {__version__}</generator>",
        f"  <lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>",
    ]
    for p, meta, body in recent:
        project = str(meta.get("project") or p.parent.name)
        slug = str(meta.get("slug", p.stem))
        title = str(meta.get("title", slug))
        href_rel = f"sessions/{project}/{slug}.html"
        link = f"{site_base_url.rstrip('/')}/{href_rel}" if site_base_url else href_rel
        summary = _plain_text(body)[:300]
        started = str(meta.get("started", ""))
        pub_date = ""
        if started:
            try:
                dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except Exception:
                pass
        lines.extend(
            [
                "  <item>",
                f"    <title>{html.escape(title)}</title>",
                f"    <link>{html.escape(link)}</link>",
                f"    <guid isPermaLink=\"false\">{html.escape(_page_id(project, slug))}</guid>",
                f"    <description>{html.escape(summary)}</description>",
            ]
        )
        if pub_date:
            lines.append(f"    <pubDate>{pub_date}</pubDate>")
        lines.append("  </item>")

    lines.append("</channel>")
    lines.append("</rss>")
    out_path = out_dir / "rss.xml"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ─── robots.txt (A6) ─────────────────────────────────────────────────────


def write_robots_txt(out_dir: Path) -> Path:
    content = """User-agent: *
Allow: /

Sitemap: /sitemap.xml

# AI-agent friendly entry points (https://llmstxt.org)
# See /llms.txt for the machine-readable index
# See /llms-full.txt for the flattened content dump
# See /graph.jsonld for the schema.org JSON-LD graph
"""
    out_path = out_dir / "robots.txt"
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ─── ai-readme.md (A14) ──────────────────────────────────────────────────


def write_ai_readme(
    out_dir: Path,
    groups: dict[str, Any],
    total_sessions: int,
) -> Path:
    """Generate wiki/ai-readme.md — AI-specific entry point."""
    content = f"""# This wiki, explained for AI agents

You are reading an **llmwiki** — a Karpathy-style LLM Wiki compiled from
Claude Code and Codex CLI session transcripts. If you are an AI agent
trying to answer a question about the user's past work, here is how to
navigate this wiki efficiently.

## Stats

- **llmwiki version**: {__version__}
- **Total sessions**: {total_sessions}
- **Total projects**: {len(groups)}

## Machine-readable entry points

You probably want one of these, not the HTML:

| Format | URL | Use when |
|---|---|---|
| **llms.txt** | `/llms.txt` | You want the catalog + links to each project |
| **llms-full.txt** | `/llms-full.txt` | You want the flattened content dump to paste into your context (~5 MB cap) |
| **graph.jsonld** | `/graph.jsonld` | You want the schema.org entity/concept/source graph |
| **sitemap.xml** | `/sitemap.xml` | You want every page's URL + last-modified |
| **rss.xml** | `/rss.xml` | You want the 50 newest sessions |

Every HTML page has sibling `.txt` and `.json` files at the same URL:

- `sessions/<project>/<slug>.html` — human-readable HTML
- `sessions/<project>/<slug>.txt` — plain text of the same content
- `sessions/<project>/<slug>.json` — structured metadata + body

Prefer the `.json` siblings for structured queries, the `.txt` siblings
for content, and the HTML only when you need the rendered view.

## Navigation structure

The wiki follows Karpathy's 3-layer pattern:

1. **Raw layer** (`raw/sessions/<project>/*.md`) — immutable session
   transcripts. Each has YAML frontmatter with `project`, `slug`, `date`,
   `started`, `ended`, `model`, `tools_used`, `gitBranch`, `cwd`, etc.
2. **Wiki layer** (`wiki/`) — LLM-maintained pages
   - `sources/` — one summary per raw source
   - `entities/` — people, companies, projects, tools (TitleCase)
   - `concepts/` — ideas, patterns, frameworks (TitleCase)
   - `syntheses/` — saved query answers
   - `comparisons/` — side-by-side diffs
   - `questions/` — first-class open questions
3. **Site layer** (`site/` or `https://...`) — generated static HTML

## Cross-linking

All pages link to each other via `[[wikilink]]` syntax. The JSON-LD graph
exposes the full entity/concept/source relation graph. The per-page
`.json` sibling includes `wikilinks_out` with every outbound link.

## Querying via MCP

If you have MCP access, the llmwiki MCP server exposes 7 tools
(v0.4 adds `wiki_export`):

- `wiki_query(question, max_pages)` — keyword search + page content
- `wiki_search(term, include_raw)` — raw grep
- `wiki_list_sources(project)` — list sources with metadata
- `wiki_read_page(path)` — read one page
- `wiki_lint()` — orphans + broken wikilinks report
- `wiki_sync(dry_run)` — trigger the converter
- `wiki_export(format)` — export the whole wiki in a named format

## Projects

{chr(10).join(f"- **{project}** ({len(sessions)} sessions)" for project, sessions in sorted(groups.items()))}

## How this wiki was built

Every session in `raw/` was converted from a `.jsonl` transcript by an
agent-specific adapter (Claude Code, Codex CLI, Cursor, Obsidian,
Gemini CLI, or PDF). The converter runs redaction on username, API keys,
tokens, and emails before anything hits disk. The wiki layer was then
compiled by an LLM (the user's coding agent) following the workflows in
`CLAUDE.md` and `AGENTS.md`.

No embeddings, no RAG, no database. Everything is plain markdown under
`wiki/` and plain HTML/JSON/TXT under `site/`.
"""
    out_path = out_dir / "ai-readme.md"
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ─── marp slides ────────────────────────────────────────────────────────


def write_marp(
    out_dir: Path,
    sources: list[tuple[Path, dict[str, Any], str]],
    *,
    topic: str = "",
    max_slides: int = 30,
) -> Path:
    """Generate a Marp-compatible slide deck from wiki sources.

    Each source becomes 1-2 slides (title + key claims).
    The output is standard Marp markdown that renders with
    ``marp --html deck.md`` or the VS Code Marp extension.
    """
    lines = [
        "---",
        "marp: true",
        "theme: default",
        "paginate: true",
        f"title: llmwiki — {topic or 'Knowledge Overview'}",
        "---",
        "",
        f"# {topic or 'Knowledge Overview'}",
        "",
        f"*Generated from {len(sources)} wiki sources*",
        "",
    ]

    slide_count = 1
    for _, meta, body in sources:
        if slide_count >= max_slides:
            break

        title = meta.get("title", "Untitled")
        if topic and topic.lower() not in title.lower() and topic.lower() not in body.lower():
            continue

        # Extract key claims from body
        claims: list[str] = []
        in_claims = False
        for line in body.splitlines():
            if line.strip().startswith("## Key Claims") or line.strip().startswith("## Key Facts"):
                in_claims = True
                continue
            if in_claims and line.startswith("## "):
                break
            if in_claims and line.strip().startswith("- "):
                claims.append(line.strip())

        if not claims:
            # Fallback: first 3 non-empty body lines
            for line in body.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                    claims.append(f"- {stripped}")
                    if len(claims) >= 3:
                        break

        lines.append("---")
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        for c in claims[:5]:
            lines.append(c)
        lines.append("")
        slide_count += 1

    # Final slide
    lines.append("---")
    lines.append("")
    lines.append("## Thank You")
    lines.append("")
    lines.append(f"*{slide_count} slides from llmwiki*")
    lines.append("")

    out_path = out_dir / "deck.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ─── orchestration ──────────────────────────────────────────────────────


def export_all(
    out_dir: Path,
    groups: dict[str, Any],
    sources: list[tuple[Path, dict[str, Any], str]],
    site_base_url: str = "",
) -> dict[str, Path]:
    """Write every AI-consumable export format into `out_dir`.

    Returns a dict {format_name: output_path}.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    total_sessions = len(sources)

    paths["llms.txt"] = write_llms_txt(out_dir, groups, total_sessions)
    paths["llms-full.txt"] = write_llms_full_txt(out_dir, sources)
    paths["graph.jsonld"] = write_graph_jsonld(out_dir, groups, sources)
    paths["sitemap.xml"] = write_sitemap(out_dir, groups, sources, site_base_url)
    paths["rss.xml"] = write_rss(out_dir, sources, site_base_url)
    paths["robots.txt"] = write_robots_txt(out_dir)
    paths["ai-readme.md"] = write_ai_readme(out_dir, groups, total_sessions)

    return paths
