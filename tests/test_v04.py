"""Tests for v0.4 additions — exporters, manifest, link_checker, wiki_export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki import __version__

from tests.conftest import REPO_ROOT


# ─── version bump ────────────────────────────────────────────────────────


def test_version_is_valid_semver_0x():
    """v0.4 introduced these tests. The constraint has been relaxed over
    time: v0.4→v0.9 was allowed, and with v1.0.0 the pre-1.0 constraint is
    lifted entirely. We only assert semver shape now so the v0.4 exporter
    tests below gate on actual exporter behaviour, not the version string."""
    parts = __version__.split(".")
    assert len(parts) == 3, f"expected x.y.z, got {__version__}"
    major, minor, patch = parts
    assert major.isdigit() and int(major) >= 0, f"invalid major: {__version__}"
    assert minor.isdigit(), (
        f"minor must be an integer; got {__version__}"
    )


def test_pyproject_version_matches_package():
    """Whatever version `llmwiki/__init__.py` sets, `pyproject.toml`
    must match — otherwise `pip install .` ships a different number
    than `llmwiki --version` reports."""
    content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in content, (
        f"pyproject.toml version does not match __version__ ({__version__})"
    )


# ─── exporters ───────────────────────────────────────────────────────────


def test_exporters_module_imports():
    from llmwiki.exporters import (
        export_all,
        write_llms_txt,
        write_llms_full_txt,
        write_graph_jsonld,
        write_sitemap,
        write_rss,
        write_robots_txt,
        write_ai_readme,
        write_page_txt,
        write_page_json,
        _plain_text,
        _sha256_16,
        _page_id,
    )
    for f in (
        export_all, write_llms_txt, write_llms_full_txt, write_graph_jsonld,
        write_sitemap, write_rss, write_robots_txt, write_ai_readme,
        write_page_txt, write_page_json,
    ):
        assert callable(f)


def test_plain_text_strips_markdown():
    from llmwiki.exporters import _plain_text

    md = "# Heading\n\nSome **bold** and `code` and [link](http://x).\n\n```py\nprint('x')\n```\n\n- Bullet\n- [[wikilink]]\n"
    text = _plain_text(md)
    assert "**" not in text
    assert "```" not in text
    assert "print('x')" not in text
    assert "Heading" in text
    assert "wikilink" in text


def test_sha256_16_stable():
    from llmwiki.exporters import _sha256_16

    h1 = _sha256_16("hello")
    h2 = _sha256_16("hello")
    assert h1 == h2
    assert len(h1) == 16
    assert _sha256_16("hello") != _sha256_16("world")


def test_page_id_format():
    from llmwiki.exporters import _page_id

    assert _page_id("ai-newsletter", "my-slug") == "ai-newsletter/my-slug"


def test_write_llms_txt(tmp_path):
    from llmwiki.exporters import write_llms_txt

    groups = {"proj-a": [], "proj-b": []}
    p = write_llms_txt(tmp_path, groups, total_sessions=42)
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert content.startswith("# llmwiki")
    assert "42 sessions" in content
    assert "proj-a" in content
    assert "proj-b" in content


def test_write_robots_txt(tmp_path):
    from llmwiki.exporters import write_robots_txt

    p = write_robots_txt(tmp_path)
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "User-agent:" in content
    assert "Sitemap:" in content
    assert "llms.txt" in content


def test_write_ai_readme(tmp_path):
    from llmwiki.exporters import write_ai_readme

    p = write_ai_readme(tmp_path, groups={"a": []}, total_sessions=5)
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "AI agents" in content
    assert "llms.txt" in content


# ─── build integration ──────────────────────────────────────────────────


def test_build_produces_ai_exports():
    site = REPO_ROOT / "site"
    # `llmwiki init` creates an empty site/ dir with just .gitkeep, which would
    # make a `site.exists()` skip return False even though no real build has
    # happened. Key on manifest.json — it's only written by a full build.
    if not (site / "manifest.json").exists():
        pytest.skip("site/ not built (no manifest.json — run `llmwiki build`)")
    for expected in (
        "llms.txt",
        "llms-full.txt",
        "graph.jsonld",
        "sitemap.xml",
        "rss.xml",
        "robots.txt",
        "ai-readme.md",
        "manifest.json",
    ):
        p = site / expected
        assert p.exists(), f"missing {expected} after build"


def test_graph_jsonld_is_valid_json():
    site = REPO_ROOT / "site"
    p = site / "graph.jsonld"
    if not p.exists():
        pytest.skip("graph.jsonld not built")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["@context"] == "https://schema.org"
    assert "@graph" in data
    assert isinstance(data["@graph"], list)


def test_manifest_has_files_and_hashes():
    site = REPO_ROOT / "site"
    p = site / "manifest.json"
    if not p.exists():
        pytest.skip("manifest.json not built")
    data = json.loads(p.read_text(encoding="utf-8"))
    for key in ("version", "generated_at", "total_files", "total_bytes", "files", "perf_budget"):
        assert key in data
    assert len(data["files"]) > 0
    for entry in data["files"][:5]:
        assert "path" in entry and "size" in entry and "sha256" in entry


def test_per_page_sibling_txt_and_json_exist():
    site_sessions = REPO_ROOT / "site" / "sessions"
    if not site_sessions.exists():
        pytest.skip("site/sessions/ not built")
    html_files = [p for p in site_sessions.rglob("*.html") if p.name != "index.html"]
    if not html_files:
        pytest.skip("no session HTML files")
    sample = html_files[0]
    txt = sample.with_suffix(".txt")
    jsn = sample.with_suffix(".json")
    assert txt.exists(), f"missing .txt sibling for {sample.name}"
    assert jsn.exists(), f"missing .json sibling for {sample.name}"


def test_session_page_has_schema_org_microdata():
    site_sessions = REPO_ROOT / "site" / "sessions"
    if not site_sessions.exists():
        pytest.skip("site/sessions/ not built")
    html_files = [p for p in site_sessions.rglob("*.html") if p.name != "index.html"]
    if not html_files:
        pytest.skip("no session HTML files")
    content = html_files[0].read_text(encoding="utf-8")
    assert 'itemtype="https://schema.org/Article"' in content
    assert "llmwiki:metadata" in content


def test_session_page_has_canonical_link():
    site_sessions = REPO_ROOT / "site" / "sessions"
    if not site_sessions.exists():
        pytest.skip("site/sessions/ not built")
    html_files = [p for p in site_sessions.rglob("*.html") if p.name != "index.html"]
    if not html_files:
        pytest.skip("no session HTML files")
    content = html_files[0].read_text(encoding="utf-8")
    assert '<link rel="canonical"' in content


# ─── manifest module ─────────────────────────────────────────────────────


def test_manifest_module_imports():
    from llmwiki.manifest import build_manifest, write_manifest, sha256_hex, PERF_BUDGET

    assert callable(build_manifest)
    assert callable(write_manifest)
    assert callable(sha256_hex)
    assert isinstance(PERF_BUDGET, dict)
    for key in ("total_site_bytes", "per_page_bytes", "css_js_bytes"):
        assert key in PERF_BUDGET


def test_manifest_sha256_hex_is_16_chars(tmp_path):
    from llmwiki.manifest import sha256_hex

    f = tmp_path / "hello.txt"
    f.write_text("hello world", encoding="utf-8")
    h = sha256_hex(f)
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


def test_manifest_missing_file_returns_empty_hash(tmp_path):
    from llmwiki.manifest import sha256_hex

    h = sha256_hex(tmp_path / "nonexistent.txt")
    assert h == ""


# ─── link checker ────────────────────────────────────────────────────────


def test_link_checker_imports():
    from llmwiki.link_checker import check_site, is_external, resolve_target

    assert callable(check_site)
    assert callable(is_external)
    assert callable(resolve_target)


def test_link_checker_is_external():
    from llmwiki.link_checker import is_external

    assert is_external("http://example.com")
    assert is_external("https://example.com")
    assert is_external("mailto:a@b.c")
    assert is_external("javascript:void(0)")
    assert not is_external("about.html")
    assert not is_external("../index.html")


# ─── MCP wiki_export tool ────────────────────────────────────────────────


def test_mcp_has_wiki_export_tool():
    from llmwiki.mcp.server import TOOLS, TOOL_IMPLS

    names = {t["name"] for t in TOOLS}
    assert "wiki_export" in names
    assert "wiki_export" in TOOL_IMPLS


def test_mcp_wiki_export_list_format():
    from llmwiki.mcp.server import tool_wiki_export

    result = tool_wiki_export({"format": "list"})
    assert "content" in result
    assert isinstance(result["content"], list)


def test_mcp_wiki_export_unknown_format():
    from llmwiki.mcp.server import tool_wiki_export

    result = tool_wiki_export({"format": "bogus"})
    assert result["isError"] is True


# ─── CLI subcommands ─────────────────────────────────────────────────────


def test_cli_has_v04_subcommands():
    from llmwiki.cli import build_parser

    parser = build_parser()
    help_text = parser.format_help()
    for cmd in ("check-links", "export", "manifest"):
        assert cmd in help_text, f"missing v0.4 CLI subcommand: {cmd}"
