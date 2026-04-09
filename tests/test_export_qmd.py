"""Tests for `llmwiki.export_qmd` — qmd collection export adapter (v0.6 · #59)."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from llmwiki.export_qmd import (
    _GLOB_PATTERNS,
    copy_wiki_tree,
    export_qmd,
    render_index_script,
    render_qmd_manifest,
    render_qmd_readme,
)


# ─── render_qmd_manifest ─────────────────────────────────────────────────


def test_manifest_contains_collection_name_and_version():
    out = render_qmd_manifest("my-wiki")
    assert "collection: my-wiki" in out
    assert "version: 1" in out


def test_manifest_contains_every_glob_pattern():
    out = render_qmd_manifest()
    for name, pattern in _GLOB_PATTERNS:
        assert f"name: {name}" in out
        assert f'glob: "{pattern}"' in out


def test_manifest_yaml_is_parseable_by_eye():
    """Cheap smoke test — the manifest should at least have matching
    key counts. Real qmd-compat testing lives in qmd's own repo."""
    out = render_qmd_manifest()
    lines = out.splitlines()
    name_count = sum(1 for ln in lines if ln.strip().startswith("- name:"))
    glob_count = sum(1 for ln in lines if ln.strip().startswith("glob:"))
    assert name_count == glob_count == len(_GLOB_PATTERNS)


# ─── render_qmd_readme ──────────────────────────────────────────────────


def test_readme_mentions_indexing_command():
    readme = render_qmd_readme("my-wiki")
    assert "qmd index" in readme
    assert "my-wiki" in readme


def test_readme_has_claude_desktop_mcp_snippet():
    readme = render_qmd_readme()
    assert '"mcpServers"' in readme
    assert '"command": "qmd"' in readme
    assert "claude_desktop_config.json" in readme


def test_readme_warns_about_folder_context_preservation():
    """The _context.md files from #60 are preserved in the copy — this
    is a deliberate design choice worth documenting so users don't
    think qmd is double-indexing them."""
    readme = render_qmd_readme()
    assert "_context.md" in readme


# ─── render_index_script ────────────────────────────────────────────────


def test_index_script_is_bash_shebang():
    script = render_index_script()
    assert script.startswith("#!/usr/bin/env bash")


def test_index_script_runs_qmd_index():
    script = render_index_script()
    assert "qmd index ." in script


def test_index_script_has_install_hint_on_missing_qmd():
    script = render_index_script()
    assert "not found on PATH" in script
    assert "github.com/tobi/qmd" in script


# ─── copy_wiki_tree ─────────────────────────────────────────────────────


def test_copy_wiki_tree_missing_source_returns_zero(tmp_path):
    n = copy_wiki_tree(tmp_path / "nonexistent", tmp_path / "out")
    assert n == 0


def test_copy_wiki_tree_empty_source_returns_zero(tmp_path):
    (tmp_path / "wiki").mkdir()
    n = copy_wiki_tree(tmp_path / "wiki", tmp_path / "out")
    assert n == 0


def test_copy_wiki_tree_preserves_structure(tmp_path):
    src = tmp_path / "wiki"
    (src / "entities").mkdir(parents=True)
    (src / "concepts").mkdir()
    (src / "index.md").write_text("# Index", encoding="utf-8")
    (src / "entities" / "OpenAI.md").write_text("# OpenAI", encoding="utf-8")
    (src / "concepts" / "RAG.md").write_text("# RAG", encoding="utf-8")

    n = copy_wiki_tree(src, tmp_path / "out")
    assert n == 3

    out_wiki = tmp_path / "out" / "wiki"
    assert (out_wiki / "index.md").read_text() == "# Index"
    assert (out_wiki / "entities" / "OpenAI.md").read_text() == "# OpenAI"
    assert (out_wiki / "concepts" / "RAG.md").read_text() == "# RAG"


