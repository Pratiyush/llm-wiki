"""#452: sessions/index.html shouldn't render the date in both the
Session cell and the Date column.

Frontmatter for auto-generated session sources stores the title as
``"Session: <slug> — <date>"``. After the renderer strips the
``"Session: "`` prefix, the cell text becomes ``"<slug> — <date>"`` —
which is wasteful since the next cell already shows the same date.

These tests pin the contract:

1. For a row whose title ends in `` — <date>`` matching the row's date,
   the Session ``<td>`` does not contain that date string.
2. The Date ``<td>`` still carries the date.
3. Custom titles without the ``" — YYYY-MM-DD"`` suffix are left intact.
4. The colgroup + ``table-layout: fixed`` rules are present so sticky
   header alignment doesn't regress.
"""
from __future__ import annotations

import re
from pathlib import Path

from llmwiki.build import render_sessions_index
from llmwiki.render.css import CSS


def _src(slug: str, date: str, project: str = "demo", title: str | None = None):
    """Build a (path, meta, body) tuple matching render_sessions_index input."""
    fm = {
        "title": title if title is not None else f"Session: {slug} — {date}",
        "slug": slug,
        "project": project,
        "date": date,
        "model": "claude-sonnet-4-6",
        "started": f"{date}T00:00:00+00:00",
        "user_messages": 5,
        "tool_calls": 12,
    }
    fname = f"{date}T00-00-{project}-{slug}.md"
    return (Path("raw/sessions") / fname, fm, "body")


def _row_for_slug(html_text: str, slug: str) -> str:
    m = re.search(
        r'<tr data-project="[^"]*" data-model="[^"]*" data-date="[^"]*" data-slug="' + re.escape(slug) + r'">.*?</tr>',
        html_text,
        re.DOTALL,
    )
    assert m, f"row for slug {slug!r} not found in rendered html"
    return m.group(0)


def _link_text(td_html: str) -> str:
    """Extract just the link's anchor text from a `<td><a …>TEXT</a></td>` cell.

    We can't grep the full `<td>` for the date — the href naturally embeds
    the date as part of the session filename, which would false-positive.
    The contract being asserted is about visible text only.
    """
    m = re.search(r"<a[^>]*>(.*?)</a>", td_html, re.DOTALL)
    return m.group(1) if m else td_html


def test_session_cell_no_longer_contains_date(tmp_path: Path) -> None:
    sources = [_src("dark-mode-toggle", "2026-04-01", project="demo-blog-engine")]
    groups = {"demo-blog-engine": sources}
    out = render_sessions_index(sources, groups, tmp_path)
    html_text = out.read_text(encoding="utf-8")
    row = _row_for_slug(html_text, "dark-mode-toggle")
    cells = re.findall(r"<td.*?>(.*?)</td>", row, re.DOTALL)
    # cells = [Session, Agent, Project, Date, Model, Msgs, Tools]
    session_cell, _, _, date_cell, *_ = cells
    session_text = _link_text(session_cell)
    assert "dark-mode-toggle" in session_text
    assert "2026-04-01" not in session_text, (
        "Session cell anchor text still contains the date — "
        "the dedicated Date column already has it"
    )
    assert "2026-04-01" in date_cell, "Date column lost the date string"


def test_custom_title_without_date_suffix_preserved(tmp_path: Path) -> None:
    """If somebody hand-edits a session frontmatter title to something
    that doesn't follow the auto-generated `" — <date>"` shape, the
    Session cell must keep it verbatim."""
    sources = [_src("custom", "2026-04-01", title="My Custom Session Title")]
    groups = {"demo": sources}
    out = render_sessions_index(sources, groups, tmp_path)
    html_text = out.read_text(encoding="utf-8")
    row = _row_for_slug(html_text, "custom")
    session_cell = re.findall(r"<td.*?>(.*?)</td>", row, re.DOTALL)[0]
    assert "My Custom Session Title" in session_cell


def test_session_prefix_still_stripped(tmp_path: Path) -> None:
    """The pre-existing "Session: " prefix-strip must continue to work
    after the new date-suffix-strip lands on top of it."""
    sources = [_src("with-prefix", "2026-04-01")]
    groups = {"demo": sources}
    out = render_sessions_index(sources, groups, tmp_path)
    html_text = out.read_text(encoding="utf-8")
    row = _row_for_slug(html_text, "with-prefix")
    session_cell = re.findall(r"<td.*?>(.*?)</td>", row, re.DOTALL)[0]
    assert "Session:" not in session_cell


def test_colgroup_present_for_sticky_header_alignment(tmp_path: Path) -> None:
    """Pin the markup contract for sticky-header alignment fix — a
    <colgroup> + table-layout:fixed combo keeps thead aligned with tbody."""
    sources = [_src("a", "2026-04-01")]
    out = render_sessions_index(sources, {"demo": sources}, tmp_path)
    html_text = out.read_text(encoding="utf-8")
    assert "<colgroup>" in html_text
    assert html_text.count("<col ") == 7  # 7 columns
    # The CSS rule that makes colgroup widths binding must be present.
    assert "table-layout: fixed" in CSS
    assert ".sessions-table" in CSS
