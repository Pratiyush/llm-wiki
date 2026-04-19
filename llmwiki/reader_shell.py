"""Reader-first article shell — Wikipedia-style page layout (v1.2.0 · #112).

Today's session pages render as transcripts: frontmatter → summary →
conversation → connections. It works, but reading feels like watching
replay footage of a commit log.

The "reader shell" wraps the same content in a **Wikipedia-style
encyclopedia layout** so pages feel like articles someone wrote, not
logs someone dumped:

    ┌─────────────────────────────────────────────────────────┐
    │ Browse drawer  │  Article header + utility bar         │
    │  (nav pane)    ├────────────────────┬───────────────────┤
    │                │  Article body       │  Infobox        │
    │                │                     │  (metadata)     │
    │                │                     ├───────────────── │
    │                │                     │  Revisions      │
    │                │                     ├───────────────── │
    │                │                     │  See also       │
    │                │                     ├───────────────── │
    │                │                     │  References     │
    └────────────────┴─────────────────────┴─────────────────┘

**Fully opt-in.** Pages without ``reader_shell: true`` in frontmatter
render through the existing pipeline unchanged — this ships as a layer,
not a rewrite.

Public API
----------
- :data:`SHELL_FLAG_FIELD` — frontmatter key that flips rendering
- :class:`ShellSlots` — dataclass collecting every slot's content
- :func:`render_article_shell` — emits the complete shell HTML
- :func:`extract_infobox_fields` — pulls metadata from frontmatter
- :func:`is_reader_shell_enabled` — check the frontmatter flag
- :func:`ReaderShellCSS` — CSS class names (kept in Python so tests
  can reference them without parsing the stylesheet)

Design notes
------------
- **Stdlib only.** No template engine — f-strings + ``html.escape``.
- **Every slot is optional.** `render_article_shell` accepts empty
  ShellSlots; missing sections just don't render. No empty chrome.
- **CSS lives separately.** The inline stylesheet lands in
  ``llmwiki/render/css.py`` under a ``.reader-shell`` namespace so it
  doesn't leak into non-reader pages.
- **XSS-safe.** Body HTML is assumed trusted (comes from the build
  pipeline). Everything pulled out of frontmatter is HTML-escaped.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

# ─── Constants ─────────────────────────────────────────────────────────

#: Frontmatter key that opts a page into the reader shell.
SHELL_FLAG_FIELD = "reader_shell"

#: Keys we automatically surface in the infobox (right-hand metadata
#: column). Unknown keys are ignored.
INFOBOX_FIELDS_IN_ORDER: tuple[str, ...] = (
    "type",
    "entity_type",
    "project",
    "model",
    "lifecycle",
    "cache_tier",
    "confidence",
    "last_updated",
    "date",
)

#: Human labels for the infobox keys. Unknown keys fall back to
#: title-cased + underscore-stripped.
INFOBOX_FIELD_LABELS: dict[str, str] = {
    "type": "Type",
    "entity_type": "Entity type",
    "project": "Project",
    "model": "Model",
    "lifecycle": "Lifecycle",
    "cache_tier": "Cache tier",
    "confidence": "Confidence",
    "last_updated": "Last updated",
    "date": "Date",
}


class ReaderShellCSS:
    """CSS class names used by the shell. Kept as a class so tests +
    external CSS callers have a single source of truth to reference.
    """

    WRAP = "reader-shell"
    DRAWER = "reader-shell__drawer"
    MAIN = "reader-shell__main"
    HEADER = "reader-shell__header"
    UTILITY = "reader-shell__utility"
    BODY = "reader-shell__body"
    INFOBOX = "reader-shell__infobox"
    INFOBOX_ROW = "reader-shell__infobox-row"
    REVISIONS = "reader-shell__revisions"
    SEEALSO = "reader-shell__see-also"
    REFERENCES = "reader-shell__references"


# ─── Opt-in detection ──────────────────────────────────────────────────


def is_reader_shell_enabled(meta: Mapping[str, Any]) -> bool:
    """True iff the page's frontmatter has ``reader_shell: true``
    (case-insensitive, accepts ``"true"`` / ``"yes"`` / ``1``)."""
    raw = meta.get(SHELL_FLAG_FIELD)
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    value = str(raw).strip().lower()
    return value in {"true", "yes", "on", "1"}


# ─── Slot model ────────────────────────────────────────────────────────


@dataclass
class ShellSlots:
    """Everything the shell renders. All fields optional; empty ones
    collapse so pages with no references / no revisions don't grow
    empty chrome.
    """

    title: str = ""
    subtitle: str = ""              # one-line tagline below the h1
    breadcrumbs: list[tuple[str, str]] = field(default_factory=list)
    # ``(label, href)`` pairs; href="" means "current page, unlinked"

    body_html: str = ""             # trusted HTML from the build pipeline

    infobox: dict[str, str] = field(default_factory=dict)
    # {label: value} — already human-formatted, will be HTML-escaped

    drawer_links: list[tuple[str, str]] = field(default_factory=list)
    # Navigation pane; (label, href) pairs

    revisions: list[tuple[str, str]] = field(default_factory=list)
    # (date, summary) pairs shown in the "Revisions" rail

    see_also: list[tuple[str, str]] = field(default_factory=list)
    # (label, href) pairs pulled from ``## Connections`` or ``## Related``

    references: list[tuple[str, str]] = field(default_factory=list)
    # (label, href) pairs pulled from ``## Sources`` or ``## References``

    utility_actions: list[tuple[str, str]] = field(default_factory=list)
    # (label, href-or-js) pairs for the utility bar (copy-md, download)


# ─── Infobox field extraction ─────────────────────────────────────────


def _format_value(value: Any) -> str:
    """Render a frontmatter value as a compact human string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        # Confidence scores are floats 0–1; format to two places.
        if isinstance(value, float) and 0 <= value <= 1:
            return f"{value:.2f}"
        return str(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v)
    return str(value)


