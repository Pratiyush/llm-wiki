"""Static prototype hub (#114).

Publishes a `site/prototypes/` directory linked from the main nav that
contains review-ready HTML states for UX iteration **before** larger
UI changes touch the live templates.

Six states ship today:

- ``page-shell`` — skeleton with nav, footer, no content (layout audit)
- ``article-anatomy`` — annotated session page showing every slot
- ``drawer-browse`` — the project-browse drawer open, with faceted list
- ``search-results`` — command-palette mid-query with 10+ results
- ``empty-search`` — "nothing matches" state
- ``references-rail`` — article with the right-hand `## Connections` rail

Each state is a single static HTML file that inherits the site's CSS
palette + typography (via the same `llmwiki/render/css.py` tokens the
live site uses), so visual fidelity matches 1:1.

Public API
----------
- :data:`PROTOTYPE_STATES` — ordered list of (slug, title, description)
- :func:`build_prototype_hub` — write `site/prototypes/*.html` + index
- :func:`prototype_nav_link` — the link the main nav embeds (optional)

Design notes
------------
- **Stdlib + the existing CSS only.** No Storybook, no JS framework —
  this ships as part of the static build.
- **Every state is independent.** You can open any one file directly;
  no shared runtime state across prototypes.
- **Accent stripe identifies prototypes.** Every page carries a 4 px
  `#7C3AED` top stripe so reviewers never confuse a prototype with a
  real page.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ─── States ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PrototypeState:
    """One reviewable UI state that `site/prototypes/` ships."""

    slug: str         # URL slug: "page-shell"
    title: str        # display name: "Page shell"
    description: str  # what the reviewer is looking at


PROTOTYPE_STATES: tuple[PrototypeState, ...] = (
    PrototypeState(
        slug="page-shell",
        title="Page shell",
        description="Empty layout with nav + footer + breadcrumb. "
                    "Use to audit spacing, header heights, and mobile breakpoints.",
    ),
    PrototypeState(
        slug="article-anatomy",
        title="Article anatomy",
        description="Annotated session page showing every slot a session renders "
                    "(frontmatter, summary, transcript, connections, related). "
                    "Orange callouts mark the landmarks.",
    ),
    PrototypeState(
        slug="drawer-browse",
        title="Drawer — browse",
        description="Project-browse drawer in its open state with faceted list "
                    "(by project, entity_type, lifecycle, cache_tier).",
    ),
    PrototypeState(
        slug="search-results",
        title="Search — mid-query",
        description="Command palette with 10+ results: title match, heading "
                    "match, and body-only match classes all represented.",
    ),
    PrototypeState(
        slug="empty-search",
        title="Search — no matches",
        description="Empty state when the query matches nothing. Reviews the "
                    "fallback copy and the escape hatches we offer.",
    ),
    PrototypeState(
        slug="references-rail",
        title="References rail",
        description="Article with the right-hand `## Connections` rail "
                    "populated — inbound + outbound wikilinks + related pages.",
    ),
)


# ─── Output directory helpers ──────────────────────────────────────────


PROTOTYPES_DIRNAME = "prototypes"


def prototypes_dir(site_dir: Path) -> Path:
    """Return ``site/prototypes/``."""
    return site_dir / PROTOTYPES_DIRNAME


def prototype_nav_link() -> tuple[str, str]:
    """Return ``(href, label)`` for the main nav."""
    return f"{PROTOTYPES_DIRNAME}/index.html", "Prototypes"


# ─── Rendering ─────────────────────────────────────────────────────────


_BASE_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — llmwiki prototypes</title>
<link rel="stylesheet" href="../style.css">
<style>
  /* Identification stripe so reviewers never confuse these with real pages. */
  .proto-stripe {{ height: 4px; background: #7C3AED; }}
  .proto-frame {{
    max-width: 960px; margin: 0 auto; padding: 48px 24px;
  }}
  .proto-meta {{
    background: var(--bg-alt); border: 1px solid var(--border-subtle);
    border-radius: 8px; padding: 16px; margin-bottom: 32px;
    font-size: 0.85rem; color: var(--text-secondary);
  }}
  .proto-meta h1 {{
    font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em;
    color: var(--text-muted); margin: 0 0 4px 0;
  }}
  .proto-meta p {{ margin: 0; }}
  .proto-callout {{
    background: #fff7ed; border-left: 3px solid #f59e0b;
    padding: 8px 12px; margin: 12px 0; font-size: 0.85rem;
    color: #78350f;
  }}
  :root[data-theme="dark"] .proto-callout {{
    background: #2a1b0a; color: #fde68a;
  }}
</style>
</head>
<body>
<div class="proto-stripe" aria-hidden="true"></div>
<main class="proto-frame">
"""

