"""#636 (#pw-x8): cross-browser smoke for the highest-traffic pages.

The full e2e suite runs only against chromium (browser-install cost +
test-runtime budget). This module is a small smoke — homepage, sessions
index, graph — that's *meant* to run against chromium / firefox /
webkit via a separate CI workflow. Catches engine-specific regressions
in CSS variable resolution, custom-element scoping, SVG behaviour, or
Promise semantics that only surface outside chromium.

Run locally:

    pytest tests/e2e/test_cross_browser_smoke.py --browser=firefox
    pytest tests/e2e/test_cross_browser_smoke.py --browser=webkit

CI matrixes over all three browsers via `.github/workflows/cross-browser.yml`.

Each test stays small and fast — anything bigger lives in the chromium-
only suite to keep the cross-browser job under 5 minutes.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Page


def test_homepage_loads_with_nav_and_title(page: Page, base_url: str) -> None:
    """The single most important page — title bar + sticky nav must
    render in every engine. Catches engine-specific CSS variable
    resolution failures + missing-feature regressions."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    title = page.title()
    assert "LLM Wiki" in title or "llmwiki" in title.lower(), (
        f"unexpected document title: {title!r}"
    )
    nav = page.locator("header.nav").first
    assert nav.is_visible(timeout=3000), "site nav not visible on homepage"


def test_sessions_index_renders_table(page: Page, base_url: str) -> None:
    """Table layout regressions across engines: tables with
    `table-layout: fixed` + sticky thead behave subtly differently
    on Firefox vs WebKit. Catches the family of #452-style
    column-alignment bugs across engines."""
    resp = page.request.get(f"{base_url}/sessions/index.html")
    if resp.status >= 400:
        pytest.skip(f"sessions index not shipped (HTTP {resp.status})")
    page.goto(f"{base_url}/sessions/index.html", wait_until="domcontentloaded")
    table = page.locator("table.sessions-table").first
    assert table.is_visible(timeout=3000)
    # At least one row in the body — the seeded harness has 8 demo sessions.
    rows = page.locator("table.sessions-table tbody tr").count()
    assert rows >= 1, f"sessions table has {rows} rows — expected ≥1"


def test_graph_page_loads_canvas(page: Page, base_url: str) -> None:
    """Canvas + vis-network behaviour varies by engine. Smoke checks
    that the canvas is at least attached + has nonzero size — full
    graph render uses CDN-loaded vis-network which has its own engine
    quirks."""
    resp = page.request.get(f"{base_url}/graph.html")
    if resp.status >= 400:
        pytest.skip("graph.html not shipped")
    page.goto(f"{base_url}/graph.html", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)  # let vis-network init
    box = page.evaluate(
        "() => { const c = document.querySelector('canvas'); "
        "return c ? c.getBoundingClientRect() : null; }"
    )
    assert box is not None, "no <canvas> in graph.html"
    assert box["width"] > 0 and box["height"] > 0, (
        f"canvas has zero size in this engine: {box}"
    )


def test_theme_toggle_flips_data_theme(page: Page, base_url: str) -> None:
    """Theme toggle relies on localStorage + custom property updates;
    Firefox + WebKit each have their own quirks here. Confirms the
    cross-engine contract."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    page.locator("body").click(position={"x": 1, "y": 1})
    initial = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    btn = page.locator("#theme-toggle").first
    if not btn.is_visible():
        pytest.skip("no #theme-toggle on this build")
    btn.click()
    page.wait_for_timeout(200)
    after = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    assert after != initial, (
        f"theme toggle did not flip data-theme: {initial!r} -> {after!r}"
    )