def _label_for(key: str) -> str:
    """Return a human label for an infobox key."""
    if key in INFOBOX_FIELD_LABELS:
        return INFOBOX_FIELD_LABELS[key]
    return key.replace("_", " ").strip().title()


def extract_infobox_fields(meta: Mapping[str, Any]) -> dict[str, str]:
    """Pull known fields from ``meta`` into the infobox in canonical
    order, dropping empty values and formatting the rest compactly.

    Consumers should pass the result straight to ``ShellSlots.infobox``.
    """
    out: dict[str, str] = {}
    for key in INFOBOX_FIELDS_IN_ORDER:
        if key not in meta:
            continue
        formatted = _format_value(meta[key])
        if not formatted:
            continue
        out[_label_for(key)] = formatted
    return out


# ─── Rendering ─────────────────────────────────────────────────────────


def _render_breadcrumbs(items: list[tuple[str, str]]) -> str:
    if not items:
        return ""
    parts: list[str] = []
    for i, (label, href) in enumerate(items):
        safe_label = html.escape(label)
        if href and i < len(items) - 1:
            parts.append(f'<a href="{html.escape(href)}">{safe_label}</a>')
        else:
            parts.append(f'<span aria-current="page">{safe_label}</span>')
    sep = '<span class="sep" aria-hidden="true"> / </span>'
    return f'<nav class="reader-shell__crumbs" aria-label="Breadcrumb">{sep.join(parts)}</nav>'


def _render_infobox(fields: dict[str, str]) -> str:
    if not fields:
        return ""
    rows = "\n".join(
        f'  <div class="{ReaderShellCSS.INFOBOX_ROW}">'
        f'<dt>{html.escape(label)}</dt>'
        f'<dd>{html.escape(value)}</dd></div>'
        for label, value in fields.items()
    )
    return f'<aside class="{ReaderShellCSS.INFOBOX}" aria-label="Metadata"><dl>\n{rows}\n</dl></aside>'


