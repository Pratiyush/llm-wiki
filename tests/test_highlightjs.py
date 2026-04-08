"""Tests for the highlight.js client-side syntax highlighting integration (v0.5).

These lock in the behaviour of the swap from server-side Pygments/codehilite
to client-side highlight.js:

* ``md_to_html`` produces ``<pre><code class="language-xxx">`` for fenced
  code blocks (no ``.codehilite`` wrapper, no Pygments tokens).
* ``page_head`` and ``page_head_article`` include both light and dark
  highlight.js stylesheets plus the shared theme constants.
* ``page_foot`` injects the highlight.js CDN script and the init snippet.
* No build.py symbol still references ``HAS_PYGMENTS`` or ``codehilite``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki.build import (
    HLJS_DARK_CSS,
    HLJS_LIGHT_CSS,
    HLJS_SCRIPT,
    HLJS_VERSION,
    _hljs_head_tags,
    md_to_html,
    page_foot,
    page_head,
    page_head_article,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ─── md_to_html emits highlight.js-compatible markup ─────────────────────


def test_md_to_html_fenced_code_uses_language_class():
    html = md_to_html("```python\nprint('hi')\n```\n")
    assert '<pre><code class="language-python">' in html
    assert "codehilite" not in html


def test_md_to_html_no_language_fallback_still_pre_code():
    # Untagged fences should still produce a <pre><code> block that hljs
    # can auto-detect. The exact class attribute is optional for untagged
    # blocks — we just require the wrapping tags.
    html = md_to_html("```\nplain text\n```\n")
    assert "<pre><code" in html
    assert "</code></pre>" in html
    assert "codehilite" not in html


def test_md_to_html_inline_code_uses_plain_code_tag():
    html = md_to_html("This is `inline` code.\n")
    assert "<code>inline</code>" in html
    assert "codehilite" not in html


def test_md_to_html_multiple_languages_tagged_independently():
    body = (
        "```bash\nls -la\n```\n"
        "\n"
        "```json\n{\"a\": 1}\n```\n"
    )
    html = md_to_html(body)
    assert '<pre><code class="language-bash">' in html
    assert '<pre><code class="language-json">' in html


# ─── constants are CDN-shaped ────────────────────────────────────────────


def test_hljs_version_is_semver_major_11():
    assert re.match(r"^11\.\d+\.\d+$", HLJS_VERSION), (
        "Pin highlight.js to a v11.x release for stable theme class names."
    )


@pytest.mark.parametrize(
    "url",
    [HLJS_LIGHT_CSS, HLJS_DARK_CSS, HLJS_SCRIPT],
)
def test_hljs_urls_point_at_cdn_release(url):
    assert url.startswith("https://"), "highlight.js assets must load over HTTPS"
    assert "highlightjs/cdn-release" in url
    assert HLJS_VERSION in url


def test_hljs_head_tags_includes_both_themes_and_disables_dark():
    tags = _hljs_head_tags()
    assert 'id="hljs-light"' in tags
    assert 'id="hljs-dark"' in tags
    assert HLJS_LIGHT_CSS in tags
    assert HLJS_DARK_CSS in tags
    # The dark theme ships disabled so the page loads in the light palette
    # by default, then syncs to the saved theme on DOMContentLoaded.
    dark_line = next(line for line in tags.splitlines() if "hljs-dark" in line)
    assert "disabled" in dark_line


# ─── page_head injects theme links ───────────────────────────────────────


def test_page_head_contains_hljs_links():
    html = page_head("t", "d", css_prefix="")
    assert 'id="hljs-light"' in html
    assert 'id="hljs-dark"' in html
    assert HLJS_LIGHT_CSS in html


def test_page_head_article_contains_hljs_links():
    html = page_head_article("t", "d", css_prefix="")
    assert 'id="hljs-light"' in html
    assert 'id="hljs-dark"' in html
    assert HLJS_DARK_CSS in html


# ─── page_foot injects the CDN script + init snippet ─────────────────────


def test_page_foot_loads_highlightjs_script():
    html = page_foot(js_prefix="")
    assert HLJS_SCRIPT in html
    # Must be deferred so it doesn't block first paint.
    assert "defer" in html


def test_page_foot_runs_highlightall_init():
    html = page_foot(js_prefix="")
    # The init snippet calls hljs.highlightAll() once the CDN script loads.
    assert "hljs.highlightAll" in html
    # Guarded by a readiness check so we never call into an undefined global.
    assert "window.hljs" in html


# ─── the Pygments codepath is gone ───────────────────────────────────────


def test_build_py_drops_pygments_codepath():
    # If these symbols leak back in, someone re-introduced the server-side
    # highlighter alongside hljs, which would double-style every <code>.
    src = (REPO_ROOT / "llmwiki" / "build.py").read_text(encoding="utf-8")
    assert "HAS_PYGMENTS" not in src
    # The old Pygments CSS had `.codehilite { background: ...` rules.
    # Comments that merely mention the word are fine; actual CSS selectors
    # or markdown ext_configs entries are not.
    assert ".codehilite {" not in src
    assert '"codehilite"' not in src
    assert "'codehilite'" not in src


# ─── an on-the-fly build references hljs end-to-end ──────────────────────


def test_site_build_emits_hljs_markup(tmp_path, monkeypatch):
    """Run the real builder against a minimal raw/ layout and confirm the
    output HTML actually carries the highlight.js tags. This is the
    smoke-test for the whole swap — if it passes, deploy is safe."""
    from llmwiki import build as build_mod

    raw_root = tmp_path / "raw"
    raw_sessions = raw_root / "sessions"
    (raw_sessions / "demo-proj").mkdir(parents=True)
    session_md = """---
title: "Session: hljs smoke"
type: source
tags: [demo]
date: 2026-04-08
source_file: raw/sessions/demo-proj/2026-04-08-hljs-smoke.md
sessionId: demo-hljs
slug: hljs-smoke
project: demo-proj
started: 2026-04-08T09:00:00+00:00
ended: 2026-04-08T09:30:00+00:00
model: claude-sonnet-4-6
---

# Session: hljs smoke

```python
def greet(name: str) -> str:
    return f"hi {name}"
```
"""
    (raw_sessions / "demo-proj" / "2026-04-08-hljs-smoke.md").write_text(
        session_md, encoding="utf-8"
    )
    # Point build_site at our tmp raw/ layout without touching the real one.
    monkeypatch.setattr(build_mod, "RAW_DIR", raw_root)
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", raw_sessions)

    out = tmp_path / "site"
    rc = build_mod.build_site(out_dir=out, synthesize=False)
    assert rc == 0, f"build_site returned {rc}"

    index_html = (out / "index.html").read_text(encoding="utf-8")
    assert "hljs-light" in index_html
    assert "hljs-dark" in index_html
    assert HLJS_SCRIPT in index_html

    session_html = (
        out / "sessions" / "demo-proj" / "2026-04-08-hljs-smoke.html"
    ).read_text(encoding="utf-8")
    assert '<pre><code class="language-python">' in session_html
    assert "hljs.highlightAll" in session_html
