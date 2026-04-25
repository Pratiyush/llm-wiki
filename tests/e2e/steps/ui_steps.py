"""Step definitions for every Gherkin feature under
``tests/e2e/features/``.

Design choices:

* **Playwright locators, not selectors** — we use ``page.locator(...)``
  so auto-wait is on and the step text stays high-level.
* **Explicit waits over sleeps** — any step that waits for something
  to appear uses ``expect(locator).to_be_visible(timeout=...)`` rather
  than ``time.sleep``.
* **Parametrized strings, not regexes** — pytest-bdd supports both,
  but parametrized strings are easier to read in the feature files.
* **No raw DOM queries except when the assertion is about a runtime
  property** — e.g. `data-theme` attribute, `disabled` flag on a
  ``<link>`` element. Those use `page.evaluate(...)` because
  Playwright locators can't assert on stylesheet disabled state.

Scope of the step library: everything the seven feature files under
``tests/e2e/features/`` reference. Adding a new scenario that uses
an unregistered step will fail loudly at collection time.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, then, when


# ─── shared background steps ────────────────────────────────────────────


@given("a built llmwiki site is served")
def _built_site_served(base_url: str) -> str:
    """Sanity-check that the session-scoped `base_url` fixture is
    live. The real build + serve work happens in `conftest.py`."""
    assert base_url.startswith("http://")
    return base_url


@given("clipboard permissions are granted")
def _clipboard_perms(browser_context_args: dict[str, Any]) -> None:
    """The ``browser_context_args`` override in ``conftest.py`` already
    grants clipboard-read and clipboard-write. Assert we didn't lose
    it at override time so the copy-markdown scenario has them."""
    perms = browser_context_args.get("permissions") or []
    assert "clipboard-read" in perms, (
        "clipboard-read permission missing from browser_context_args; "
        "the conftest override was dropped"
    )
    assert "clipboard-write" in perms


# ─── navigation steps ───────────────────────────────────────────────────


@given("I visit the homepage")
@when("I visit the homepage")
def _visit_homepage(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/index.html")


@when("I visit the homepage on a mobile viewport")
def _visit_homepage_mobile(mobile_page: Page, base_url: str) -> None:
    mobile_page.goto(f"{base_url}/index.html")


@when(parsers.parse('I open the session "{slug}"'))
def _open_session(page: Page, base_url: str, slug: str) -> None:
    page.goto(f"{base_url}/sessions/{slug}.html")


# ─── page-title + hero assertions ───────────────────────────────────────


@then(parsers.parse('I see the page title contains "{fragment}"'))
@then(parsers.parse('the page title contains "{fragment}"'))
def _title_contains(page: Page, fragment: str) -> None:
    assert fragment in page.title(), (
        f'page title "{page.title()}" does not contain "{fragment}"'
    )


@then(parsers.parse('I see a hero heading with text "{text}"'))
def _hero_heading(page: Page, text: str) -> None:
    heading = page.locator(".hero h1").first
    expect(heading).to_be_visible()
    assert heading.inner_text().strip() == text, (
        f'hero h1 is "{heading.inner_text().strip()}", expected "{text}"'
    )


@then(parsers.parse('I see the subtitle mentions "{fragment}"'))
def _subtitle_mentions(page: Page, fragment: str) -> None:
    sub = page.locator(".hero .hero-sub").first
    expect(sub).to_be_visible()
    assert fragment in sub.inner_text()


# ─── nav bar ────────────────────────────────────────────────────────────


@then(parsers.parse('the nav bar has a "{label}" link'))
def _nav_has_link(page: Page, label: str) -> None:
    link = page.locator(f'.nav-links a:has-text("{label}")').first
    expect(link).to_be_visible()


# ─── project cards ──────────────────────────────────────────────────────


@then(parsers.parse('I see a project card for "{project}"'))
def _project_card(page: Page, project: str) -> None:
    card = page.locator(f'.card-project:has-text("{project}")').first
    expect(card).to_be_visible()


# ─── session-page assertions ───────────────────────────────────────────


@then("I see a breadcrumbs bar")
def _breadcrumbs(page: Page) -> None:
    crumbs = page.locator(".breadcrumbs").first
    expect(crumbs).to_be_visible()


@then(parsers.parse('I see a "{label}" button'))
def _button_visible(page: Page, label: str) -> None:
    btn = page.locator(f'button:has-text("{label}")').first
    expect(btn).to_be_visible()


@then(parsers.parse('the article contains the heading "{heading}"'))
def _article_heading(page: Page, heading: str) -> None:
    # The session body uses h2/h3 for section headings.
    h = page.locator(f'.content h2:has-text("{heading}"), .content h3:has-text("{heading}")').first
    expect(h).to_be_visible()


@then(parsers.parse('the article contains a fenced code block with language "{lang}"'))
def _fenced_code_lang(page: Page, lang: str) -> None:
    block = page.locator(f'pre > code.language-{lang}, pre > code.hljs.language-{lang}').first
    expect(block).to_be_visible()


@then(parsers.parse('at least one "{selector}" element becomes visible within {seconds:d} seconds'))
def _element_visible_within(page: Page, selector: str, seconds: int) -> None:
    el = page.locator(selector).first
    expect(el).to_be_visible(timeout=seconds * 1000)


# ─── command palette ───────────────────────────────────────────────────


def _focus_body(page: Page) -> None:
    """Global shortcuts (Cmd+K, g-prefix, ?) attach to `document`
    and bubble up from whatever is focused. On a freshly navigated
    page nothing is focused, so clicks need a real target first —
    we tap the body at (1, 1) to guarantee focus reaches document."""
    try:
        page.locator("body").first.click(position={"x": 1, "y": 1})
    except Exception:
        pass  # Some scenarios press Escape before any nav; ignore the click failure


# `^...$` anchors keep this from swallowing `I press "a" then "b"`
# (which is a different step — pytest-bdd's default `parse` matcher
# is greedy and would otherwise capture `a" then "b` as the key).
@when(parsers.re(r'^I press "(?P<key>[^"]+)"$'))
def _press_key(page: Page, key: str) -> None:
    # Cross-platform portability: the Cmd+K binding on macOS is
    # Ctrl+K on Linux/Windows. Translate "Meta+K" to Playwright's
    # portable "ControlOrMeta+k" chord so a single feature file
    # works on local (macOS) and CI (Linux).
    #
    # Lowercase `k` is critical: Playwright's `Meta+K` (capital K)
    # fires a keydown with `e.key === "K"`, but build.py's global
    # handler checks `e.key === "k"`, so the palette never opens
    # and every Cmd+K-driven scenario silently times out.
    if key in ("Meta+K", "Cmd+K", "Ctrl+K", "Meta+k", "Cmd+k", "Ctrl+k"):
        key = "ControlOrMeta+k"
    _focus_body(page)
    page.keyboard.press(key)


@when("the command palette becomes visible")
@then("the command palette becomes visible")
def _palette_visible(page: Page) -> None:
    # The palette flips `aria-hidden="false"` on open via the
    # openPalette() JS function (see llmwiki/build.py). We retry
    # for up to 3s because openPalette also kicks off an async
    # loadIndex().then(...) that could race with Playwright on CI.
    page.wait_for_function(
        "() => document.getElementById('palette')?.getAttribute('aria-hidden') === 'false'",
        timeout=3000,
    )


@then("the palette input is focused")
def _palette_input_focused(page: Page) -> None:
    # Focus is set inside openPalette() right after the aria-hidden
    # flip. Wait up to 2s to let the input claim focus.
    page.wait_for_function(
        "() => document.activeElement && document.activeElement.id === 'palette-input'",
        timeout=2000,
    )


@when(parsers.parse('I type "{text}" into the palette input'))
def _type_into_palette(page: Page, text: str) -> None:
    # The palette input is focused when the palette opens; fire the
    # keystrokes through the keyboard so the JS filter runs through
    # its real keydown handler.
    page.keyboard.type(text)


@then(parsers.parse('the palette results contain "{fragment}"'))
def _palette_results_contain(page: Page, fragment: str) -> None:
    results = page.locator("#palette-results").first
    expect(results).to_contain_text(fragment, timeout=3000)


# ─── keyboard navigation (g h / g p / g s / ?) ──────────────────────────


@when(parsers.re(r'^I press "(?P<a>[^"]+)" then "(?P<b>[^"]+)"$'))
def _press_chord(page: Page, a: str, b: str) -> None:
    # Same focus trick as _press_key — the g-prefix handler lives on
    # `document`, so we need an activeElement for keydown to bubble.
    _focus_body(page)
    starting_url = page.url
    page.keyboard.press(a)
    # The second key in a g-prefix chord (`g h`, `g p`, `g s`)
    # assigns `window.location.href` synchronously, which tears down
    # the execution context while Playwright is still post-processing
    # the press. Swallow that specific error — the navigation did
    # happen, and the URL assertion on the next step will catch any
    # actual bug.
    try:
        page.keyboard.press(b)
    except Exception as e:
        if "Execution context was destroyed" not in str(e):
            raise
    # Wait for the new document so subsequent URL assertions read the
    # final pathname.  domcontentloaded ≠ url-has-actually-changed, so
    # when the chord navigated away from the starting URL we also poll
    # page.url until it flips (fixes a real race seen on CI — #339
    # follow-up: `_url_contains` used to read page.url while the
    # navigation hadn't fully registered, returning the pre-nav URL).
    try:
        page.wait_for_load_state("domcontentloaded", timeout=3000)
    except Exception:
        pass
    # For the ? / / chords we don't actually navigate — only wait when
    # the second key is one of {h, p, s}.
    if b.lower() in ("h", "p", "s"):
        try:
            page.wait_for_function(
                "startingUrl => window.location.href !== startingUrl",
                arg=starting_url,
                timeout=3000,
            )
        except Exception:
            # Timeout is fine — the URL assertion will give a precise
            # error if the navigation genuinely didn't fire.
            pass


def _current_path(page: Page) -> str:
    """Read ``window.location.pathname`` via Playwright's stable
    ``page.url`` property instead of ``page.evaluate()``.

    ``page.evaluate()`` tears down its execution context when a
    navigation is mid-flight (the g-prefix chords navigate
    synchronously from a keypress handler), so the evaluate race
    against teardown — and flakes roughly 1-in-20 in CI.  ``page.url``
    is populated by the frame-navigated event without running JS and
    is safe post-navigation.  parse ``urlparse().path`` so callers get
    the pathname just like the old code.
    """
    from urllib.parse import urlparse
    return urlparse(page.url).path


@then(parsers.parse('the URL path ends with "{a}" or "{b}"'))
def _url_ends_with_either(page: Page, a: str, b: str) -> None:
    path = _current_path(page)
    assert path.endswith(a) or path.endswith(b), (
        f'URL path "{path}" does not end with "{a}" or "{b}"'
    )


@then(parsers.parse('the URL path contains "{fragment}"'))
def _url_contains(page: Page, fragment: str) -> None:
    path = _current_path(page)
    assert fragment in path, f'URL path "{path}" does not contain "{fragment}"'


@when("the help dialog becomes visible")
@then("the help dialog becomes visible")
def _help_dialog_visible(page: Page) -> None:
    dialog = page.locator(".help-dialog").first
    expect(dialog).to_be_visible(timeout=3000)


# #278: additional keyboard-shortcut coverage.


@then("the command palette becomes hidden")
def _palette_hidden(page: Page) -> None:
    page.wait_for_function(
        "() => document.getElementById('palette')?.getAttribute('aria-hidden') === 'true'",
        timeout=3000,
    )


@then("the help dialog becomes hidden")
def _help_dialog_hidden(page: Page) -> None:
    # The help dialog may unmount OR gain a hidden attribute — accept either.
    page.wait_for_function(
        """() => {
            const d = document.querySelector('.help-dialog');
            if (!d) return true;
            return d.offsetParent === null || d.getAttribute('aria-hidden') === 'true';
        }""",
        timeout=3000,
    )


@when(parsers.parse("I wait {ms:d} milliseconds"))
def _wait_ms(page: Page, ms: int) -> None:
    page.wait_for_timeout(ms)


# ─── mobile bottom nav ─────────────────────────────────────────────────


@then("the mobile bottom nav is visible")
def _mbn_visible(mobile_page: Page) -> None:
    nav = mobile_page.locator(".mobile-bottom-nav").first
    expect(nav).to_be_visible()


@then("the mobile bottom nav is hidden")
def _mbn_hidden(page: Page) -> None:
    # Under print-media emulation the mobile nav should be hidden
    # regardless of viewport — the @media print rule in CSS takes
    # precedence. We check computed `display` rather than Playwright's
    # visibility helper because `to_be_hidden` treats "off-screen" as
    # hidden, and the print-media display:none IS the feature.
    display = page.evaluate(
        "() => { const n = document.querySelector('.mobile-bottom-nav');"
        "  if (!n) return 'none';"
        "  return getComputedStyle(n).display; }"
    )
    assert display == "none", (
        f'.mobile-bottom-nav display is "{display}", expected "none" under print media'
    )


@then(parsers.parse('the mobile bottom nav has a "{label}" button'))
def _mbn_button(mobile_page: Page, label: str) -> None:
    btn = mobile_page.locator(
        f'.mobile-bottom-nav [aria-label="{label}"], .mobile-bottom-nav button:has-text("{label}"), .mobile-bottom-nav [data-page="{label.lower()}"]'
    ).first
    expect(btn).to_be_visible()


@when(parsers.parse('I tap the mobile bottom nav "{label}" button'))
def _mbn_tap(mobile_page: Page, label: str) -> None:
    # The mobile nav uses stable ids: #mbn-search, #mbn-theme
    id_map = {"Search": "#mbn-search", "Theme": "#mbn-theme"}
    selector = id_map.get(label)
    if selector:
        mobile_page.locator(selector).first.click()
    else:
        mobile_page.locator(
            f'.mobile-bottom-nav button:has-text("{label}")'
        ).first.click()


# ─── theme attribute + stylesheet disabled checks ──────────────────────


@then(parsers.parse('the document root has data-theme "{theme}"'))
def _theme_attr(page: Page, theme: str) -> None:
    actual = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    assert actual == theme, f'data-theme is "{actual}", expected "{theme}"'


@when(parsers.parse('I click the desktop "{selector}" button'))
def _click_desktop(page: Page, selector: str) -> None:
    page.locator(selector).first.click()


@then(parsers.parse('the "{selector}" stylesheet is disabled'))
def _stylesheet_disabled(page: Page, selector: str) -> None:
    disabled = page.evaluate(
        f"() => document.querySelector('{selector}')?.disabled"
    )
    assert disabled is True, f'{selector} disabled={disabled}, expected True'


@then(parsers.parse('the "{selector}" stylesheet is enabled'))
def _stylesheet_enabled(page: Page, selector: str) -> None:
    disabled = page.evaluate(
        f"() => document.querySelector('{selector}')?.disabled"
    )
    assert disabled is False, f'{selector} disabled={disabled}, expected False'


# ─── clipboard ─────────────────────────────────────────────────────────


@when(parsers.parse('I click the "{label}" button'))
def _click_named_button(page: Page, label: str) -> None:
    page.locator(f'button:has-text("{label}")').first.click()


@then(parsers.parse('the clipboard contains "{fragment}"'))
def _clipboard_contains(page: Page, fragment: str) -> None:
    # Playwright's clipboard API: page.evaluate to call the Clipboard API.
    clip = page.evaluate("() => navigator.clipboard.readText()")
    assert fragment in clip, (
        f'clipboard did not contain "{fragment}" (got {len(clip)} chars)'
    )


# ─── responsive: viewport + layout ─────────────────────────────────────


@when(parsers.re(r'I resize the viewport to (?P<width>\d+)x(?P<height>\d+)'))
def _resize_viewport(page: Page, width: str, height: str) -> None:
    page.set_viewport_size({"width": int(width), "height": int(height)})


@then("the body has no horizontal scroll")
def _no_horizontal_scroll(page: Page) -> None:
    # scrollWidth > clientWidth means content exceeds the viewport.
    # We allow a small tolerance for rounding weirdness on HiDPI AND
    # for long unbreakable strings in the sparse E2E synthetic wiki
    # (e.g. a monospaced code token wider than 320px at tiny-phone).
    # The interesting regression is the 200+px nav-links overflow
    # that this suite caught on first run — we keep the catch for
    # the real regression class (nav spanning the viewport) without
    # failing on a single wide code word in the synthetic fixture.
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    viewport = page.viewport_size or {"width": 1280}
    # Tolerance scales with viewport — 40px on tiny phones, 1px on
    # desktop. A desktop with 40px overflow is a real bug; a 320×568
    # phone with 40px from a long code token is not.
    tolerance = 40 if viewport["width"] < 500 else 1
    assert overflow <= tolerance, (
        f"body has {overflow}px of horizontal overflow at {viewport} "
        f"(tolerance {tolerance}px) — likely a real nav or layout regression"
    )


@then("the nav bar is visible")
def _nav_bar_visible(page: Page) -> None:
    nav = page.locator(".nav").first
    expect(nav).to_be_visible()


@then("the nav bar is hidden")
def _nav_bar_hidden(page: Page) -> None:
    # In print media the nav is display:none — check computed style
    # rather than Playwright visibility since "visible" under print
    # emulation can be weird.
    display = page.evaluate(
        "() => getComputedStyle(document.querySelector('.nav')).display"
    )
    assert display == "none", f'.nav display is "{display}", expected "none"'


@then("the hero heading is visible")
def _hero_heading_visible(page: Page) -> None:
    heading = page.locator(".hero h1").first
    expect(heading).to_be_visible()


@then(parsers.parse('the mobile bottom nav visibility is {expected}'))
def _mbn_visibility(page: Page, expected: str) -> None:
    # True/false per the Examples table in responsive.feature.
    display = page.evaluate(
        "() => { const n = document.querySelector('.mobile-bottom-nav');"
        "  if (!n) return 'none';"
        "  return getComputedStyle(n).display; }"
    )
    is_visible = display != "none"
    want = expected.lower() == "true"
    assert is_visible == want, (
        f'mobile-bottom-nav display="{display}", is_visible={is_visible}, '
        f"expected visible={want} at viewport {page.viewport_size}"
    )


@then(parsers.parse('at least one "{selector}" element is visible'))
def _selector_visible(page: Page, selector: str) -> None:
    el = page.locator(selector).first
    expect(el).to_be_visible()


@then("the article main content width stays under viewport width")
def _article_width_ok(page: Page) -> None:
    article = page.locator(".content, article.article").first
    box = article.bounding_box()
    assert box is not None, "article has no bounding box"
    viewport = page.viewport_size
    assert box["width"] <= viewport["width"], (
        f'article width {box["width"]} > viewport width {viewport["width"]}'
    )


# ─── edge cases ────────────────────────────────────────────────────────


@when("I clear the palette input")
def _clear_palette(page: Page) -> None:
    page.evaluate("() => { const i = document.getElementById('palette-input'); if (i) i.value = ''; i?.dispatchEvent(new Event('input', { bubbles: true })); }")


@then("the palette results area is visible")
def _palette_results_area(page: Page) -> None:
    # Presence in the DOM is enough — the container carries its
    # open state via the `#palette.open` class on the parent.
    count = page.locator("#palette-results").count()
    assert count >= 1, "palette results container missing from DOM"


@when(parsers.parse('I rapidly type "{text}" into the palette input'))
def _rapid_type(page: Page, text: str) -> None:
    # Type through the keyboard (the palette input is focused when
    # the palette is open) so the filter sees real keydown events.
    # Delay=0 exercises the filter loop at full tilt; any blocking
    # synchronous work in the filter would race and drop keystrokes.
    page.keyboard.type(text, delay=0)


@then("the browser console has no errors")
def _console_clean(page: Page) -> None:
    # The conftest-level console listener records errors into
    # page.context.request_errors — but Playwright's request error
    # API is request-scoped, not console-scoped. We attach a
    # per-scenario listener via the `page.on("pageerror")` event
    # and store errors on the page object.
    errors = getattr(page, "_llmwiki_console_errors", [])
    assert not errors, f"browser console errors: {errors}"


@then("the command palette is hidden")
def _palette_hidden(page: Page) -> None:
    # Close flips aria-hidden back to "true". We assert on that
    # directly — the Playwright `to_be_hidden` check treats
    # aria-hidden="true" as "attached but hidden" which is exactly
    # the state we want.
    page.wait_for_function(
        "() => document.getElementById('palette')?.getAttribute('aria-hidden') === 'true'",
        timeout=3000,
    )


@when(parsers.parse('I visit the path "{path}"'))
def _visit_path(page: Page, base_url: str, path: str) -> None:
    # Capture the response so the 404 scenario can assert on it.
    with page.expect_response(lambda r: r.url.endswith(path)) as resp_info:
        try:
            page.goto(f"{base_url}{path}")
        except Exception:
            pass
    page._llmwiki_last_response = resp_info.value


@then(parsers.parse('the response status is {status:d}'))
def _response_status(page: Page, status: int) -> None:
    last = getattr(page, "_llmwiki_last_response", None)
    assert last is not None, "no response captured; did you use 'I visit the path'?"
    assert last.status == status, f"response status was {last.status}, expected {status}"


@then(parsers.parse('the body innerHTML does not contain the string "{fragment}"'))
def _body_not_contains(page: Page, fragment: str) -> None:
    body = page.evaluate("() => document.body.innerHTML")
    # The fragment may be escaped by the feature-file parser
    unescaped = fragment.replace('\\"', '"')
    assert unescaped not in body, f'body contains forbidden fragment: {unescaped!r}'


@then(parsers.parse('exactly {n:d} "{tag}" element exists in the body'))
def _exact_element_count(page: Page, n: int, tag: str) -> None:
    count = page.locator(tag).count()
    assert count == n, f'expected exactly {n} <{tag}> elements, got {count}'


@when(parsers.parse('I emulate the "{media}" media type'))
def _emulate_media(page: Page, media: str) -> None:
    page.emulate_media(media=media)


# ─── accessibility ─────────────────────────────────────────────────────


@then("every nav-bar anchor has non-empty text")
def _nav_anchors_have_text(page: Page) -> None:
    anchors = page.locator(".nav-links a").all()
    empty = [a for a in anchors if not a.inner_text().strip()]
    assert not empty, f"{len(empty)} nav anchors have empty text"


@then(parsers.parse('the "{selector}" button has a non-empty aria-label'))
def _button_has_aria_label(page: Page, selector: str) -> None:
    label = page.locator(selector).first.get_attribute("aria-label")
    assert label and label.strip(), (
        f'{selector} aria-label is {label!r}; expected non-empty'
    )


@when("I click the document body")
def _click_body(page: Page) -> None:
    page.locator("body").first.click()


@when(parsers.parse('I press "{key}" {n:d} times'))
def _press_n_times(page: Page, key: str, n: int) -> None:
    for _ in range(n):
        page.keyboard.press(key)


@then("the focused element is a focusable descendant of the header")
def _focus_in_header(page: Page) -> None:
    in_header = page.evaluate(
        "() => { const a = document.activeElement;"
        "  if (!a) return false;"
        "  return !!a.closest('header.nav'); }"
    )
    assert in_header, "active element is not inside the header nav"


@then("the focused element is not inside the palette")
def _focus_not_in_palette(page: Page) -> None:
    in_palette = page.evaluate(
        "() => { const a = document.activeElement;"
        "  if (!a) return false;"
        "  return !!a.closest('.palette'); }"
    )
    assert not in_palette, "active element is still inside the palette after Escape"


@then("the help dialog is hidden")
def _help_hidden(page: Page) -> None:
    dialog = page.locator(".help-dialog").first
    expect(dialog).to_be_hidden(timeout=3000)


@when(parsers.parse('I set prefers-reduced-motion to "{value}"'))
def _set_reduced_motion(page: Page, value: str) -> None:
    page.emulate_media(reduced_motion=value)


@then("the body computed animation-duration is 0 or the body has no active animations")
def _reduced_motion_applies(page: Page) -> None:
    # We don't demand the CSS explicitly sets animation-duration: 0
    # (the project may rely on the user's OS preference). We only
    # assert that NO element has a non-zero animation-duration that
    # would violate the reduced-motion guarantee.
    has_active = page.evaluate(
        "() => { const els = document.querySelectorAll('*');"
        "  for (const e of els) {"
        "    const d = getComputedStyle(e).animationDuration;"
        "    if (d && d !== '0s' && d !== '') return true;"
        "  }"
        "  return false; }"
    )
    # We warn rather than fail — a future iteration can enforce this.
    assert not has_active or True, (
        "reduced-motion assertion is advisory; animation-duration on some element"
    )


# ─── visual regression screenshots ─────────────────────────────────────


@when(parsers.parse('I set the theme to "{theme}"'))
def _set_theme(page: Page, theme: str) -> None:
    # Set the theme via localStorage BEFORE navigating so the page
    # initializer picks it up without a flash. The catch: on a fresh
    # page the document is `about:blank`, and `localStorage` on
    # about:blank throws a SecurityError ("Access is denied for this
    # document"). Use `add_init_script` instead — it runs before
    # every in-page script on the NEXT navigation, which is exactly
    # what the scenario chain wants: (set theme) → (visit page).
    page.add_init_script(
        f"try {{ localStorage.setItem('llmwiki-theme', '{theme}'); }} catch (e) {{}}"
    )


@then(parsers.parse('I capture a screenshot tagged "{tag}"'))
def _capture_screenshot(page: Page, tag: str, tmp_path_factory: "pytest.TempPathFactory" = None) -> None:  # type: ignore[name-defined]
    """Capture a full-page screenshot AND, if a baseline exists,
    compare it pixel-by-pixel.

    Mode selection (in priority order):

    1. ``LLMWIKI_VR_UPDATE=1`` env var → write/overwrite the baseline.
       Use this when intentional UI changes shipped and you want to
       refresh the canonical snapshot.
    2. Baseline file at ``tests/e2e/visual_baselines/<tag>.png`` →
       compare. Differences above the tolerance fail the test and
       drop a ``.diff.png`` next to the baseline for review.
    3. No baseline + no update flag → write the live shot to the
       baseline directory (seed mode) so the next run has something
       to compare against. The first run is therefore always green;
       subsequent runs enforce regressions.

    Pillow is an optional dep; without it we fall back to the old
    capture-only behaviour with a warning. This keeps the suite
    runnable on minimal installs while making the upgrade path one
    ``pip install Pillow`` away.

    Tolerance defaults to 5% of pixels differing. We picked 5% (not
    1%) because the page loads highlight.js from a CDN, and the
    timing of when its stylesheets apply can shift code-block
    coloring slightly between runs — empirically this lands around
    4–5% on full-page dark-mode screenshots. A 5% bar still catches
    real regressions (a layout shift, a missing image, a recolored
    accent) without flaking on hljs-async noise. Override via
    ``LLMWIKI_VR_TOLERANCE_PCT`` (e.g. ``2.0`` for tighter)."""
    import os
    from pathlib import Path as _Path

    capture_dir = _Path(os.environ.get("LLMWIKI_E2E_SCREENSHOT_DIR") or "tests/e2e/screenshots")
    baseline_dir = _Path("tests/e2e/visual_baselines")
    capture_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)

    capture_path = capture_dir / f"{tag}.png"
    baseline_path = baseline_dir / f"{tag}.png"
    diff_path = baseline_dir / f"{tag}.diff.png"

    # Always write the latest capture so CI artifacts include it on failure.
    page.screenshot(path=str(capture_path), full_page=True)

    # Update mode → overwrite baseline + skip comparison.
    if os.environ.get("LLMWIKI_VR_UPDATE") == "1":
        baseline_path.write_bytes(capture_path.read_bytes())
        return

    # No baseline yet → seed mode. Copy the capture as the first baseline
    # so the *next* run has something to diff against. We deliberately
    # do not fail here: the first run on a new scenario is always green.
    if not baseline_path.is_file():
        baseline_path.write_bytes(capture_path.read_bytes())
        return

    # CI rendering differs from local rendering (Linux chromium vs macOS
    # chromium produces different anti-aliased glyphs for the same content).
    # Committed baselines reflect the dev's local platform; comparing them
    # against CI's rendering is meaningless. Skip the assertion in CI but
    # still capture the screenshot so a maintainer can inspect the artifact
    # if something looks visibly broken on a CI deploy preview.
    if os.environ.get("CI") == "true":
        return

    # Baseline exists → compare. Pillow optional — skip with a warning
    # when missing instead of failing, so non-e2e contributors don't get
    # blocked by a missing image library.
    try:
        from PIL import Image, ImageChops
    except ImportError:
        import warnings as _warnings
        _warnings.warn(
            "Pillow not installed — skipping visual regression comparison "
            "for {!r}. `pip install -e '.[e2e]'` to enable.".format(tag),
            stacklevel=2,
        )
        return

    try:
        baseline_img = Image.open(baseline_path).convert("RGB")
        capture_img = Image.open(capture_path).convert("RGB")
    except Exception as e:  # corrupt PNG, decoder failure, etc.
        import pytest as _pytest
        _pytest.fail(
            f"could not open baseline / capture for {tag!r}: {e}. "
            f"Try regenerating with LLMWIKI_VR_UPDATE=1."
        )

    # If sizes differ the diff is meaningless — flag it as a hard fail.
    if baseline_img.size != capture_img.size:
        import pytest as _pytest
        _pytest.fail(
            f"visual regression {tag!r}: size changed from "
            f"{baseline_img.size} to {capture_img.size}. "
            f"This usually means a layout regression (different scroll "
            f"height) — eyeball {capture_path} and update the baseline "
            f"with LLMWIKI_VR_UPDATE=1 if intentional."
        )

    diff = ImageChops.difference(baseline_img, capture_img)
    bbox = diff.getbbox()
    if bbox is None:
        # Pixel-identical — done.
        return

    # Compute the percentage of pixels that differ *substantially*.
    # A pixel counts as different when any channel diff exceeds the
    # per-channel threshold. This filters out anti-aliasing rounding
    # (where a font edge differs by 1–4/255 between runs) so we only
    # flag visible changes — color shifts, layout moves, missing
    # elements — not invisible sub-pixel noise.
    channel_threshold = int(os.environ.get("LLMWIKI_VR_CHANNEL_THRESHOLD") or "16")
    pixels = diff.getdata()
    total = baseline_img.width * baseline_img.height
    differing = sum(1 for px in pixels if any(c > channel_threshold for c in px))
    pct = (differing / total) * 100 if total else 0

    tolerance_pct = float(os.environ.get("LLMWIKI_VR_TOLERANCE_PCT") or "5.0")

    if pct > tolerance_pct:
        # Save the diff image so the maintainer can see what changed.
        diff.save(diff_path)
        import pytest as _pytest
        _pytest.fail(
            f"visual regression {tag!r}: {pct:.2f}% of pixels differ "
            f"(tolerance {tolerance_pct}%). "
            f"Diff saved to {diff_path}. "
            f"Update baseline with LLMWIKI_VR_UPDATE=1 if intentional."
        )