def _render_link_list(
    items: list[tuple[str, str]],
    *,
    css_class: str,
    title: str,
) -> str:
    if not items:
        return ""
    rows = "\n".join(
        f'  <li><a href="{html.escape(href)}">{html.escape(label)}</a></li>'
        if href else
        f'  <li>{html.escape(label)}</li>'
        for label, href in items
    )
    safe_title = html.escape(title)
    return (
        f'<section class="{css_class}" aria-label="{safe_title}">'
        f'<h2>{safe_title}</h2><ul>\n{rows}\n</ul></section>'
    )


def _render_revisions(items: list[tuple[str, str]]) -> str:
    if not items:
        return ""
    rows = "\n".join(
        f'  <li><time>{html.escape(date)}</time> — {html.escape(summary)}</li>'
        for date, summary in items
    )
    return (
        f'<section class="{ReaderShellCSS.REVISIONS}" aria-label="Revision history">'
        f'<h2>Revisions</h2><ul>\n{rows}\n</ul></section>'
    )


def _render_utility_bar(actions: list[tuple[str, str]]) -> str:
    if not actions:
        return ""
    buttons = "\n".join(
        f'  <a href="{html.escape(href)}" class="reader-shell__util-btn">{html.escape(label)}</a>'
        for label, href in actions
    )
    return (
        f'<div class="{ReaderShellCSS.UTILITY}" role="toolbar" aria-label="Page actions">\n'
        f'{buttons}\n</div>'
    )


def _render_drawer(links: list[tuple[str, str]]) -> str:
    # The drawer is always rendered (even empty) so the layout stays
    # consistent — we just show a placeholder message if no links exist.
    if not links:
        content = (
            '<p class="reader-shell__drawer-empty">'
            'No browse entries configured. Set <code>drawer_links</code> '
            'in the page\u2019s frontmatter.</p>'
        )
    else:
        content = "<ul>\n" + "\n".join(
            f'  <li><a href="{html.escape(href)}">{html.escape(label)}</a></li>'
            for label, href in links
        ) + "\n</ul>"
    return (
        f'<aside class="{ReaderShellCSS.DRAWER}" aria-label="Browse">'
        f'<h2>Browse</h2>{content}</aside>'
    )


def render_article_shell(slots: ShellSlots) -> str:
    """Render the complete reader shell as an HTML string.

    The output is a single ``<div class="reader-shell">`` block that
    the build pipeline wraps its existing page template around — the
    shell doesn't need to emit ``<html>`` / ``<head>`` itself, only
    the structured article layout.
    """
    title_html = (
        f'<h1>{html.escape(slots.title)}</h1>'
        if slots.title
        else ""
    )
    subtitle_html = (
        f'<p class="reader-shell__subtitle">{html.escape(slots.subtitle)}</p>'
        if slots.subtitle
        else ""
    )

    header = (
        f'<header class="{ReaderShellCSS.HEADER}">'
        f'{_render_breadcrumbs(slots.breadcrumbs)}'
        f'{title_html}'
        f'{subtitle_html}'
        f'{_render_utility_bar(slots.utility_actions)}'
        "</header>"
    )

    drawer = _render_drawer(slots.drawer_links)
    infobox = _render_infobox(slots.infobox)
    revisions = _render_revisions(slots.revisions)
    see_also = _render_link_list(
        slots.see_also,
        css_class=ReaderShellCSS.SEEALSO,
        title="See also",
    )
    references = _render_link_list(
        slots.references,
        css_class=ReaderShellCSS.REFERENCES,
        title="References",
    )

    # Right column collects infobox + revisions + see-also + references.
    # Empty sections collapse cleanly.
    right_column = "".join(filter(None, [
        infobox,
        revisions,
        see_also,
        references,
    ]))

    body = (
        f'<main class="{ReaderShellCSS.MAIN}">'
        f'{header}'
        f'<div class="{ReaderShellCSS.BODY}">{slots.body_html}</div>'
        "</main>"
    )

    right = (
        f'<aside class="reader-shell__rail" aria-label="Page rail">{right_column}</aside>'
        if right_column else ""
    )

    return (
        f'<div class="{ReaderShellCSS.WRAP}">'
        f'{drawer}'
        f'{body}'
        f'{right}'
        "</div>"
    )


