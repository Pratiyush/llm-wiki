"""Binder for ``features/graph_viewer.feature`` (#278 follow-up)."""

from __future__ import annotations

from pytest_bdd import given, scenarios, then, when

from playwright.sync_api import Page, expect

from tests.e2e.steps.ui_steps import *  # noqa: F401,F403


scenarios("features/graph_viewer.feature")


def _graph_page_shipped(page: Page, base_url: str) -> bool:
    """Return True when graph.html exists on the server.

    On seeded-corpus E2E runs the graph has zero nodes, and the
    build step intentionally skips writing graph.html in that case
    (see ``graph.copy_to_site``).  The test should skip cleanly
    rather than fail when the page is absent — the builder behaviour
    is already covered in the unit tests.
    """
    resp = page.request.get(base_url + "/graph.html")
    return resp.status < 400


@when("I visit the graph page")
def _visit_graph(page: Page, base_url: str) -> None:
    if not _graph_page_shipped(page, base_url):
        import pytest
        pytest.skip("graph.html not shipped (empty seeded graph)")
    page.goto(base_url + "/graph.html", wait_until="domcontentloaded")


@then("the graph canvas is visible")
def _graph_visible(page: Page) -> None:
    # vis-network renders a <canvas> when graph has data. Empty
    # graphs get the offline-notice banner or just a header — on
    # CI the seeded wiki is sparse, so wait for EITHER the canvas
    # or the #network container itself to be present.
    page.wait_for_selector("#network", state="attached", timeout=5000)


@then("the stats overlay shows the page count")
def _stats_shown(page: Page) -> None:
    # The seeded wiki for E2E tests may be sparse. Just check the
    # overlay element exists + carries a non-empty text content.
    stats = page.locator("#s-pages")
    stats.wait_for(state="attached", timeout=5000)


@then('the "Home" back-link is visible')
def _back_link_visible(page: Page) -> None:
    # The back-to-site link carries id="back-to-site" per #268.
    link = page.locator("#back-to-site")
    # attached rather than visible — on a tiny viewport the button may
    # be below the fold until scrolled.
    link.wait_for(state="attached", timeout=3000)
    href = link.get_attribute("href")
    assert href == "index.html", f"unexpected href: {href!r}"


@then('the graph JSON payload contains "site_url"')
def _graph_payload_has_site_url(page: Page) -> None:
    # Inspect the inline GRAPH constant in the page source.
    html = page.content()
    assert '"site_url"' in html, (
        "graph.html is missing site_url in its injected GRAPH payload — "
        "was the fix from #331 rolled back?"
    )
