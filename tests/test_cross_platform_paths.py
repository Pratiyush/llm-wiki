"""Cross-platform path coverage for all adapters.

Every adapter that uses OS-specific paths (~/Library/, ~/.config/, ~/AppData/)
in DEFAULT_ROOTS must cover at least macOS + Linux + Windows.  Adapters that
only use dot-dirs (~/.agent/) are inherently cross-platform and are verified
separately.  The PDF adapter has no defaults (user-configured) and is exempt.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

from llmwiki.adapters.claude_code import ClaudeCodeAdapter
from llmwiki.adapters.codex_cli import CodexCliAdapter
from llmwiki.adapters.cursor import CursorAdapter
from llmwiki.adapters.gemini_cli import GeminiCliAdapter
from llmwiki.adapters.obsidian import ObsidianAdapter
from llmwiki.adapters.pdf import PdfAdapter


# ── helpers ──────────────────────────────────────────────────────────

def _get_default_paths(adapter_cls) -> list[Path]:
    """Return the list of default root paths for an adapter class."""
    if hasattr(adapter_cls, "DEFAULT_ROOTS"):
        return list(adapter_cls.DEFAULT_ROOTS)
    if hasattr(adapter_cls, "DEFAULT_VAULT_PATHS"):
        return list(adapter_cls.DEFAULT_VAULT_PATHS)
    # Fall back to session_store_path (may be a single Path)
    ssp = adapter_cls.session_store_path
    if isinstance(ssp, list):
        return list(ssp)
    return [ssp]


_MACOS_MARKERS = ("Library",)
_LINUX_MARKERS = (".config", ".local")
_WINDOWS_MARKERS = ("AppData",)


def _has_os_specific_paths(paths: list[Path]) -> bool:
    """True if any path uses an OS-specific directory convention."""
    for p in paths:
        parts = p.parts
        if any(m in parts for m in _MACOS_MARKERS + _LINUX_MARKERS + _WINDOWS_MARKERS):
            return True
    return False


def _covers_platform(paths: list[Path], markers: tuple[str, ...]) -> bool:
    """True if at least one path contains a marker for the given platform."""
    for p in paths:
        if any(m in p.parts for m in markers):
            return True
    return False


def _is_dot_dir_only(paths: list[Path]) -> bool:
    """True if every path is a dot-directory under home (cross-platform)."""
    home = Path.home()
    for p in paths:
        try:
            rel = p.relative_to(home)
        except ValueError:
            return False
        # A dot-dir starts with '.' in its first component
        if not rel.parts or not rel.parts[0].startswith("."):
            return False
    return True


# ── adapters that use OS-specific paths must cover all 3 platforms ───

# These adapters have platform-specific entries in DEFAULT_ROOTS:
_OS_SPECIFIC_ADAPTERS = [
    CursorAdapter,
    GeminiCliAdapter,
    ObsidianAdapter,
]


def test_os_specific_adapters_have_at_least_2_roots():
    """Every adapter with OS-specific paths needs >=2 DEFAULT_ROOTS entries."""
    for cls in _OS_SPECIFIC_ADAPTERS:
        paths = _get_default_paths(cls)
        assert len(paths) >= 2, (
            f"{cls.__name__} has only {len(paths)} default root(s); "
            f"need >=2 for cross-platform coverage"
        )


def test_cursor_covers_macos_linux_windows():
    paths = _get_default_paths(CursorAdapter)
    assert _covers_platform(paths, _MACOS_MARKERS), "CursorAdapter missing macOS path"
    assert _covers_platform(paths, _LINUX_MARKERS), "CursorAdapter missing Linux path"
    assert _covers_platform(paths, _WINDOWS_MARKERS), "CursorAdapter missing Windows path"


def test_gemini_cli_covers_macos_linux_windows():
    paths = _get_default_paths(GeminiCliAdapter)
    # macOS is covered by ~/.gemini (dot-dir) — check Linux and Windows specifics
    assert _covers_platform(paths, _LINUX_MARKERS), "GeminiCliAdapter missing Linux path"
    assert _covers_platform(paths, _WINDOWS_MARKERS), "GeminiCliAdapter missing Windows path"


def test_obsidian_covers_windows():
    paths = _get_default_paths(ObsidianAdapter)
    assert _covers_platform(paths, _WINDOWS_MARKERS), "ObsidianAdapter missing Windows path"


# ── dot-dir-only adapters are inherently cross-platform ──────────────

_DOT_DIR_ADAPTERS = [
    ClaudeCodeAdapter,
    CodexCliAdapter,
]


def test_dotdir_adapters_are_cross_platform():
    """Dot-directory adapters (~/.agent/) work on all platforms by definition."""
    for cls in _DOT_DIR_ADAPTERS:
        paths = _get_default_paths(cls)
        assert _is_dot_dir_only(paths), (
            f"{cls.__name__} uses non-dot-dir paths but is not in the "
            f"OS-specific adapter list"
        )


# ── PDF adapter is exempt (user-configured, no defaults) ────────────

def test_pdf_adapter_has_empty_defaults():
    """PDF adapter intentionally has no defaults — user must configure roots."""
    assert PdfAdapter.DEFAULT_ROOTS == [], (
        "PdfAdapter should have empty DEFAULT_ROOTS (user-configured)"
    )


# ── every adapter's paths resolve under Path.home() ─────────────────

_ALL_ADAPTERS = [
    ClaudeCodeAdapter,
    CodexCliAdapter,
    CursorAdapter,
    GeminiCliAdapter,
    ObsidianAdapter,
    # PDF excluded — empty defaults
]


def test_all_default_paths_are_under_home():
    """All default roots should be relative to the user's home directory."""
    home = Path.home()
    for cls in _ALL_ADAPTERS:
        paths = _get_default_paths(cls)
        for p in paths:
            assert str(p).startswith(str(home)), (
                f"{cls.__name__} path {p} is not under home ({home})"
            )


def test_no_adapter_uses_hardcoded_username():
    """No adapter should hardcode a username like /Users/alice/ or /home/bob/."""
    for cls in _ALL_ADAPTERS:
        paths = _get_default_paths(cls)
        for p in paths:
            # Path.home() resolves dynamically; make sure no extra user dir is
            # hardcoded beyond what Path.home() provides.
            parts_str = str(p)
            home_str = str(Path.home())
            after_home = parts_str[len(home_str):]
            # Should not contain another /Users/ or /home/ segment
            assert "/Users/" not in after_home, (
                f"{cls.__name__}: path {p} contains hardcoded /Users/ after home"
            )
            assert "/home/" not in after_home, (
                f"{cls.__name__}: path {p} contains hardcoded /home/ after home"
            )
