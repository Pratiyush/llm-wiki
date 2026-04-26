"""#460: mobile-viewport top-nav items were unreachable.

Below 1024px the desktop `.nav-links` row is hidden by an existing
media query, so Graph / Docs / Changelog had no path on phones. The
mobile bottom nav only carries Home / Projects / Sessions / Search /
Theme. The fix adds a hamburger button (visible <1024px) that toggles
a drawer mirroring the same 6 nav links vertically.

These tests pin the markup, CSS, and JS contracts.
"""
from __future__ import annotations

from llmwiki.build import nav_bar
from llmwiki.render.css import CSS
from llmwiki.render.js import JS


# ─── Markup contract ──────────────────────────────────────────────────


def test_nav_emits_hamburger_button() -> None:
    html_text = nav_bar(active="home")
    assert 'id="nav-hamburger"' in html_text
    assert 'aria-expanded="false"' in html_text
    assert 'aria-controls="nav-drawer"' in html_text
    assert 'aria-label="Open navigation menu"' in html_text


def test_nav_emits_drawer_with_six_links() -> None:
    html_text = nav_bar(active="home")
    assert 'id="nav-drawer"' in html_text
    # Drawer starts hidden so the user doesn't see it on desktop.
    assert "<div id=\"nav-drawer\" class=\"nav-drawer\" hidden" in html_text
    # All six top-level nav targets reachable from the drawer.
    for target in (
        'href="index.html"',
        'href="projects/index.html"',
        'href="sessions/index.html"',
        'href="graph.html"',
        'href="docs/index.html"',
        'href="changelog.html"',
    ):
        assert html_text.count(target) >= 2, (
            f"{target} should appear in both .nav-links AND .nav-drawer "
            "so it's reachable on every viewport"
        )


def test_drawer_marks_active_link() -> None:
    """The drawer must visually highlight the current page so users
    can orient themselves on mobile, same as the desktop nav."""
    html_text = nav_bar(active="graph")
    # The drawer Graph link carries `class="nav-drawer-link active"`.
    assert 'class="nav-drawer-link active">Graph</a>' in html_text


# ─── CSS contract ─────────────────────────────────────────────────────


def test_css_hides_hamburger_above_1024() -> None:
    """Hamburger should be hidden by default (desktop) and only shown
    where the desktop nav-links row has been hidden (<1024)."""
    assert ".nav-hamburger {" in CSS
    # Default: display none.
    assert "display: none" in CSS
    # Show below 1024.
    assert "@media (max-width: 1023px) { .nav-hamburger" in CSS


def test_css_drawer_styles_present() -> None:
    assert ".nav-drawer {" in CSS
    assert ".nav-drawer-link {" in CSS
    # Drawer must carry an active state for the current page.
    assert ".nav-drawer-link.active" in CSS


# ─── JS contract ──────────────────────────────────────────────────────


def test_js_wires_hamburger_toggle() -> None:
    assert "nav-hamburger" in JS
    assert "nav-drawer" in JS
    # Toggle reads + writes aria-expanded.
    assert 'getAttribute("aria-expanded")' in JS
    assert 'setAttribute("aria-expanded"' in JS


def test_js_handles_escape_key() -> None:
    """ESC closes the drawer and returns focus to the hamburger so
    keyboard users don't get trapped."""
    assert 'key === "Escape"' in JS
    # Focus return — find the assignment near the Escape handler.
    esc_block = JS[JS.find('key === "Escape"'): JS.find('key === "Escape"') + 200]
    assert "btn.focus()" in esc_block


def test_js_closes_drawer_on_outside_click() -> None:
    """Click-outside-to-close is the standard menu pattern."""
    # The handler checks contains() on both drawer + button, then closes.
    assert "drawer.contains(e.target)" in JS
    assert "btn.contains(e.target)" in JS


def test_js_closes_drawer_after_navigation() -> None:
    """After tapping a drawer link, close before the next page loads
    so the next page doesn't briefly render with the drawer open."""
    drawer_block = JS[JS.find("nav-drawer"): JS.find("Reading progress")]
    assert 'querySelectorAll("a")' in drawer_block
    assert 'setOpen(false)' in drawer_block
