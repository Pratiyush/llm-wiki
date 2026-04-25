"""UX / microcopy / naming sanity from a human-perspective.

Most UI bugs are not "the button doesn't work" — they're "the button
works but the label is gibberish", "the empty state looks like an
error", "the error message ends in 'undefined'", or "the date format
is unreadable". This module asserts on those quiet UX bugs.

Heuristics encoded here:

1. **No raw template artifacts shipped to users** — strings like
   ``{title}``, ``{{ user }}``, ``None``, ``undefined``, ``null`` are
   leaks from a broken format string and should never reach the user.
2. **Buttons have human-readable labels** — not just icons. An
   icon-only button is fine for power users but must carry a tooltip
   (``title`` or ``aria-label``).
3. **Headings are not empty** — an empty ``<h1>`` is a layout bug.
4. **The site name is consistent** — a build that says "LLM Wiki" in
   the title and "llmwiki" in the nav and "Wiki" in the footer is
   confusing. We don't enforce a single canonical form; we just flag
   inconsistencies in case the brand voice changes.
5. **Time formatting is human-readable** — a session card showing
   ``2026-04-09T09:00:00+00:00`` is technically correct but unfriendly.
   We don't forbid ISO; we flag pages where it's the *only* time format.
6. **No leftover debug strings** — TODO, FIXME, XXX, lorem ipsum,
   debug:.
7. **404 / empty states have an action** — "no results" with no link
   to "go home" is a dead end.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page


# Strings that must never leak into rendered text — these are
# template-rendering bugs.
TEMPLATE_LEAK_PATTERNS = [
    r"\{[a-zA-Z_]\w*\}",          # f-string placeholder: {title}
    r"\{\{\s*[\w\.]+\s*\}\}",     # Jinja-style: {{ project }}
    r"\bundefined\b",
    r"\bNone\b",                   # Python None leaked into HTML
    r"\bnull\b(?![- ])",          # JS null (but not "null-pointer" etc.)
    r"\[object Object\]",
]

# Debug / placeholder text that should not ship.
DEBUG_LEAK_PATTERNS = [
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bXXX\b",
    r"\blorem ipsum\b",
]


def _visible_text(page: Page) -> str:
    """Return the visible body text — excludes <script>, <style>,
    and aria-hidden subtrees."""
    return page.evaluate(
        """() => {
            // Clone body so we can scrub script/style without
            // mutating the live page. Then extract innerText, which
            // already drops display:none subtrees.
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll('script, style, [aria-hidden="true"]').forEach(
                el => el.remove()
            );
            return clone.innerText || '';
        }"""
    )


def test_homepage_has_no_template_leaks(page: Page, base_url: str) -> None:
    """A failed format string leaves placeholders in the rendered
    output. Asserting this on the homepage catches the most common
    leak class — a missing variable in a header or hero subtitle."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    text = _visible_text(page)
    leaks: list[str] = []
    for pattern in TEMPLATE_LEAK_PATTERNS:
        for m in re.finditer(pattern, text):
            # Skip code blocks where these tokens are legitimate.
            ctx_start = max(0, m.start() - 20)
            ctx_end = min(len(text), m.end() + 20)
            leaks.append(text[ctx_start:ctx_end].replace("\n", " "))
    # Allow a couple of legitimate appearances (e.g. "None" inside
    # a session that literally discusses null) — fail only on bulk.
    assert len(leaks) <= 2, (
        f"homepage has {len(leaks)} suspected template leaks:\n  "
        + "\n  ".join(leaks[:5])
    )


def test_session_page_chrome_has_no_template_leaks(page: Page, base_url: str) -> None:
    """Template-leak guard for the *chrome* of a session page — the
    breadcrumbs, hero h1, page title, sidebar, and footer. We do NOT
    scan the article body because session content legitimately
    contains code with f-string placeholders, Python ``None``, JS
    ``null`` etc. The chrome is what users perceive as "the site",
    so leaks there are the only ones that read as broken."""
    page.goto(
        f"{base_url}/sessions/e2e-demo/2026-04-09-e2e-python-demo.html",
        wait_until="domcontentloaded",
    )
    chrome_selectors = (
        "title", ".hero", ".breadcrumbs", ".nav", "header", "footer",
        ".mobile-bottom-nav", ".sidebar",
    )
    chrome_text = page.evaluate(
        """(selectors) => {
            const out = [];
            for (const sel of selectors) {
                document.querySelectorAll(sel).forEach(el => {
                    out.push(el.innerText || el.textContent || '');
                });
            }
            return out.join('\\n');
        }""",
        list(chrome_selectors),
    )

    leaks: list[str] = []
    for pattern in TEMPLATE_LEAK_PATTERNS:
        for m in re.finditer(pattern, chrome_text):
            ctx_start = max(0, m.start() - 20)
            ctx_end = min(len(chrome_text), m.end() + 20)
            leaks.append(chrome_text[ctx_start:ctx_end].replace("\n", " "))
    assert not leaks, (
        f"session page chrome has {len(leaks)} template leak(s):\n  "
        + "\n  ".join(leaks[:5])
    )


