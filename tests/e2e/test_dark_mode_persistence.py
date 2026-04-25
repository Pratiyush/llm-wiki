"""Dark-mode persistence across reloads + system preference handling.

The existing ``test_theme_toggle.py`` covers the immediate toggle —
click the button, assert ``data-theme`` flips. That misses three
real-world regression classes:

1. **Persistence**: user toggles dark, refreshes the page, theme
   resets to light. (localStorage write didn't fire, or the boot
   script reads it incorrectly.)
2. **System preference fallback**: user has zero localStorage but
   ``prefers-color-scheme: dark`` in their OS — we should respect it
   on first paint without a flash of light theme.
3. **highlight.js sync**: the page ships two hljs stylesheets
   (#hljs-light, #hljs-dark) and toggles ``disabled`` on each based
   on the active theme. A regression that flips the wrong one leaves
   code blocks looking wrong even though the rest of the page reads
   fine.

This file covers all three.
"""

from __future__ import annotations

from playwright.sync_api import Page, BrowserContext, expect


def _get_theme(page: Page) -> str:
    """Return the active ``data-theme`` value on <html>."""
    return page.evaluate("() => document.documentElement.getAttribute('data-theme')") or ""


def _set_localstorage_theme(page: Page, theme: str) -> None:
    """Set the persisted theme key BEFORE the next navigation. We use
    ``add_init_script`` because localStorage on about:blank throws."""
    page.add_init_script(
        f"try {{ localStorage.setItem('llmwiki-theme', {theme!r}); }} catch (e) {{}}"
    )


def test_theme_persists_across_reload(page: Page, base_url: str) -> None:
    """User flips to dark, refreshes — theme should still be dark.
    Catches the regression where the toggle handler fires but skips
    the localStorage write."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    initial = _get_theme(page)

    # Click the toggle exactly once.
    toggle = page.locator("#theme-toggle").first
    expect(toggle).to_be_visible()
    toggle.click()

    after_toggle = _get_theme(page)
    assert after_toggle != initial, (
        f"clicking #theme-toggle didn't change data-theme (was {initial!r}, "
        f"still {after_toggle!r})"
    )

    # Reload + assert the toggled value is still active.
    page.reload(wait_until="domcontentloaded")
    after_reload = _get_theme(page)
    assert after_reload == after_toggle, (
        f"theme didn't persist: was {after_toggle!r} pre-reload, "
        f"now {after_reload!r} — localStorage write failed?"
    )


def test_theme_respects_prefers_color_scheme_when_unset(
    context: BrowserContext, base_url: str
) -> None:
    """First-time visitor with no localStorage value should see the
    theme that matches their OS preference. We emulate
    ``prefers-color-scheme: dark`` and assert the boot script picks
    it up."""
    # Open a brand-new context with the dark color-scheme media
    # query. Using a fresh context guarantees no localStorage
    # carries over from a prior test.
    page = context.new_page()
    try:
        page.emulate_media(color_scheme="dark")
        # Clear any persisted value the harness may have leaked.
        page.add_init_script(
            "try { localStorage.removeItem('llmwiki-theme'); } catch (e) {}"
        )
        page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
        theme = _get_theme(page)
        # The boot script may either set data-theme="dark" or leave
        # it absent and rely on @media (prefers-color-scheme: dark)
        # in CSS. Both are valid implementations — we only fail when
        # the script *forces* light despite the media query.
        assert theme != "light", (
            f"with prefers-color-scheme=dark and no localStorage, "
            f"data-theme was {theme!r} — boot script ignored OS preference"
        )
    finally:
        page.close()


def test_explicit_localstorage_overrides_system_preference(
    context: BrowserContext, base_url: str
) -> None:
    """User explicitly chose light despite OS dark mode (or vice versa).
    The persisted value MUST win over ``prefers-color-scheme``.
    Reverse: a regression that prioritises the OS preference over
    the user's own choice is a real UX bug — users should not have
    to re-pick their theme every time their OS theme changes."""
    page = context.new_page()
    try:
        page.emulate_media(color_scheme="dark")
        # Force a "user chose light" persisted value.
        _set_localstorage_theme(page, "light")
        page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
        theme = _get_theme(page)
        assert theme == "light", (
            f"localStorage said light, OS said dark, page rendered as "
            f"{theme!r} — user preference must win"
        )
    finally:
        page.close()


def test_highlightjs_stylesheet_disabled_state_matches_theme(page: Page, base_url: str) -> None:
    """The page ships two hljs stylesheets (#hljs-light, #hljs-dark)
    with one ``disabled`` based on the active theme. After a toggle,
    the disabled flag must flip in the opposite direction."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")

    def _disabled(selector: str) -> bool:
        return page.evaluate(
            f"() => !!document.querySelector({selector!r})?.disabled"
        )

    # Skip if the page doesn't ship dual hljs stylesheets.
    has_light = page.locator("#hljs-light").count() > 0
    has_dark = page.locator("#hljs-dark").count() > 0
    if not (has_light and has_dark):
        import pytest
        pytest.skip("dual hljs stylesheets not present on this build")

    # Snapshot the initial state.
    init_light = _disabled("#hljs-light")
    init_dark = _disabled("#hljs-dark")
    # Exactly one should be disabled.
    assert init_light != init_dark, (
        f"both hljs stylesheets have disabled={init_light}/{init_dark} "
        f"— code blocks will render with both themes layered"
    )

    # Toggle and re-check.
    page.locator("#theme-toggle").first.click()
    after_light = _disabled("#hljs-light")
    after_dark = _disabled("#hljs-dark")
    assert after_light != after_dark, (
        f"after toggle, hljs disabled state is light={after_light} "
        f"dark={after_dark} — at least one must be disabled"
    )
    # And the flag must have flipped on each.
    assert after_light != init_light, "#hljs-light disabled state did not flip on theme toggle"
    assert after_dark != init_dark, "#hljs-dark disabled state did not flip on theme toggle"


def test_theme_toggle_button_has_accessible_name(page: Page, base_url: str) -> None:
    """The toggle is icon-only on most viewports — without an
    aria-label or visible text it's invisible to screen readers."""
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    toggle = page.locator("#theme-toggle").first
    expect(toggle).to_be_visible()
    label = toggle.get_attribute("aria-label") or toggle.inner_text() or ""
    assert label.strip(), (
        "#theme-toggle has no aria-label and no visible text — "
        "screen readers will announce it as 'button' with no context"
    )