_BASE_FOOT = """\
</main>
</body>
</html>
"""


def _meta_block(state: PrototypeState) -> str:
    return (
        '<div class="proto-meta">'
        '<h1>Prototype — not a live page</h1>'
        f'<p><b>{html.escape(state.title)}</b> · {html.escape(state.description)}</p>'
        '</div>'
    )


def _render_page_shell(state: PrototypeState) -> str:
    body = """
<header style="border-bottom: 1px solid var(--border-subtle); padding: 16px 0; margin-bottom: 32px;">
  <nav><strong>llmwiki</strong> · <a href="#">Home</a> · <a href="#">Projects</a> · <a href="#">Sessions</a></nav>
</header>
<article>
  <h1 style="font-size: 2rem; margin-bottom: 12px;">Page shell</h1>
  <p style="color: var(--text-muted);">breadcrumb → placeholder → breadcrumb</p>
  <div style="height: 400px; border: 2px dashed var(--border); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); margin: 32px 0;">
    content slot
  </div>
</article>
<footer style="border-top: 1px solid var(--border-subtle); padding-top: 16px; color: var(--text-muted); font-size: 0.85rem;">
  generated locally · built with llmwiki
</footer>
"""
    return body


def _render_article_anatomy(state: PrototypeState) -> str:
    body = """
<article>
  <div class="proto-callout">Slot 1 — <b>frontmatter &amp; breadcrumbs</b></div>
  <nav style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 8px;">
    Home / Projects / <b>demo-blog-engine</b>
  </nav>
  <h1 style="font-size: 2rem;">Session: Ship a Rust blog engine</h1>
  <p style="color: var(--text-muted); font-size: 0.85rem;">2026-04-12 · claude-sonnet-4-6 · 12 user messages · 34 tool calls</p>

  <div class="proto-callout">Slot 2 — <b>summary</b></div>
  <h2>Summary</h2>
  <p>A 2–4 sentence synthesis of what the session accomplished.</p>

  <div class="proto-callout">Slot 3 — <b>transcript body (collapsible tool outputs)</b></div>
  <h2>Conversation</h2>
  <p>Turn 1 — User · Turn 1 — Assistant · …</p>

  <div class="proto-callout">Slot 4 — <b>connections / wikilinks</b></div>
  <h2>Connections</h2>
  <ul><li>[[Rust]]</li><li>[[StaticSiteGeneration]]</li></ul>

  <div class="proto-callout">Slot 5 — <b>related pages rail</b></div>
  <h2>Related</h2>
  <p>Three cards with 0.6+ similarity score…</p>
</article>
"""
    return body


def _render_drawer_browse(state: PrototypeState) -> str:
    body = """
<div style="display: grid; grid-template-columns: 280px 1fr; gap: 24px;">
  <aside style="background: var(--bg-alt); border-radius: 8px; padding: 16px;">
    <h2 style="font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted);">Browse</h2>
    <ul style="list-style: none; padding: 0; margin: 12px 0;">
      <li>▸ By project <span style="color: var(--text-muted);">(30)</span></li>
      <li>▸ By entity_type <span style="color: var(--text-muted);">(7)</span></li>
      <li>▸ By lifecycle <span style="color: var(--text-muted);">(5)</span></li>
      <li>▸ By cache_tier <span style="color: var(--text-muted);">(4)</span></li>
    </ul>
    <h2 style="font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted);">Projects</h2>
    <ul style="list-style: none; padding: 0; font-family: var(--mono); font-size: 0.82rem;">
      <li>llm-wiki <span style="color: var(--text-muted);">6</span></li>
      <li>germanly <span style="color: var(--text-muted);">61</span></li>
      <li>enigma <span style="color: var(--text-muted);">26</span></li>
      <li>research <span style="color: var(--text-muted);">93</span></li>
    </ul>
  </aside>
  <section>
    <h1>Projects</h1>
    <p style="color: var(--text-muted);">30 total · tap a facet to narrow</p>
  </section>
</div>
"""
    return body


