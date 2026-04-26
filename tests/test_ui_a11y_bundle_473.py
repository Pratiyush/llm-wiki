"""#473 UI/UX a11y bundle: pin five small fixes from the Opus UI epic.

Five issues addressed in one PR (closely related single-line CSS / JS /
HTML adjustments that share the same render code path):

  - #565 (#ui-h1): skip-link focus ring + overflow reset on focus
  - #566 (#ui-h4): localStorage access wrapped in try/catch
  - #568 (#ui-h8): aria-expanded + aria-controls on #open-palette;
                   aria-pressed on #theme-toggle
  - #571 (#ui-h14): vis-network pinned to @9.1.9 with SRI hash
  - #564 (#ui-c5): viewport-fit=cover already in meta (verified)

Each fix gets its own focused assertion below.
"""
from __future__ import annotations

import re

from llmwiki.build import nav_bar, page_head
from llmwiki.graph import HTML_TEMPLATE
from llmwiki.render.css import CSS
from llmwiki.render.js import JS


# ─── #565 — skip-link focus ring ──────────────────────────────────────


def test_skip_link_has_visible_focus_ring() -> None:
    """The skip-link `:focus-visible` rule must reset overflow + width
    AND emit a strong outline so keyboard users see where focus
    landed against the accent background."""
    # Match either focus or focus-visible — the rule lists both.
    rule = re.search(
        r"\.skip-link:focus[^{]*\{[^}]*outline:\s*\d+px",
        CSS,
        re.DOTALL,
    )
    assert rule, "skip-link :focus rule missing outline declaration"


# ─── #566 — localStorage try/catch ─────────────────────────────────────


def test_all_localstorage_setitem_calls_wrapped() -> None:
    """Every `localStorage.setItem(...)` in render/js.py must be inside
    a try block — Safari Private Mode + sandboxed iframes throw on
    write, and an unwrapped throw kills the rest of the wiring."""
    # Find every setItem call site; ensure each appears within ~120
    # chars after a `try {` keyword.
    for m in re.finditer(r"localStorage\.setItem\(", JS):
        prefix = JS[max(0, m.start() - 250) : m.start()]
        assert "try {" in prefix or "try{" in prefix, (
            f"unwrapped localStorage.setItem at offset {m.start()}; "
            f"context: {prefix[-120:]!r}"
        )


def test_main_localstorage_getitem_wrapped() -> None:
    """The pre-paint theme reader at the top of the script must catch
    SecurityError so a private-mode visitor still gets a usable page
    (just without theme persistence)."""
    # The header reader sequence: `let saved = null; try { saved = localStorage.getItem(...) } catch (e) {...}`.
    block = JS[: JS.find("syncHljsTheme();")]
    assert "try { saved = localStorage.getItem" in block or \
        re.search(r"try\s*\{\s*saved\s*=\s*localStorage\.getItem", block), \
        "main theme-reader localStorage.getItem must be wrapped in try"


# ─── #568 — aria-expanded / aria-controls / aria-pressed ───────────────


def test_palette_button_has_aria_expanded_and_controls() -> None:
    nav = nav_bar(active="home")
    assert 'id="open-palette"' in nav
    assert 'aria-expanded="false"' in nav
    assert 'aria-controls="palette"' in nav
    assert 'aria-haspopup="dialog"' in nav


def test_theme_button_has_aria_pressed() -> None:
    nav = nav_bar(active="home")
    assert 'id="theme-toggle"' in nav
    assert 'aria-pressed=' in nav
    # JS keeps the value in sync with data-theme.
    assert 'syncAriaPressed' in JS
    assert 'aria-pressed' in JS


def test_open_palette_aria_expanded_flips_on_open() -> None:
    """When the palette opens, the trigger's aria-expanded must flip
    to true so AT users hear the right state when they refocus the
    button. The __syncTriggerAriaExpanded helper drives this from
    inside __openDialog/__closeDialog."""
    assert "__syncTriggerAriaExpanded" in JS
    open_block = JS[JS.find("function __openDialog"): JS.find("function __closeDialog")]
    close_block = JS[JS.find("function __closeDialog"): JS.find("function __closeDialog") + 600]
    assert "__syncTriggerAriaExpanded(dialog, true)" in open_block
    assert "__syncTriggerAriaExpanded(dialog, false)" in close_block


# ─── #571 — vis-network pinned + SRI ───────────────────────────────────


def test_vis_network_version_pinned() -> None:
    """The bare `unpkg.com/vis-network/standalone/...` URL pulls latest
    on every load — a malicious or accidental upstream change ships
    JS to every site visitor. Pin to an explicit version."""
    assert "unpkg.com/vis-network/" not in HTML_TEMPLATE, (
        "vis-network is loaded without a version pin; supply-chain risk"
    )
    assert re.search(r"vis-network@\d+\.\d+\.\d+/standalone", HTML_TEMPLATE), (
        "vis-network must be pinned to a specific @x.y.z version"
    )


def test_vis_network_has_sri_integrity() -> None:
    """SRI hash gates the load — wrong hash → browser refuses to
    execute. Combined with the version pin this prevents an attacker
    who compromises the registry from running code in the browser."""
    assert 'integrity="sha384-' in HTML_TEMPLATE
    assert 'crossorigin="anonymous"' in HTML_TEMPLATE


# ─── #564 — viewport-fit=cover ─────────────────────────────────────────


def test_viewport_fit_cover_present() -> None:
    """iOS Safari needs viewport-fit=cover for env(safe-area-inset-*)
    to resolve to non-zero on devices with a home indicator. Without
    it, `padding-bottom: calc(... + env(safe-area-inset-bottom))` in
    the mobile bottom nav resolves to 0 and the bar lands on top of
    the system gesture area."""
    head = page_head("Title", "Description")
    assert "viewport-fit=cover" in head
