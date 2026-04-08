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


# ─── raw HTML tags in prose must NOT leak as live elements (#74) ─────────


def test_md_to_html_escapes_raw_textarea_in_prose():
    """Regression for the v0.5 hljs-breakage bug: session content mentions
    `<textarea>` in prose. Before the fix, the tag passed through the markdown
    library unescaped, leaked into the DOM, and swallowed every following
    element — including the `<script>` tag that boots hljs. After the fix,
    any tag-shaped substring in prose is escaped so the page stays intact."""
    body = "The markdown inside the <textarea> is correct.\n"
    html_out = md_to_html(body)
    assert "<textarea>" not in html_out
    assert "&lt;textarea&gt;" in html_out


def test_md_to_html_escapes_block_level_raw_html():
    body = "paragraph\n\n<textarea>\nhi\n</textarea>\n\nmore\n"
    html_out = md_to_html(body)
    assert "<textarea>" not in html_out
    assert "</textarea>" not in html_out
    assert "&lt;textarea&gt;" in html_out
    assert "&lt;/textarea&gt;" in html_out


def test_md_to_html_escapes_unknown_custom_elements():
    """Even non-standard tags like <module>, <slug>, <date>, <project> (all
    seen in real session content) need to be escaped — the browser parses
    them as custom elements and still mis-nests the rest of the document."""
    body = "Nested tag mess: <module><project><slug>foo</slug></project></module>\n"
    html_out = md_to_html(body)
    for tag in ("module", "project", "slug"):
        assert f"<{tag}>" not in html_out
        assert f"&lt;{tag}&gt;" in html_out


def test_md_to_html_preserves_inline_code_with_html_syntax():
    """Inline code spans MUST continue to render as `<code>&lt;tag&gt;</code>`
    so the docs can show HTML syntax. The preprocessor skips backtick spans
    so the markdown library's own inline-code handling is untouched.
    Note: `"` inside `<code>` is NOT entity-escaped by Python markdown
    (valid HTML — quote chars inside element text don't need entities)."""
    body = "Use `<textarea class=\"foo\">` for hidden copy source.\n"
    html_out = md_to_html(body)
    assert "<code>" in html_out
    assert '&lt;textarea class="foo"&gt;' in html_out
    # And critically: the raw tag form must be absent so nothing leaks.
    assert "<textarea" not in html_out


def test_md_to_html_preserves_fenced_code_with_html():
    """Fenced code blocks are extracted into placeholders by `fenced_code`
    (priority 25) *before* the escape preprocessor (priority 22) runs, so
    HTML inside fences is preserved verbatim and later escaped by the
    fenced_code extension itself."""
    body = "```html\n<div>hi</div>\n```\n"
    html_out = md_to_html(body)
    assert '<pre><code class="language-html">' in html_out
    # The fenced-code extension takes care of escaping < and > inside.
    assert "&lt;div&gt;hi&lt;/div&gt;" in html_out


def test_md_to_html_preserves_html_comments():
    """`<!-- ... -->` is NOT escaped — build.py emits an
    `<!-- llmwiki:metadata ... -->` comment that AI agents parse directly
    from the HTML body. The preprocessor regex only matches `<[letter]`,
    never `<!`, so comments survive."""
    body = "text\n\n<!-- llmwiki:metadata\nslug: foo\n-->\nmore text\n"
    html_out = md_to_html(body)
    assert "<!-- llmwiki:metadata" in html_out
    assert "&lt;!" not in html_out


def test_md_to_html_does_not_escape_bare_less_than_in_math():
    """`x < 10 and y > 5` must still render as literal text without the
    preprocessor trying to treat it as a tag. The regex only matches
    `<letter` so a space or digit after `<` is left alone for markdown's
    own escaper to handle (it turns bare `<` into `&lt;`)."""
    body = "Condition: x < 10 and y > 5 works.\n"
    html_out = md_to_html(body)
    assert "x &lt; 10" in html_out
    assert "y &gt; 5" in html_out


def test_md_to_html_preserves_markdown_syntax_around_tags():
    body = "**bold** and *italic* and [link](https://example.com) with <br> tag\n"
    html_out = md_to_html(body)
    assert "<strong>bold</strong>" in html_out
    assert "<em>italic</em>" in html_out
    assert '<a href="https://example.com">link</a>' in html_out
    assert "&lt;br&gt;" in html_out
    assert "<br>" not in html_out


def test_md_to_html_session_tail_script_survives_raw_tag():
    """Direct simulation of the pre-fix page-breakage: a body that mentions
    `<textarea>` must not cause any downstream HTML to appear inside the
    literal textarea. We assert the body contains NO raw textarea open tag
    at all — which is what saves the `<script>` tag at the end of every
    session page."""
    body = (
        "# Session\n\n"
        "The check failed because the raw dash was inside the <textarea>.\n\n"
        "Fix: escape the content before writing.\n"
    )
    html_out = md_to_html(body)
    assert "<textarea" not in html_out
    assert "&lt;textarea&gt;" in html_out


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