def _render_search_results(state: PrototypeState) -> str:
    body = """
<div style="max-width: 640px; margin: 0 auto;">
  <input type="search" placeholder="Search wiki…" value="karpathy"
         style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 1rem;">
  <p style="color: var(--text-muted); font-size: 0.85rem; margin-top: 8px;">12 results · mode: <b>flat</b></p>
  <ul style="list-style: none; padding: 0; margin-top: 16px;">
    <li style="padding: 12px 0; border-bottom: 1px solid var(--border-subtle);">
      <h3 style="margin: 0;">Andrej Karpathy <span style="color: var(--text-muted); font-size: 0.78rem;">entity</span></h3>
      <p style="color: var(--text-muted); font-size: 0.85rem; margin: 4px 0 0;">Researcher behind the original llm-wiki gist…</p>
    </li>
    <li style="padding: 12px 0; border-bottom: 1px solid var(--border-subtle);">
      <h3 style="margin: 0;">Session: Ship the LLM Wiki seed <span style="color: var(--text-muted); font-size: 0.78rem;">source</span></h3>
      <p style="color: var(--text-muted); font-size: 0.85rem; margin: 4px 0 0;">Karpathy's pattern spells out what a wiki should do…</p>
    </li>
    <li style="padding: 12px 0; border-bottom: 1px solid var(--border-subtle);">
      <h3 style="margin: 0;">#Karpathy <span style="color: var(--text-muted); font-size: 0.78rem;">tag · 18 sessions</span></h3>
    </li>
  </ul>
</div>
"""
    return body


def _render_empty_search(state: PrototypeState) -> str:
    body = """
<div style="max-width: 640px; margin: 0 auto; text-align: center; padding: 48px 0;">
  <input type="search" placeholder="Search wiki…" value="lorem ipsum"
         style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 1rem;">
  <div style="font-size: 3rem; margin: 32px 0 8px;">🔍</div>
  <h2>No matches</h2>
  <p style="color: var(--text-muted);">
    Nothing matches <b>lorem ipsum</b>. Try:
  </p>
  <ul style="list-style: none; padding: 0; margin: 16px 0; color: var(--text-muted);">
    <li>• Fewer words (llmwiki is best at 1–3 keyword queries)</li>
    <li>• A broader tag — <a href="#">#karpathy</a>, <a href="#">#rust</a>, <a href="#">#ollama</a></li>
    <li>• The <a href="#">knowledge graph</a> to browse visually</li>
  </ul>
</div>
"""
    return body


def _render_references_rail(state: PrototypeState) -> str:
    body = """
<div style="display: grid; grid-template-columns: 1fr 280px; gap: 32px;">
  <article>
    <h1>Session: Seed the llm-wiki repo</h1>
    <p style="color: var(--text-muted); font-size: 0.85rem;">2026-04-16 · claude-sonnet-4-6</p>
    <h2>Summary</h2>
    <p>First session kicking off the karpathy-style wiki. See the right rail for connections.</p>
    <h2>Key claims</h2>
    <ul>
      <li>Raw layer is immutable — never edit <code>raw/</code>.</li>
      <li>Every page has a <b>Connections</b> block.</li>
    </ul>
  </article>
  <aside style="position: sticky; top: 24px; align-self: start; background: var(--bg-alt); border-radius: 8px; padding: 16px;">
    <h2 style="font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted);">Connections</h2>
    <h3 style="font-size: 0.78rem; color: var(--text-muted); margin-top: 12px;">Outbound · 4</h3>
    <ul style="list-style: none; padding: 0; margin: 6px 0;">
      <li>→ <a href="#">Karpathy</a></li>
      <li>→ <a href="#">LLMWiki</a></li>
      <li>→ <a href="#">ObsidianVault</a></li>
    </ul>
    <h3 style="font-size: 0.78rem; color: var(--text-muted); margin-top: 12px;">Inbound · 2</h3>
    <ul style="list-style: none; padding: 0; margin: 6px 0;">
      <li>← <a href="#">Session: v1.0 refactor</a></li>
      <li>← <a href="#">LLM Wiki (entity)</a></li>
    </ul>
    <h3 style="font-size: 0.78rem; color: var(--text-muted); margin-top: 12px;">Related · 3</h3>
    <ul style="list-style: none; padding: 0; margin: 6px 0; font-size: 0.82rem;">
      <li>Session: v1.1 rc2</li>
      <li>Session: graph viewer</li>
      <li>Session: cache tiers</li>
    </ul>
  </aside>
</div>
"""
    return body


