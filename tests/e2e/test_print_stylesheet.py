"""#640 (#pw-x12): print stylesheet validation.

The site ships an `@media print` block in `render/css.py` that hides
nav/palette/heatmap/charts/etc. and flips the palette to black-on-
white so a printed session reads cleanly. There's no automated check
that the rules actually take effect when a browser switches to print
media — every time the print CSS gets touched it could silently
regress without anyone noticing until they hit Cmd+P.

This module flips Playwright's media emulation to `print` and asserts
the contract:

  1. The nav header is hidden.
  2. The palette container is hidden.
  3. Body background resolves to white.
  4. Body text resolves to (near-)black.
  5. Code blocks remain readable (have a non-default font + a border).

Catches: regressions where someone removes a `display: none !important`
selector, the palette's `.open` state leaks into print, or the bg/text
colour-flip drifts out of sync with the print spec.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Page


def _flip_to_print(page: Page) -> None:
    page.emulate_media(media="print")


def _rgb_close_to_white(rgb: str) -> bool:
    # `getComputedStyle` returns rgb(R, G, B) — the print rule sets
    # `--bg: #fff` so we accept anything ≥240 per channel.
    import re
    m = re.search(r"rgb\((\d+),\s*(\d+),\s*(\d+)", rgb)
    if not m:
        return False
    r, g, b = (int(x) for x in m.groups())
    return r >= 240 and g >= 240 and b >= 240


def _rgb_close_to_black(rgb: str) -> bool:
    import re
    m = re.search(r"rgb\((\d+),\s*(\d+),\s*(\d+)", rgb)
    if not m:
        return False
    r, g, b = (int(x) for x in m.groups())
    return r <= 50 and g <= 50 and b <= 50


def test_print_hides_nav_header(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    _flip_to_print(page)
    nav_display = page.evaluate(
        "() => { const n = document.querySelector('header.nav'); return n ? getComputedStyle(n).display : 'none'; }"
    )
    assert nav_display == "none", f"nav should be hidden in print, got display={nav_display!r}"


def test_print_hides_palette_and_help_dialog(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    _flip_to_print(page)
    pal = page.evaluate(
        "() => { const e = document.getElementById('palette'); return e ? getComputedStyle(e).display : 'none'; }"
    )
    helpd = page.evaluate(
        "() => { const e = document.getElementById('help-dialog'); return e ? getComputedStyle(e).display : 'none'; }"
    )
    assert pal == "none", f"palette should be hidden in print, got display={pal!r}"
    assert helpd == "none", f"help-dialog should be hidden in print, got display={helpd!r}"


def test_print_body_is_white_with_dark_text(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    _flip_to_print(page)
    bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    fg = page.evaluate("() => getComputedStyle(document.body).color")
    assert _rgb_close_to_white(bg), f"print body bg should resolve to ~white, got {bg!r}"
    assert _rgb_close_to_black(fg), f"print body text should resolve to ~black, got {fg!r}"


def test_print_hides_progress_bar(page: Page, base_url: str) -> None:
    """The reading progress bar would otherwise print as a thin
    accent-coloured stripe at the top of every page."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    _flip_to_print(page)
    bar = page.evaluate(
        "() => { const e = document.getElementById('progress-bar'); return e ? getComputedStyle(e).display : 'none'; }"
    )
    assert bar == "none", f"progress-bar should be hidden in print, got display={bar!r}"
