"""#454: every input/select in the filter bar above sessions/index.html
must be wrapped in a `<label>` so screen readers announce it consistently
and the visual baseline doesn't drift below its peers.

The slug input was the only bare control; this test pins the label
contract for it and verifies all four neighbouring controls keep theirs.
"""
from __future__ import annotations

import re
from pathlib import Path

from llmwiki.build import render_sessions_index


def _src(slug: str = "x", project: str = "demo", date: str = "2026-04-01"):
    fm = {
        "title": f"Session: {slug} — {date}",
        "slug": slug,
        "project": project,
        "date": date,
        "model": "claude-sonnet-4-6",
        "started": f"{date}T00:00:00+00:00",
    }
    return (Path(f"raw/sessions/{date}T00-00-{project}-{slug}.md"), fm, "body")


def _render(tmp_path: Path) -> str:
    sources = [_src("a"), _src("b", date="2026-04-02")]
    out = render_sessions_index(sources, {"demo": sources}, tmp_path)
    return out.read_text(encoding="utf-8")


def test_slug_input_wrapped_in_label(tmp_path: Path) -> None:
    html_text = _render(tmp_path)
    # Find a label that contains the slug input. Span across newlines so
    # the wrapper layout is allowed.
    pattern = re.compile(
        r'<label>\s*Slug\s*<input[^>]*id="filter-text"',
        re.IGNORECASE,
    )
    assert pattern.search(html_text), (
        "filter-text input must be wrapped in a `<label>Slug ...</label>` "
        "so screen readers announce it consistently with the other filters"
    )


def test_filter_text_no_longer_bare(tmp_path: Path) -> None:
    """Defensive — make sure no bare `<input ... id="filter-text">` survives
    outside a label wrapper."""
    html_text = _render(tmp_path)
    # Every occurrence of id="filter-text" must be preceded (within ~80
    # chars) by an opening <label> tag. The current renderer emits exactly
    # one such input, so this is a tight contract.
    occurrences = [m.start() for m in re.finditer(r'id="filter-text"', html_text)]
    assert occurrences, "filter-text input missing from rendered html"
    for start in occurrences:
        prefix = html_text[max(0, start - 120) : start]
        assert "<label>" in prefix, f"filter-text input not wrapped in label: {prefix!r}"


def test_all_filters_have_labels(tmp_path: Path) -> None:
    """Project, Model, From, To, and Slug all need a `<label>` wrapper."""
    html_text = _render(tmp_path)
    for control_id in (
        "filter-project",
        "filter-model",
        "filter-date-from",
        "filter-date-to",
        "filter-text",
    ):
        m = re.search(r'id="' + control_id + r'"', html_text)
        assert m, f"{control_id} not in rendered html"
        prefix = html_text[max(0, m.start() - 200) : m.start()]
        assert "<label>" in prefix, f"{control_id} not wrapped in label"
