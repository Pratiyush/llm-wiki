"""#455: home project cards show a small muted activity date range
under the meta line. These tests pin the rendering contract so the
date-range div doesn't drift back to bare meta-only cards.

The render_index() emitter computes the range from each session's
`date:` frontmatter field (string YYYY-MM-DD). Five cases exercised:

1. Multi-day project shows `first → last` arrow form.
2. Single-day project shows the date once, no arrow.
3. Project with no dates renders no `.card-date-range` element.
4. Date strings are html-escaped (defence in depth — frontmatter
   should already be safe, but the emitter shouldn't trust that).
5. CSS rule `.card-date-range` is defined in render/css.py so the
   div isn't unstyled.
"""
from __future__ import annotations

from pathlib import Path

from llmwiki.build import render_index
from llmwiki.render.css import CSS


def _meta(date: str, project: str = "demo", model: str = "claude-sonnet-4-6") -> dict:
    return {
        "title": f"session-{date}",
        "slug": f"session-{date}",
        "project": project,
        "date": date,
        "model": model,
        "tools_used": [],
    }


def _session(date: str, project: str = "demo", filename: str | None = None):
    """Build a (path, meta, body) tuple matching render_index() input shape."""
    fname = filename or f"2026-01-01T00-00-{project}-{date}.md"
    return (Path("raw/sessions") / fname, _meta(date, project=project), "body")


def _render(groups, tmp_path: Path) -> str:
    all_sources = [s for sessions in groups.values() for s in sessions]
    out_path = render_index(groups=groups, all_sources=all_sources, out_dir=tmp_path)
    return out_path.read_text(encoding="utf-8")


def test_multi_day_project_renders_date_range(tmp_path: Path) -> None:
    groups = {"demo": [
        _session("2026-03-12", filename="a.md"),
        _session("2026-04-01", filename="b.md"),
        _session("2026-03-20", filename="c.md"),
    ]}
    html_out = _render(groups, tmp_path)
    assert 'class="card-date-range"' in html_out
    assert "2026-03-12 → 2026-04-01" in html_out


def test_single_day_project_renders_one_date(tmp_path: Path) -> None:
    groups = {"demo": [
        _session("2026-04-01", filename="a.md"),
        _session("2026-04-01", filename="b.md"),
    ]}
    html_out = _render(groups, tmp_path)
    assert 'class="card-date-range"' in html_out
    assert ">2026-04-01<" in html_out
    # Arrow only appears in multi-day form. Spot-check inside the cards.
    cards_only = html_out.split('class="card-grid"', 1)[1]
    assert "→" not in cards_only


def test_no_dates_no_date_element(tmp_path: Path) -> None:
    """Sessions whose meta has no `date` (or blank) yield no date-range div."""
    no_date_meta = {"slug": "x", "project": "demo", "model": "claude-sonnet-4-6"}
    blank_meta = {"slug": "y", "project": "demo", "model": "claude-sonnet-4-6", "date": ""}
    groups = {"demo": [
        (Path("raw/sessions/x.md"), no_date_meta, "b"),
        (Path("raw/sessions/y.md"), blank_meta, "b"),
    ]}
    html_out = _render(groups, tmp_path)
    assert "card-date-range" not in html_out


def test_date_string_html_escaped(tmp_path: Path) -> None:
    """Defence in depth — even if frontmatter ever carries `<` characters,
    the card div must escape them rather than render raw."""
    groups = {"demo": [
        _session("2026-03-12<script>alert(1)</script>", filename="a.md"),
        _session("2026-04-01", filename="b.md"),
    ]}
    html_out = _render(groups, tmp_path)
    assert "<script>alert" not in html_out
    assert "&lt;script&gt;" in html_out


def test_css_class_defined() -> None:
    assert ".card-date-range" in CSS