def test_copy_wiki_tree_skips_non_markdown_files(tmp_path):
    src = tmp_path / "wiki"
    src.mkdir()
    (src / "index.md").write_text("md", encoding="utf-8")
    (src / "image.png").write_bytes(b"\x89PNG")
    (src / "data.json").write_text("{}", encoding="utf-8")

    n = copy_wiki_tree(src, tmp_path / "out")
    assert n == 1
    assert not (tmp_path / "out" / "wiki" / "image.png").exists()
    assert not (tmp_path / "out" / "wiki" / "data.json").exists()


def test_copy_wiki_tree_preserves_context_md_files(tmp_path):
    """_context.md files from #60 must survive the copy."""
    src = tmp_path / "wiki"
    (src / "entities").mkdir(parents=True)
    (src / "entities" / "_context.md").write_text(
        "# Entities context", encoding="utf-8"
    )
    n = copy_wiki_tree(src, tmp_path / "out")
    assert n == 1
    assert (tmp_path / "out" / "wiki" / "entities" / "_context.md").exists()


# ─── export_qmd end-to-end ─────────────────────────────────────────────


def test_export_qmd_empty_wiki_still_produces_manifest_readme_script(tmp_path):
    src = tmp_path / "empty-wiki"
    src.mkdir()
    out = tmp_path / "export"
    summary = export_qmd(out, source_wiki=src)

    assert summary["files_copied"] == 0
    assert (out / "qmd.yaml").exists()
    assert (out / "README.md").exists()
    assert (out / "index.sh").exists()
    assert (out / "wiki").is_dir()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows does not expose POSIX execute bits via stat()",
)
def test_export_qmd_sets_index_script_executable_bit(tmp_path):
    src = tmp_path / "wiki"
    src.mkdir()
    out = tmp_path / "export"
    export_qmd(out, source_wiki=src)
    mode = (out / "index.sh").stat().st_mode
    assert mode & stat.S_IXUSR, "index.sh must have owner-execute bit set"


def test_export_qmd_copies_nested_wiki_tree(tmp_path):
    src = tmp_path / "wiki"
    (src / "sources" / "demo-proj").mkdir(parents=True)
    (src / "sources" / "demo-proj" / "2026-04-09-demo.md").write_text(
        "# Demo session", encoding="utf-8"
    )
    (src / "entities").mkdir()
    (src / "entities" / "OpenAI.md").write_text("# OpenAI", encoding="utf-8")
    (src / "projects").mkdir()
    (src / "projects" / "demo-proj.md").write_text(
        "# demo-proj", encoding="utf-8"
    )

    out = tmp_path / "export"
    summary = export_qmd(out, source_wiki=src, collection_name="nested-test")

    assert summary["files_copied"] == 3
    assert summary["collection"] == "nested-test"
    assert (out / "wiki" / "sources" / "demo-proj" / "2026-04-09-demo.md").exists()
    assert (out / "wiki" / "entities" / "OpenAI.md").exists()
    assert (out / "wiki" / "projects" / "demo-proj.md").exists()

    # Manifest must reflect the custom collection name
    manifest = (out / "qmd.yaml").read_text()
    assert "collection: nested-test" in manifest


def test_export_qmd_is_idempotent_on_rerun(tmp_path):
    """Running export_qmd twice against the same source + out should
    produce byte-identical results (apart from mtimes)."""
    src = tmp_path / "wiki"
    src.mkdir()
    (src / "index.md").write_text("# Hi", encoding="utf-8")

    out = tmp_path / "export"
    export_qmd(out, source_wiki=src)
    first_manifest = (out / "qmd.yaml").read_text()
    first_readme = (out / "README.md").read_text()

    export_qmd(out, source_wiki=src)
    second_manifest = (out / "qmd.yaml").read_text()
    second_readme = (out / "README.md").read_text()

    assert first_manifest == second_manifest
    assert first_readme == second_readme


def test_export_qmd_returns_out_dir_string(tmp_path):
    src = tmp_path / "wiki"
    src.mkdir()
    out = tmp_path / "export"
    summary = export_qmd(out, source_wiki=src)
    assert summary["out_dir"] == str(out)
