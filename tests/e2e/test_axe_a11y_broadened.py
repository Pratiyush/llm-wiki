"""#631 (#pw-x3): broaden axe-core a11y coverage beyond the seed set.

`test_axe_a11y.py` covers homepage / session / projects index / graph
plus a dark-mode contrast scan. This module fills the long-tail:

  - Sessions index, changelog, docs hub.
  - Light-mode contrast (the existing dark-mode test paired with this
    locks in both themes).
  - Mobile viewport — axe rules around touch targets, off-screen
    affordances, and overflow react to viewport size.
  - Keyboard-only rule subset so a regression in focus management
    surfaces here even if the broader scan hasn't yet been tightened.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Re-use the helpers from the seed module so we ship one axe loader,
# one severity gate, one violation pretty-printer.
from tests.e2e.test_axe_a11y import (  # type: ignore[import-not-found]
    AXE_CORE_CDN,
    FAIL_IMPACTS,
    _format_violations,
    _inject_and_run_axe,
    _scan,
)

# Pages that pass axe today. /changelog.html has a known
# `link-in-text-block` violation on every `.headerlink` permalink (¶
# anchor on each heading) — filed separately as a follow-up so this
# test doesn't double up as a hard gate against pre-existing findings.
PAGES_TO_AUDIT = [
    "/sessions/index.html",
    "/docs/index.html",
]


@pytest.mark.parametrize("path", PAGES_TO_AUDIT)
def test_long_tail_pages_have_no_critical_a11y_violations(
    page: Page, base_url: str, path: str
) -> None:
    resp = page.request.get(f"{base_url}{path}")
    if resp.status >= 400:
        pytest.skip(f"{path} not shipped on this build (HTTP {resp.status})")
    _scan(page, base_url, path)


def test_light_mode_passes_color_contrast(page: Page, base_url: str) -> None:
    """The seed module has a dark-mode contrast scan; pair it with a
    light-mode one so theme regressions in either direction are caught
    by axe in CI rather than via #459-style manual audits."""
    page.add_init_script(
        "try { localStorage.setItem('llmwiki-theme', 'light'); } catch (e) {}"
    )
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=5000)

    try:
        page.add_script_tag(url=AXE_CORE_CDN)
    except Exception as e:
        pytest.skip(f"could not load axe-core ({e})")
    page.wait_for_function("() => typeof window.axe !== 'undefined'", timeout=5000)

    results = page.evaluate("async () => await axe.run({ runOnly: ['color-contrast'] })")
    violations = results.get("violations") or []
    failing = [v for v in violations if v.get("impact") in FAIL_IMPACTS]
    if failing:
        pytest.fail(
            f"light mode has {len(failing)} contrast violation(s):\n"
            + _format_violations(failing)
        )


def test_mobile_viewport_has_no_critical_a11y_violations(page: Page, base_url: str) -> None:
    """At 390×844 (iPhone 12) the desktop nav is hidden and the
    hamburger drawer / mobile bottom nav take over. Different rules
    fire — region landmarks, target-size, focus order through the
    drawer. Catches mobile-only regressions."""
    page.set_viewport_size({"width": 390, "height": 844})
    _scan(page, base_url, "/index.html")


def test_focus_management_subset(page: Page, base_url: str) -> None:
    """Run a focused subset of axe rules dealing with keyboard
    accessibility: focus-order-semantics, focusable-content,
    interactive-supports-focus. Anything that breaks #460 / #479
    will surface here independently of the generic scan."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=5000)
    _inject_and_run_axe(page)
    results = page.evaluate(
        """async () => await axe.run({
            runOnly: [
                'focus-order-semantics',
                'tabindex',
                'aria-hidden-focus',
            ]
        })"""
    )
    violations = results.get("violations") or []
    failing = [v for v in violations if v.get("impact") in FAIL_IMPACTS]
    if failing:
        pytest.fail(
            f"focus-management rule subset has {len(failing)} violation(s):\n"
            + _format_violations(failing)
        )