# ─── Convenience wrapper: build slots from raw inputs ─────────────────


def build_slots(
    *,
    title: str,
    body_html: str,
    meta: Mapping[str, Any],
    breadcrumbs: Optional[list[tuple[str, str]]] = None,
    see_also: Optional[list[tuple[str, str]]] = None,
    references: Optional[list[tuple[str, str]]] = None,
    revisions: Optional[list[tuple[str, str]]] = None,
    drawer_links: Optional[list[tuple[str, str]]] = None,
    utility_actions: Optional[list[tuple[str, str]]] = None,
    subtitle: str = "",
) -> ShellSlots:
    """One-call factory: auto-extract the infobox from ``meta``, copy
    through the caller-supplied lists (or default to empty)."""
    return ShellSlots(
        title=title,
        subtitle=subtitle,
        body_html=body_html,
        infobox=extract_infobox_fields(meta),
        breadcrumbs=list(breadcrumbs or []),
        see_also=list(see_also or []),
        references=list(references or []),
        revisions=list(revisions or []),
        drawer_links=list(drawer_links or []),
        utility_actions=list(utility_actions or []),
    )


# ─── CSS block (importable from build.py / render/css.py) ─────────────


READER_SHELL_CSS = """\
/* --- Reader shell (v1.2.0 · #112) --- */
.reader-shell {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 280px;
  gap: 32px;
  max-width: 1440px;
  margin: 0 auto;
  padding: 32px 24px;
  align-items: start;
}
.reader-shell__drawer,
.reader-shell__rail {
  position: sticky;
  top: 24px;
  align-self: start;
  background: var(--bg-alt);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px;
  font-size: 0.85rem;
}
.reader-shell__drawer h2,
.reader-shell__rail h2 {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin: 0 0 10px 0;
}
.reader-shell__drawer ul,
.reader-shell__rail ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.reader-shell__drawer li,
.reader-shell__rail li { padding: 4px 0; }

.reader-shell__drawer-empty {
  color: var(--text-muted);
  font-size: 0.78rem;
  margin: 0;
}

.reader-shell__header {
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 16px;
  margin-bottom: 24px;
}
.reader-shell__crumbs {
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.reader-shell__crumbs .sep { margin: 0 6px; }
.reader-shell__subtitle {
  color: var(--text-muted);
  margin-top: 4px;
}

.reader-shell__utility {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.reader-shell__util-btn {
  padding: 4px 10px;
  font-size: 0.78rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-secondary);
  text-decoration: none;
  transition: border-color 0.15s;
}
.reader-shell__util-btn:hover { border-color: var(--accent); }

.reader-shell__body { line-height: 1.7; }

.reader-shell__infobox dl {
  margin: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 10px;
  font-size: 0.82rem;
}
.reader-shell__infobox-row { display: contents; }
.reader-shell__infobox dt { color: var(--text-muted); }
.reader-shell__infobox dd { margin: 0; }

.reader-shell__revisions,
.reader-shell__see-also,
.reader-shell__references {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--border-subtle);
}

@media (max-width: 1100px) {
  .reader-shell {
    grid-template-columns: minmax(0, 1fr) 280px;
  }
  .reader-shell__drawer { display: none; }
}
@media (max-width: 760px) {
  .reader-shell {
    grid-template-columns: minmax(0, 1fr);
    gap: 24px;
  }
  .reader-shell__rail {
    position: static;
    margin-top: 24px;
  }
}
"""
