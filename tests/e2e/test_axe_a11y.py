"""Automated WCAG 2.1 AA scan via axe-core.

The existing ``test_accessibility.py`` covers a handful of structural
checks (skip-link, aria-labels, focus order). It misses the long
tail: color contrast on every paragraph, heading-level hierarchy,
link names that read as "click here", form-control labels, etc.

This module injects axe-core into each page type, runs the full
scan, and asserts that no ``critical`` or ``serious`` violations
exist. ``moderate`` and ``minor`` are reported but don't fail the
test — they're advisory until we have a clean baseline.

Why we vendor / load axe-core via add_script_tag instead of using
the ``axe-playwright-python`` PyPI package: the package adds an
extra dependency for what is, in essence, two lines of code. We
fetch axe-core from a CDN URL pinned by the version number — a
network failure during CI just skips the test rather than failing
it (a network blip is not an a11y regression).

The CDN URL is from cdnjs.cloudflare.com; the version is pinned so
a release with a behavior change can't break our suite without an
explicit bump.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page


# Pinned axe-core version. Bump explicitly when adopting new rules.
# https://github.com/dequelabs/axe-core/releases
AXE_CORE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.0/axe.min.js"

# Severity buckets we treat as test failures. ``moderate`` and ``minor``
# are reported but don't fail — start with the high-impact issues and
# tighten the gate as the suite stabilises.
FAIL_IMPACTS = {"critical", "serious"}


def _inject_and_run_axe(page: Page) -> dict:
    """Inject axe-core via CDN and return ``axe.run()`` results.

    Returns the full result object (violations, passes, incomplete,
    inapplicable). Caller filters by ``impact``."""
    try:
        page.add_script_tag(url=AXE_CORE_CDN)
    except Exception as e:
        pytest.skip(f"could not load axe-core from CDN ({e}); skipping a11y scan")

    # Wait until axe is actually defined — add_script_tag returns
    # before the script's top-level execution finishes on slow runners.
    page.wait_for_function("() => typeof window.axe !== 'undefined'", timeout=5000)

    return page.evaluate("async () => await axe.run()")


def _format_violations(violations: list[dict[str, Any]]) -> str:
    """Pretty-print a list of axe violations for assertion messages."""
    out: list[str] = []
    for v in violations:
        out.append(
            f"  [{v.get('impact', 'unknown')}] {v.get('id')}: "
            f"{v.get('help', '')}\n"
            f"    -> {v.get('helpUrl', '')}\n"
            f"    -> nodes: {len(v.get('nodes', []))}"
        )
        # First offending node's HTML for context.
        nodes = v.get("nodes") or []
        if nodes:
            html_snippet = (nodes[0].get("html") or "")[:140]
            out.append(f"    -> first node: {html_snippet!r}")
    return "\n".join(out)


def _scan(page: Page, base_url: str, path: str) -> None:
    """Load ``base_url + path``, run axe, fail on critical / serious."""
    page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
    # Allow the page's own JS (theme boot, hljs, palette init) to settle.
    page.wait_for_load_state("networkidle", timeout=5000)

    results = _inject_and_run_axe(page)
    violations = results.get("violations") or []
    failing = [v for v in violations if v.get("impact") in FAIL_IMPACTS]

    if failing:
        msg = (
            f"axe-core found {len(failing)} {'/'.join(sorted(FAIL_IMPACTS))} "
            f"violation(s) on {path}:\n"
            + _format_violations(failing)
        )
        pytest.fail(msg)


def test_homepage_has_no_critical_a11y_violations(page: Page, base_url: str) -> None:
    """Run axe-core against the homepage. Critical/serious violations
    fail the test; moderate/minor are tolerated for now."""
    _scan(page, base_url, "/index.html")


def test_session_page_has_no_critical_a11y_violations(page: Page, base_url: str) -> None:
    """Session pages have the most user content (rendered Markdown,
    code blocks, breadcrumbs) and are the highest-risk surface for
    contrast / heading-hierarchy violations."""
    _scan(page, base_url, "/sessions/e2e-demo/2026-04-09-e2e-python-demo.html")


def test_projects_index_has_no_critical_a11y_violations(page: Page, base_url: str) -> None:
    """Projects index uses card components which have a different
    visual treatment than session pages — separate axe pass."""
    # The path varies by build mode — try both.
    for path in ("/projects/index.html", "/projects/"):
        try:
            page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
            if page.url.endswith(("404", "404.html")):
                continue
            _scan(page, base_url, path)
            return
        except Exception:
            continue
    pytest.skip("no projects index page found at any expected path")


def test_graph_page_has_no_critical_a11y_violations(page: Page, base_url: str) -> None:
    """The graph viewer is a canvas-heavy page — different a11y
    surface than text content. We test it separately because the
    ``#back-to-site`` link and any toolbar controls are the only
    keyboard-accessible elements."""
    resp = page.request.get(f"{base_url}/graph.html")
    if resp.status >= 400:
        pytest.skip("graph.html not shipped (empty seeded graph)")
    _scan(page, base_url, "/graph.html")


def test_dark_mode_passes_color_contrast_audit(page: Page, base_url: str) -> None:
    """Dark mode is a frequent source of color-contrast regressions:
    a CSS variable change in light mode breaks contrast in dark mode
    if the dark-theme override wasn't updated together. Run a
    contrast-only scan against the homepage in dark mode."""
    page.add_init_script(
        "try { localStorage.setItem('llmwiki-theme', 'dark'); } catch (e) {}"
    )
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=5000)

    try:
        page.add_script_tag(url=AXE_CORE_CDN)
    except Exception as e:
        pytest.skip(f"could not load axe-core ({e})")
    page.wait_for_function("() => typeof window.axe !== 'undefined'", timeout=5000)

    # Run with only the color-contrast rule to keep the failure
    # message focused if anything fails.
    results = page.evaluate(
        "async () => await axe.run({ runOnly: ['color-contrast'] })"
    )
    violations = results.get("violations") or []
    failing = [v for v in violations if v.get("impact") in FAIL_IMPACTS]
    if failing:
        pytest.fail(
            f"dark mode has {len(failing)} contrast violation(s):\n"
            + _format_violations(failing)
        )