_RENDERERS = {
    "page-shell": _render_page_shell,
    "article-anatomy": _render_article_anatomy,
    "drawer-browse": _render_drawer_browse,
    "search-results": _render_search_results,
    "empty-search": _render_empty_search,
    "references-rail": _render_references_rail,
}


def render_state(state: PrototypeState) -> str:
    """Render one prototype state to a full HTML document."""
    renderer = _RENDERERS[state.slug]
    body = renderer(state)
    head = _BASE_HEAD.format(title=html.escape(state.title))
    return head + _meta_block(state) + body + _BASE_FOOT


def render_hub_index(states: tuple[PrototypeState, ...] = PROTOTYPE_STATES) -> str:
    """Render the `site/prototypes/index.html` landing page."""
    cards = "\n".join(
        f'''  <a href="{html.escape(s.slug)}.html" class="proto-card">
    <h2>{html.escape(s.title)}</h2>
    <p>{html.escape(s.description)}</p>
  </a>'''
        for s in states
    )
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prototypes — llmwiki</title>
<link rel="stylesheet" href="../style.css">
<style>
  .proto-stripe {{ height: 4px; background: #7C3AED; }}
  .proto-hub {{ max-width: 960px; margin: 0 auto; padding: 48px 24px; }}
  .proto-hub h1 {{ font-size: 2rem; margin-bottom: 8px; }}
  .proto-hub p.lede {{ color: var(--text-muted); margin-bottom: 32px; }}
  .proto-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
  .proto-card {{
    display: block; padding: 16px; background: var(--bg-card);
    border: 1px solid var(--border-subtle); border-radius: 8px;
    color: var(--text); text-decoration: none; box-shadow: var(--shadow-card);
    transition: all 0.15s;
  }}
  .proto-card:hover {{ border-color: var(--accent); transform: translateY(-1px); box-shadow: var(--shadow-card-hover); }}
  .proto-card h2 {{ font-size: 1rem; margin: 0 0 6px 0; }}
  .proto-card p {{ font-size: 0.85rem; color: var(--text-muted); margin: 0; }}
</style>
</head>
<body>
<div class="proto-stripe" aria-hidden="true"></div>
<main class="proto-hub">
  <p><a href="../index.html">← Back to site</a></p>
  <h1>Prototypes</h1>
  <p class="lede">
    Six reviewable UI states. Iterate on layouts here before touching the live templates.
    Every card below is a single static HTML file sharing the site's CSS.
  </p>
  <div class="proto-grid">
{cards}
  </div>
</main>
</body>
</html>
"""


def build_prototype_hub(
    site_dir: Path,
    *,
    states: tuple[PrototypeState, ...] = PROTOTYPE_STATES,
) -> Path:
    """Write every state + the hub index into ``site/prototypes/``.

    Returns the hub index path. Raises ``FileNotFoundError`` if the caller
    hasn't created ``site_dir`` yet.
    """
    if not site_dir.is_dir():
        raise FileNotFoundError(
            f"site_dir {site_dir} does not exist — run `llmwiki build` first"
        )
    out = prototypes_dir(site_dir)
    out.mkdir(parents=True, exist_ok=True)

    for state in states:
        (out / f"{state.slug}.html").write_text(
            render_state(state), encoding="utf-8"
        )

    index = out / "index.html"
    index.write_text(render_hub_index(states), encoding="utf-8")
    return index
