"""Tests for #485 — username redaction across Windows D:/E:/cygwin/WSL.

Bug: `_redact_username` covered only `/Users/`, `/home/`, `C:\\Users\\`,
`C:/Users/`, `/mnt/<letter>/Users/`. Missed Windows non-C drives,
Cygwin (`/cygdrive/c/Users/`), Windows extended-length prefix
(`\\\\?\\C:\\Users\\`), WSL UNC (`\\\\wsl.localhost\\<distro>\\home\\`,
`\\\\wsl$\\<distro>\\home\\`).

Fix: extended the prefix alternation to cover all 5 new shapes.
"""

from __future__ import annotations

import pytest

from llmwiki.convert import Redactor


@pytest.fixture
def redactor():
    cfg = {
        "redaction": {
            "real_username": "alice",
            "replacement_username": "USER",
            "extra_patterns": [],
        },
    }
    return Redactor(cfg)


@pytest.mark.parametrize("path", [
    "/Users/alice/code",
    "/home/alice/code",
    r"C:\Users\alice\code",
    "C:/Users/alice/code",
    "/mnt/c/Users/alice/code",
])
def test_existing_prefixes_still_redact(redactor, path: str):
    out = redactor(path)
    assert "alice" not in out
    assert "USER" in out


@pytest.mark.parametrize("path", [
    r"D:\Users\alice\code",
    r"E:\Users\alice\code",
    r"F:\Users\alice\code",
    "D:/Users/alice/code",
    "E:/Users/alice/code",
])
def test_windows_non_c_drives_redacted(redactor, path: str):
    out = redactor(path)
    assert "alice" not in out, f"failed to redact {path!r}"
    assert "USER" in out


def test_cygwin_path_redacted(redactor):
    path = "/cygdrive/c/Users/alice/code"
    out = redactor(path)
    assert "alice" not in out
    assert "USER" in out


def test_cygwin_path_other_drive_redacted(redactor):
    path = "/cygdrive/d/Users/alice/code"
    out = redactor(path)
    assert "alice" not in out


def test_windows_extended_length_prefix_redacted(redactor):
    path = r"\\?\C:\Users\alice\code"
    out = redactor(path)
    assert "alice" not in out


def test_wsl_localhost_unc_redacted(redactor):
    path = r"\\wsl.localhost\Ubuntu\home\alice\code"
    out = redactor(path)
    assert "alice" not in out


def test_wsl_legacy_unc_redacted(redactor):
    path = r"\\wsl$\Ubuntu\home\alice\code"
    out = redactor(path)
    assert "alice" not in out


def test_wsl_unc_distro_with_hyphen_redacted(redactor):
    """Distro names like `Debian-12`, hyphens allowed."""
    path = r"\\wsl.localhost\Debian-12\home\alice\code"
    out = redactor(path)
    assert "alice" not in out


def test_unrelated_alice_substring_not_redacted(redactor):
    """`alice` outside a recognised prefix must NOT be touched."""
    out = redactor("Function aliceWrapper handles auth.")
    assert "aliceWrapper" in out


def test_alice_in_url_not_redacted(redactor):
    """`/users/alice/` (lowercase 'users' in a URL path) must not match
    the `/Users/` prefix."""
    out = redactor("https://example.com/users/alice/profile")
    assert "alice" in out
