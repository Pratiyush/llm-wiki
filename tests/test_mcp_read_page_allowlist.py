"""Tests for #482 — MCP wiki_read_page must restrict reads to a
documented allowlist.

The bug: `_safe_path` only checked the file was under REPO_ROOT.
Any dotfile (`.env`, `.git/config`, `.llmwiki-state.json`) or
private dir (`.venv/`, `node_modules/`) was readable via MCP. The
state file in particular leaks absolute paths to every Claude
session on the host machine.

The fix: `_is_read_page_allowed(p)` allowlist of `wiki/raw/docs/
examples/site/` directories + a few documented root files
(README, CHANGELOG, CONTRIBUTING, LICENSE).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.mcp.server import (
    _is_read_page_allowed,
    tool_wiki_read_page,
)


# ─── _is_read_page_allowed: positive cases ──────────────────────────────


@pytest.mark.parametrize("rel", [
    "wiki/index.md",
    "wiki/entities/Foo.md",
    "raw/sessions/2026-04-01-x.md",
    "docs/getting-started.md",
    "examples/sessions_config.json",
    "site/index.html",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
])
def test_allowlisted_paths_pass(rel: str):
    assert _is_read_page_allowed(REPO_ROOT / rel), (
        f"{rel!r} should be allowed by the read-page surface"
    )


# ─── _is_read_page_allowed: negative cases (the bug) ────────────────────


@pytest.mark.parametrize("rel", [
    ".env",
    ".gitignore",
    ".git/config",
    ".git/HEAD",
    ".llmwiki-state.json",
    ".llmwiki-quarantine.json",
    ".venv/lib/python3.12/something.py",
    "node_modules/some-pkg/index.js",
    "tests/test_secret_helper.py",   # tests/ deliberately not allowlisted
    "llmwiki/cli.py",                 # source code not allowlisted
    "pyproject.toml",                 # root config not allowlisted
])
def test_blocked_paths_rejected(rel: str):
    assert not _is_read_page_allowed(REPO_ROOT / rel), (
        f"{rel!r} should NOT be readable via MCP — it leaks "
        f"sensitive host info or source code"
    )


# ─── tool_wiki_read_page integration ───────────────────────────────────


def test_tool_rejects_state_file_with_helpful_error():
    """The original bug pattern: state file contains absolute paths
    to every Claude session on the host."""
    res = tool_wiki_read_page({"path": ".llmwiki-state.json"})
    assert res.get("isError") is True or "outside the readable surface" in str(res), res
    # Error message should name the allowed dirs so the caller knows
    # what to ask for instead.
    body = str(res)
    assert "wiki" in body and "raw" in body, (
        f"error message should list allowed dirs: {body}"
    )


def test_tool_accepts_changelog():
    res = tool_wiki_read_page({"path": "CHANGELOG.md"})
    # Should NOT be a permission-style error — file exists, content returned.
    assert res.get("isError") is not True or "outside the readable surface" not in str(res)


def test_tool_rejects_dot_env_even_if_present(tmp_path: Path, monkeypatch):
    """Belt-and-braces: even if a user puts `.env` in REPO_ROOT
    (gitignored, but happens), it must not be readable via MCP."""
    # Create a fake .env at REPO_ROOT (cleanup needed)
    env_path = REPO_ROOT / ".env"
    created = False
    if not env_path.exists():
        env_path.write_text("API_KEY=secret\n", encoding="utf-8")
        created = True
    try:
        res = tool_wiki_read_page({"path": ".env"})
        assert "outside the readable surface" in str(res) or res.get("isError"), res
        # Critical: secret content must NOT appear in the response.
        assert "API_KEY=secret" not in str(res)
    finally:
        if created:
            env_path.unlink()
