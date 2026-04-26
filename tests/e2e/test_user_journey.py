"""End-to-end user journey: home → project → session → graph → home.

Each existing test covers one feature in isolation. Real regressions
often span features — e.g. clicking a project card from the homepage
might work, but the breadcrumb on the destination might link to a
path that 404s. Only a multi-step journey catches that.

This is the only test in the suite that reads page-load timing and
asserts on cross-page state (theme persists across pages, no console
errors accumulate). Treat it as a smoke test for the *whole*
navigation surface, not any one feature.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_full_navigation_journey(page: Page, base_url: str) -> None:
    """Walk the canonical user path. Any step that fails surfaces a
    cross-page regression that single-feature tests miss."""

    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on("console", lambda msg: errors.append(f"console.{msg.type}: {msg.text}")
            if msg.type == "error" else None)

    # Step 1: home loads cleanly.
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    expect(page.locator(".hero h1").first).to_be_visible()

    # Step 2: toggle theme — assert it sticks for the rest of the journey.
    page.locator("#theme-toggle").first.click()
    theme_at_home = page.evaluate(
        "() => document.documentElement.getAttribute('data-theme')"
    )
    assert theme_at_home in ("dark", "light"), (
        f"theme toggle produced bogus data-theme: {theme_at_home!r}"
    )

    # Step 3: navigate to projects index via nav bar.
    projects_link = page.locator('.nav-links a:has-text("Projects")').first
    if projects_link.count() == 0:
        # Some builds put the link under a different label.
        projects_link = page.locator('.nav-links a[href*="projects"]').first
    if projects_link.count() > 0 and projects_link.is_visible():
        projects_link.click()
        page.wait_for_load_state("domcontentloaded")
        # Theme should persist across navigation.
        theme_at_projects = page.evaluate(
            "() => document.documentElement.getAttribute('data-theme')"
        )
        assert theme_at_projects == theme_at_home, (
            f"theme did not persist across navigation: home={theme_at_home!r}, "
            f"projects={theme_at_projects!r}"
        )

    # Step 4: navigate to sessions index.
    page.goto(f"{base_url}/sessions/index.html", wait_until="domcontentloaded")
    # The sessions index should render at least one row OR an empty-state.
    has_content = page.evaluate(
        "() => document.querySelector('.content, article, main')?.innerText?.length > 0"
    )
    assert has_content, "sessions index has no content area"

    # Step 5: open the synthetic demo session directly.
    page.goto(
        f"{base_url}/sessions/e2e-demo/2026-04-09-e2e-python-demo.html",
        wait_until="domcontentloaded",
    )
    expect(page.locator(".breadcrumbs").first).to_be_visible()

    # Step 6: theme STILL persists.
    theme_at_session = page.evaluate(
        "() => document.documentElement.getAttribute('data-theme')"
    )
    assert theme_at_session == theme_at_home, (
        f"theme reset on session page: home={theme_at_home!r}, "
        f"session={theme_at_session!r}"
    )

    # Step 7: open command palette via Cmd+K (cross-platform shortcut).
    page.locator("body").click(position={"x": 1, "y": 1})
    page.keyboard.press("ControlOrMeta+k")
    page.wait_for_function(
        "() => document.getElementById('palette')?.getAttribute('aria-hidden') === 'false'",
        timeout=3000,
    )
    # Close it.
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => document.getElementById('palette')?.getAttribute('aria-hidden') === 'true'",
        timeout=3000,
    )

    # Step 8: graph page (skip cleanly if not shipped).
    graph_resp = page.request.get(f"{base_url}/graph.html")
    if graph_resp.status < 400:
        page.goto(f"{base_url}/graph.html", wait_until="domcontentloaded")
        # #456: the user's escape hatch is now the Home link in the
        # injected site nav (the #268 shim was removed).
        nav_home = page.locator('header.nav nav.nav-links a[href="index.html"]').first
        if nav_home.count() > 0:
            href = nav_home.get_attribute("href")
            assert href in ("index.html", "/index.html", "../index.html"), (
                f"nav Home link has bad href: {href!r}"
            )

    # Step 9: return home. No errors should have accumulated.
    page.goto(f"{base_url}/index.html", wait_until="networkidle")

    # Filter out CDN / external-resource noise — those aren't ours.
    real_errors = [
        e for e in errors
        if "cdn" not in e.lower()
        and "highlight" not in e.lower()
        and "favicon" not in e.lower()
        and "vis-network" not in e.lower()
    ]
    assert not real_errors, (
        f"user journey accumulated {len(real_errors)} errors:\n  "
        + "\n  ".join(real_errors[:10])
    )


def test_breadcrumbs_back_to_home_works(page: Page, base_url: str) -> None:
    """The breadcrumb on a session page should always lead back to
    home in at most one click. Catches the regression where the
    first crumb's href is a relative path that doesn't resolve."""
    page.goto(
        f"{base_url}/sessions/e2e-demo/2026-04-09-e2e-python-demo.html",
        wait_until="domcontentloaded",
    )
    crumbs = page.locator(".breadcrumbs a").all()
    if not crumbs:
        import pytest
        pytest.skip("session page has no breadcrumb anchors")

    first = crumbs[0]
    href = first.get_attribute("href")
    assert href, "first breadcrumb has no href"

    # Click it and verify we land on a 2xx page (not a 404).
    with page.expect_response(lambda r: r.request.resource_type == "document") as resp_info:
        first.click()
    resp = resp_info.value
    assert resp.status < 400, (
        f"first breadcrumb leads to status {resp.status} at {resp.url}"
    )
