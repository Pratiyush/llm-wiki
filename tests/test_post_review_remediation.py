"""Pin the contract for the post-review remediation PR (v1.3.42).

Five-agent code review (local + GitHub claude-review) of v1.3.41
surfaced these real bugs which this PR addresses:

  1. `__dialogLastFocus` was a single shared slot — interleaving
     palette + help dialogs corrupted focus restoration. Now a Map
     keyed by dialog id.

  2. `__closeDialog` stripped `inert` from a sibling that was itself
     still an open dialog. Closing help while palette is open
     re-exposed the chrome behind the palette. Fixed by skipping
     siblings that match the open-dialog id list.

  3. `innerHTML` of the related-pages panel concatenated unescaped
     `s.entry.title` / `url` / `date` — latent XSS if a session
     frontmatter title contains HTML. Now built via createElement +
     textContent + a `_safeHref` validator that rejects
     `javascript:` / `data:` / `vbscript:` URLs.

  4. `role="menu"` on `nav-drawer` was wrong (children are plain
     `<a>`, not `role="menuitem"`). Removed; replaced with a plain
     `aria-label="Main navigation"` since the drawer is a disclosure
     nav, not an ARIA menu.

  5. `#mbn-theme` (mobile bottom-nav theme button) never synced
     `aria-pressed`. Added a `_mbnSyncPressed()` closure that fires
     on init + after every click, and added `aria-pressed="false"`
     to the static markup.

  6. `#palette-input` had no programmatic label. Added
     `aria-label="Search pages"`.

  7. `render_models_section` + `render_vs_section` referenced 8
     names that were never imported. The build doesn't currently call
     either function, but they would have crashed with `NameError` on
     first wire-up. Added lazy imports inside both functions.
"""
from __future__ import annotations

import re

from llmwiki.build import nav_bar, render_models_section, render_vs_section
from llmwiki.render.js import JS


# 1. Per-dialog focus stash.

def test_dialog_last_focus_is_a_map_not_single_slot() -> None:
    assert "var __dialogLastFocus = new Map()" in JS
    # set + get + delete via dialog.id key.
    assert "__dialogLastFocus.set(dialog.id, document.activeElement)" in JS
    assert "__dialogLastFocus.get(dialog.id)" in JS
    assert "__dialogLastFocus.delete(dialog.id)" in JS


# 2. inert removal respects still-open sibling dialogs.

def test_close_dialog_does_not_strip_inert_from_open_siblings() -> None:
    assert "function __isOpenDialog" in JS
    # The close path must call __isOpenDialog before removing inert.
    close_block = JS[JS.find("function __closeDialog"):
                     JS.find("function __closeDialog") + 800]
    assert "__isOpenDialog(s)" in close_block
    assert "removeAttribute(\"inert\")" in close_block


# 3. Related-pages renderer escapes its inputs.

def test_related_pages_built_via_createElement_not_innerHTML() -> None:
    """The related-pages renderer must build its DOM via createElement
    + textContent so an unescaped wiki title can't ship to the browser.

    Locate the right block by looking for the post-review safe-href
    helper rather than the section heading text (the heading also
    appears in a file-header comment higher up)."""
    block_start = JS.find("function _safeHref(")
    assert block_start != -1, "_safeHref helper missing from JS"
    block = JS[block_start: block_start + 1800]
    assert "createElement" in block
    assert "textContent" in block


def test_safe_href_rejects_javascript_protocol() -> None:
    """The _safeHref helper must reject javascript:/data:/vbscript:
    URLs so a malicious frontmatter URL can't slip past the new
    DOM-tree builder."""
    assert "javascript|data|vbscript" in JS or "javascript|data" in JS


# 4. nav-drawer no longer claims role=menu without role=menuitem children.

def test_nav_drawer_has_no_role_menu() -> None:
    nav = nav_bar(active="home")
    assert 'role="menu"' not in nav
    # The container still needs an accessible name.
    assert 'aria-label="Main navigation"' in nav


# 5. Mobile theme button keeps aria-pressed in sync.

def test_mbn_theme_has_aria_pressed_in_markup() -> None:
    """page_foot emits the mobile bottom nav. Its theme button now
    ships with `aria-pressed="false"` baked in (JS overwrites on
    page load so the initial value is just a placeholder)."""
    from llmwiki.build import page_foot
    foot = page_foot()
    # Find the mbn-theme button + its attrs.
    m = re.search(r'id="mbn-theme"[^>]*', foot)
    assert m, "mbn-theme button missing from page_foot output"
    assert 'aria-pressed' in m.group(0)


def test_mbn_theme_js_handler_calls_sync_pressed() -> None:
    """The click handler for the mobile theme button must invoke the
    aria-pressed sync helper after toggling data-theme."""
    handler_block = JS[JS.find('"mbn-theme"'):
                       JS.find('"mbn-theme"') + 1500]
    assert "_mbnSyncPressed" in handler_block
    assert "_mbnSyncPressed()" in handler_block


# 6. Palette input has accessible label.

def test_palette_input_has_aria_label() -> None:
    from llmwiki.build import page_foot
    foot = page_foot()
    m = re.search(r'id="palette-input"[^>]*', foot)
    assert m, "palette-input missing from page_foot output"
    assert 'aria-label="Search pages"' in m.group(0)


# 7. render_models_section + render_vs_section import their dependencies.

def test_render_models_section_does_not_raise_name_error_at_load_time() -> None:
    """Either the imports are at module level OR they're lazy inside
    the function body. Either way, importing build doesn't fail and
    calling the function on a no-entities tree just returns cleanly."""
    # Module imported at the top — that already proves no ImportError
    # at load time. Now exercise the function on a tmp tree to make
    # sure lazy imports inside resolve.
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "site"
        out.mkdir(parents=True)
        # No wiki/entities under REPO_ROOT (test environment), so
        # the function should return (path, 0) cleanly.
        result = render_models_section(out)
        # Tuple-of-2 contract.
        assert isinstance(result, tuple) and len(result) == 2


def test_render_vs_section_does_not_raise_name_error_at_load_time() -> None:
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "site"
        out.mkdir(parents=True)
        result = render_vs_section(out)
        assert isinstance(result, tuple) and len(result) == 2
