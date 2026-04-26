"""Tests for #489 — auto-detected `real_username` must not over-match
on Windows or stripped containers.

The bug: `load_config` fell back to `os.environ["USER"] or
Path.home().name`. Two failure modes hit users in the wild:

1. **Windows** uses `USERNAME` not `USER` → env lookup empty →
   fallback to `Path.home().name` returns the actual short name,
   which the redactor then substring-matched into unrelated path
   tokens.
2. **Stripped Docker / CI images** have `USER` unset and
   `Path.home()` = `/root` → fallback returns `"root"` → every
   `/Users/root/`, `/home/root/` path got mass-rewritten to
   `/Users/USER/`.

Fix: prefer `USER` → `USERNAME` → `Path.home().name` only when
it's ≥3 chars AND not in the generic-container set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.convert import load_config


def _config_path(tmp_path: Path) -> Path:
    """A non-existent path so load_config skips file-merge and only
    runs the auto-detect branch we want to test."""
    return tmp_path / "no-such-config.json"


def test_unix_user_env_var_wins(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("USER", "alice")
    monkeypatch.delenv("USERNAME", raising=False)
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == "alice"


def test_windows_username_env_var_used_when_USER_missing(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.setenv("USERNAME", "alice-win")
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == "alice-win"


def test_USER_takes_precedence_over_USERNAME(tmp_path: Path, monkeypatch):
    """Unix-style env wins over Windows-style if both happen to be set
    (e.g. on Cygwin or WSL)."""
    monkeypatch.setenv("USER", "unix-user")
    monkeypatch.setenv("USERNAME", "win-user")
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == "unix-user"


def test_root_homedir_does_not_leak_as_username(tmp_path: Path, monkeypatch):
    """The original bug: stripped container with USER unset →
    Path.home().name was 'root' → every /home/root/ path got
    rewritten. Must now leave field empty so the redactor stays a
    no-op until user opts in."""
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/root")))
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == ""


def test_generic_user_homedir_does_not_leak(tmp_path: Path, monkeypatch):
    """Same protection for `user`, `ubuntu`, `home` etc."""
    for generic in ("user", "User", "USER", "ubuntu", "home", "users"):
        monkeypatch.delenv("USER", raising=False)
        monkeypatch.delenv("USERNAME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls, g=generic: Path(f"/home/{g}")))
        cfg = load_config(_config_path(tmp_path))
        assert cfg["redaction"]["real_username"] == "", generic


def test_short_homedir_name_skipped(tmp_path: Path, monkeypatch):
    """Names <3 chars are too risky as substring rewrite targets."""
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/ab")))
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == ""


def test_long_specific_homedir_used(tmp_path: Path, monkeypatch):
    """Real user names (≥3 chars, not generic) ARE trusted as fallback."""
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/pratiyush")))
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == "pratiyush"


def test_explicit_config_value_overrides_autodetect(tmp_path: Path, monkeypatch):
    """If the user wrote `real_username` into config, never auto-overwrite."""
    import json
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        json.dumps({"redaction": {"real_username": "explicitly-mine"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("USER", "should-be-ignored")
    cfg = load_config(cfg_path)
    assert cfg["redaction"]["real_username"] == "explicitly-mine"
