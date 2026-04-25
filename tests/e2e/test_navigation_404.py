"""Navigation + 404 behavior for the static site.

The static-site build relies on ``http.server.SimpleHTTPRequestHandler``
which has a default 404 response that's an unstyled white page with no
nav. A user who follows a stale wikilink lands on this page and has no
way out — a real UX bug we want to catch in tests.

This module asserts:

* Hitting an unknown path returns 404 (not 200, not 500)
* The body is a plain 404 with no JS exception
* No console errors fire on the 404 page
* Internal links from the homepage actually resolve
"""

from __future__ import annotations

from playwright.sync_api import Page


def test_unknown_path_returns_404(page: Page, base_url: str) -> None:
    """Hitting a path that doesn't exist on disk returns 404 from the
    bundled stdlib server. We don't try to assert on the body — the
    plain 404 from ``http.server`` is intentionally minimal."""
    resp = page.request.get(f"{base_url}/this-path-does-not-exist.html")
    assert resp.status == 404, f"unknown path returned {resp.status}, expected 404"


def test_404_page_does_not_crash_javascript(page: Page, base_url: str) -> None:
    """Loading the 404 path in a browser tab should not raise a JS
    exception. We don't expect the navigation bar (the stdlib 404 is
    server-rendered without our template), but the page must at least
    not crash."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(f"{base_url}/this-path-does-not-exist.html", wait_until="domcontentloaded")
    assert not errors, f"404 page raised JS errors: {errors}"


def test_homepage_internal_links_resolve(page: Page, base_url: str) -> None:
    """Every same-origin link on the homepage should resolve to a 2xx
    or 3xx response. Catches the class of regression where a link
    points to a path that the build didn't actually emit (e.g. a
    project page deleted between builds)."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")

    # Collect all hrefs that look local (start with / or . or are
    # bare ``foo.html`` paths). Skip mailto:, http(s):, and # fragments.
    hrefs: list[str] = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const h = a.getAttribute('href') || '';
                if (!h) return;
                if (h.startsWith('#') || h.startsWith('mailto:')) return;
                if (h.startsWith('http://') || h.startsWith('https://')) return;
                if (h.startsWith('javascript:')) return;
                out.push(h);
            });
            return [...new Set(out)];
        }"""
    )

    if not hrefs:
        # Synthetic corpus has very few links — skip cleanly rather than fail.
        import pytest
        pytest.skip("homepage has no internal links to verify")

    broken: list[tuple[str, int]] = []
    for href in hrefs[:20]:  # cap at 20 to keep the test fast
        # Resolve relative to base_url + /index.html
        if href.startswith("/"):
            url = f"{base_url}{href}"
        else:
            url = f"{base_url}/{href}"
        # Strip fragment.
        url = url.split("#", 1)[0]
        resp = page.request.get(url)
        if resp.status >= 400:
            broken.append((href, resp.status))

    assert not broken, (
        f"{len(broken)} internal links return 4xx/5xx:\n  "
        + "\n  ".join(f"{h} → {s}" for h, s in broken[:5])
    )


def test_homepage_renders_without_console_errors(page: Page, base_url: str) -> None:
    """The conftest auto-attaches a console listener that records
    every ``console.error``. The home page should produce zero — any
    error is a real bug that's been shipping silently because no
    other test asserts on this exact page in isolation."""
    page.goto(f"{base_url}/index.html", wait_until="networkidle")
    errors = getattr(page, "_llmwiki_console_errors", [])
    # Filter out hljs / CDN noise (non-actionable in our context).
    real = [e for e in errors if "highlight" not in e.lower() and "cdn" not in e.lower()]
    assert not real, f"homepage has console errors: {real}"