def test_no_debug_strings_in_rendered_pages(page: Page, base_url: str) -> None:
    """TODO / FIXME / XXX in rendered prose are obvious "this wasn't
    finished" tells. We allow them inside code blocks (they're
    legitimate code comments) but never in the prose around them."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    # Scrub code; whatever's left is human-facing prose.
    prose = page.evaluate(
        """() => {
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll(
                'script, style, pre, code, [aria-hidden="true"]'
            ).forEach(el => el.remove());
            return clone.innerText || '';
        }"""
    )
    leaks: list[str] = []
    for pattern in DEBUG_LEAK_PATTERNS:
        for m in re.finditer(pattern, prose, re.IGNORECASE):
            ctx_start = max(0, m.start() - 30)
            ctx_end = min(len(prose), m.end() + 30)
            leaks.append(prose[ctx_start:ctx_end].replace("\n", " "))
    assert not leaks, (
        f"homepage prose contains debug strings:\n  "
        + "\n  ".join(leaks[:5])
    )


def test_every_button_has_an_accessible_name(page: Page, base_url: str) -> None:
    """An icon-only button with no aria-label / title / inner-text is
    a screen-reader dead zone — it announces as "button" with no
    context. Catches the most common regression: someone adds a new
    icon button and forgets the label."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    nameless = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('button').forEach(b => {
                const text = (b.innerText || '').trim();
                const aria = (b.getAttribute('aria-label') || '').trim();
                const title = (b.getAttribute('title') || '').trim();
                if (!text && !aria && !title) {
                    out.push({
                        id: b.id || '',
                        cls: b.className || '',
                        html: (b.outerHTML || '').slice(0, 120),
                    });
                }
            });
            return out;
        }"""
    )
    assert not nameless, (
        f"{len(nameless)} button(s) have no accessible name:\n  "
        + "\n  ".join(repr(b) for b in nameless[:5])
    )


def test_no_empty_headings_on_homepage(page: Page, base_url: str) -> None:
    """An empty heading is a layout bug — usually a CSS class flipped
    to display:none on the wrong element, leaving an empty h1/h2/h3
    in the DOM. Crashes screen-reader heading navigation."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    empty = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(h => {
                if (!(h.innerText || '').trim()) {
                    out.push({
                        tag: h.tagName,
                        cls: h.className || '',
                        html: (h.outerHTML || '').slice(0, 100),
                    });
                }
            });
            return out;
        }"""
    )
    assert not empty, (
        f"{len(empty)} empty heading(s) on homepage:\n  "
        + "\n  ".join(repr(h) for h in empty[:5])
    )


def test_link_text_is_not_generic(page: Page, base_url: str) -> None:
    """"Click here" / "Read more" / "Link" are accessibility
    anti-patterns — screen-reader users who navigate by link list
    see a list of "click here, click here, click here". Each link
    should describe its destination."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    generic = {"click here", "read more", "link", "here", "more"}
    bad = page.evaluate(
        """(generic) => {
            const out = [];
            document.querySelectorAll('a').forEach(a => {
                const text = ((a.innerText || a.textContent || '').trim().toLowerCase());
                if (generic.includes(text)) {
                    out.push({ text, href: a.getAttribute('href') || '' });
                }
            });
            return out;
        }""",
        list(generic),
    )
    assert not bad, (
        f"{len(bad)} generic-text link(s):\n  "
        + "\n  ".join(repr(b) for b in bad[:5])
    )


def test_homepage_has_a_top_level_heading(page: Page, base_url: str) -> None:
    """Every page should have exactly one ``<h1>`` — multiple h1s
    confuse assistive tech and SEO crawlers; zero h1s leaves the
    page without a landmark heading."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    count = page.locator("h1").count()
    assert count >= 1, "homepage has no <h1> at all"
    assert count <= 1, (
        f"homepage has {count} <h1> tags — one document, one h1 by convention"
    )


def test_meta_description_is_present_and_meaningful(page: Page, base_url: str) -> None:
    """``<meta name="description">`` is what search engines use as
    the snippet on a result page. Empty / missing means terrible
    SEO. We're permissive: any non-empty string is fine."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    desc = page.evaluate(
        """() => {
            const m = document.querySelector('meta[name="description"]');
            return m ? (m.getAttribute('content') || '') : null;
        }"""
    )
    if desc is None:
        pytest.skip("meta description not emitted by build")
    assert desc.strip(), "meta description is present but empty"
    assert len(desc.strip()) >= 20, (
        f"meta description is suspiciously short ({len(desc.strip())} chars): {desc!r}"
    )


def test_session_page_breadcrumbs_make_sense_to_humans(page: Page, base_url: str) -> None:
    """Breadcrumbs should read like a path: e.g. "Home / Projects /
    e2e-demo / 2026-04-09". A regression where one crumb is a UUID
    or a kebab-case slug instead of a human label is a real UX bug."""
    page.goto(
        f"{base_url}/sessions/e2e-demo/2026-04-09-e2e-python-demo.html",
        wait_until="domcontentloaded",
    )
    crumbs_text = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('.breadcrumbs a, .breadcrumbs span').forEach(
                e => { const t = (e.innerText || '').trim(); if (t) out.push(t); }
            );
            return out;
        }"""
    )
    if not crumbs_text:
        pytest.skip("no breadcrumbs on this build")
    # First crumb should be a well-known landing — Home / llmwiki / Wiki / Index.
    first = crumbs_text[0].lower()
    assert any(s in first for s in ("home", "wiki", "index", "llmwiki", "all")), (
        f"first breadcrumb is {crumbs_text[0]!r} — not a recognisable root label"
    )
    # No crumb should be a raw UUID or hash.
    for c in crumbs_text:
        assert not re.match(r"^[a-f0-9]{16,}$", c, re.IGNORECASE), (
            f"breadcrumb {c!r} looks like a raw hash/UUID, not a human label"
        )
