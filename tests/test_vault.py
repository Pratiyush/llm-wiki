"""Tests for vault-overlay mode (v1.2.0 · #54)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.vault import (
    Vault,
    VaultFormat,
    VaultLayout,
    _heading_exists,
    _sanitize_filename,
    append_section,
    describe_vault,
    detect_vault_format,
    format_wikilink,
    resolve_vault,
    vault_page_path,
    write_vault_page,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


def _make_obsidian_vault(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".obsidian").mkdir()
    (root / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
    return root


def _make_logseq_vault(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "logseq").mkdir()
    (root / "pages").mkdir()
    (root / "config.edn").write_text(";; logseq config", encoding="utf-8")
    return root


def _make_plain_vault(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "notes.md").write_text("plain notes", encoding="utf-8")
    return root


# ─── detect_vault_format ──────────────────────────────────────────────


def test_detect_obsidian_from_marker_dir(tmp_path: Path):
    v = _make_obsidian_vault(tmp_path / "obs")
    assert detect_vault_format(v) is VaultFormat.OBSIDIAN


def test_detect_logseq_from_marker_dir(tmp_path: Path):
    v = _make_logseq_vault(tmp_path / "log")
    assert detect_vault_format(v) is VaultFormat.LOGSEQ


def test_detect_logseq_from_config_edn_alone(tmp_path: Path):
    v = tmp_path / "edn-only"
    v.mkdir()
    (v / "config.edn").write_text(";; hi", encoding="utf-8")
    # No `logseq/` dir — the `config.edn` alone is enough
    assert detect_vault_format(v) is VaultFormat.LOGSEQ


def test_detect_logseq_wins_over_obsidian_when_both_present(tmp_path: Path):
    # User opened their Logseq vault in Obsidian once, creating .obsidian/.
    # We still want to treat it as Logseq so wikilinks follow the right
    # convention.
    v = _make_logseq_vault(tmp_path / "both")
    (v / ".obsidian").mkdir()
    assert detect_vault_format(v) is VaultFormat.LOGSEQ


def test_detect_plain_with_no_markers(tmp_path: Path):
    v = _make_plain_vault(tmp_path / "plain")
    assert detect_vault_format(v) is VaultFormat.PLAIN


def test_detect_raises_on_missing_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        detect_vault_format(tmp_path / "nope")


def test_detect_raises_on_file_not_directory(tmp_path: Path):
    f = tmp_path / "file.md"
    f.write_text("", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="not a directory"):
        detect_vault_format(f)


# ─── VaultLayout ──────────────────────────────────────────────────────


def test_default_layout_uses_wiki_prefix():
    layout = VaultLayout()
    assert layout.entities == "Wiki/Entities"
    assert layout.concepts == "Wiki/Concepts"
    assert layout.sources == "Wiki/Sources"
    assert layout.syntheses == "Wiki/Syntheses"
    assert layout.candidates == "Wiki/Candidates"


def test_layout_path_for_known_kinds():
    layout = VaultLayout()
    assert layout.path_for("entities") == "Wiki/Entities"
    assert layout.path_for("candidates") == "Wiki/Candidates"


def test_layout_path_for_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown page kind"):
        VaultLayout().path_for("aliens")


def test_layout_is_frozen():
    with pytest.raises(Exception):  # FrozenInstanceError
        VaultLayout().entities = "mutated"  # type: ignore[misc]


def test_custom_layout_overrides_prefix():
    layout = VaultLayout(entities="LLM/People", concepts="LLM/Ideas")
    assert layout.entities == "LLM/People"
    assert layout.path_for("concepts") == "LLM/Ideas"


# ─── Vault dataclass ──────────────────────────────────────────────────


def test_vault_is_frozen(tmp_path: Path):
    v = _make_obsidian_vault(tmp_path / "v")
    vault = resolve_vault(v)
    with pytest.raises(Exception):
        vault.format = VaultFormat.LOGSEQ  # type: ignore[misc]


def test_vault_format_flags(tmp_path: Path):
    obs = resolve_vault(_make_obsidian_vault(tmp_path / "obs"))
    log = resolve_vault(_make_logseq_vault(tmp_path / "log"))
    plain = resolve_vault(_make_plain_vault(tmp_path / "plain"))

    assert obs.is_obsidian and not obs.is_logseq
    assert log.is_logseq and not log.is_obsidian
    assert not plain.is_obsidian and not plain.is_logseq

    assert log.uses_namespace_triple_underscore
    assert not obs.uses_namespace_triple_underscore
    assert not plain.uses_namespace_triple_underscore


def test_resolve_vault_returns_absolute_root(tmp_path: Path):
    v = _make_obsidian_vault(tmp_path / "rel")
    vault = resolve_vault(v)
    assert vault.root.is_absolute()


def test_resolve_vault_accepts_custom_layout(tmp_path: Path):
    v = _make_obsidian_vault(tmp_path / "v")
    layout = VaultLayout(entities="Custom/Entities")
    vault = resolve_vault(v, layout=layout)
    assert vault.layout.entities == "Custom/Entities"


# ─── _sanitize_filename ───────────────────────────────────────────────


def test_sanitize_keeps_safe_chars():
    assert _sanitize_filename("RAG") == "RAG"
    assert _sanitize_filename("Foo_Bar-1") == "Foo_Bar-1"


def test_sanitize_replaces_unsafe_chars():
    assert _sanitize_filename("a<b>c") == "a-b-c"
    assert _sanitize_filename('a"b|c') == "a-b-c"
    assert _sanitize_filename("a/b\\c") == "a-b-c"
    assert _sanitize_filename("a?b*c") == "a-b-c"
    assert _sanitize_filename("a:b") == "a-b"


def test_sanitize_strips_whitespace():
    assert _sanitize_filename("  Foo  ") == "Foo"


# ─── vault_page_path ──────────────────────────────────────────────────


def test_vault_page_path_obsidian_nested(tmp_path: Path):
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"))
    path = vault_page_path(vault, "entities", "RAG")
    assert path == vault.root / "Wiki/Entities" / "RAG.md"


def test_vault_page_path_logseq_flat_namespace(tmp_path: Path):
    vault = resolve_vault(_make_logseq_vault(tmp_path / "v"))
    path = vault_page_path(vault, "entities", "RAG")
    # Logseq flattens via triple underscores, prefix lowercased
    assert path == vault.root / "pages" / "wiki___entities___RAG.md"


def test_vault_page_path_plain_uses_nested_folder(tmp_path: Path):
    vault = resolve_vault(_make_plain_vault(tmp_path / "v"))
    path = vault_page_path(vault, "concepts", "Karpathy")
    assert path == vault.root / "Wiki/Concepts" / "Karpathy.md"


def test_vault_page_path_sanitises_slug(tmp_path: Path):
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"))
    path = vault_page_path(vault, "entities", "a/b")
    assert path.name == "a-b.md"


def test_vault_page_path_raises_on_empty_slug(tmp_path: Path):
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"))
    with pytest.raises(ValueError, match="non-empty"):
        vault_page_path(vault, "entities", "")


def test_vault_page_path_raises_on_whitespace_only_slug(tmp_path: Path):
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"))
    with pytest.raises(ValueError, match="empty string"):
        vault_page_path(vault, "entities", "   ")


def test_vault_page_path_honours_custom_layout(tmp_path: Path):
    layout = VaultLayout(entities="Knowledge/People")
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"), layout=layout)
    path = vault_page_path(vault, "entities", "Karpathy")
    assert path == vault.root / "Knowledge/People" / "Karpathy.md"


# ─── format_wikilink ──────────────────────────────────────────────────


def test_wikilink_obsidian_is_bare_slug(tmp_path: Path):
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"))
    assert format_wikilink(vault, "entities", "RAG") == "[[RAG]]"


def test_wikilink_plain_is_bare_slug(tmp_path: Path):
    vault = resolve_vault(_make_plain_vault(tmp_path / "v"))
    assert format_wikilink(vault, "entities", "RAG") == "[[RAG]]"


def test_wikilink_logseq_namespaces_from_kind(tmp_path: Path):
    vault = resolve_vault(_make_logseq_vault(tmp_path / "v"))
    assert format_wikilink(vault, "entities", "RAG") == "[[wiki/entities/RAG]]"


def test_wikilink_rejects_empty_slug(tmp_path: Path):
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"))
    with pytest.raises(ValueError):
        format_wikilink(vault, "entities", "")


# ─── write_vault_page ─────────────────────────────────────────────────


def test_write_vault_page_creates_parent_dirs(tmp_path: Path):
    target = tmp_path / "Wiki" / "Entities" / "RAG.md"
    returned = write_vault_page(target, "hello")
    assert returned == target
    assert target.read_text(encoding="utf-8") == "hello"


def test_write_vault_page_refuses_overwrite_by_default(tmp_path: Path):
    target = tmp_path / "Foo.md"
    target.write_text("user wrote this", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        write_vault_page(target, "would clobber")
    # User content is untouched
    assert target.read_text(encoding="utf-8") == "user wrote this"


def test_write_vault_page_overwrite_flag_allows_clobber(tmp_path: Path):
    target = tmp_path / "Foo.md"
    target.write_text("old", encoding="utf-8")
    write_vault_page(target, "new", overwrite=True)
    assert target.read_text(encoding="utf-8") == "new"


def test_write_vault_page_is_noop_safe_on_fresh_target(tmp_path: Path):
    target = tmp_path / "New.md"
    write_vault_page(target, "hi")
    # Second call without overwrite should fail loudly, not silently succeed
    with pytest.raises(FileExistsError):
        write_vault_page(target, "again")


# ─── append_section ───────────────────────────────────────────────────


def test_append_section_adds_new_heading(tmp_path: Path):
    target = tmp_path / "RAG.md"
    target.write_text("# RAG\n\nUser wrote this.\n", encoding="utf-8")

    append_section(target, "Connections", "- [[Karpathy]]\n- [[Anthropic]]")

    text = target.read_text(encoding="utf-8")
    assert "User wrote this" in text
    assert "## Connections" in text
    assert "[[Karpathy]]" in text


def test_append_section_is_idempotent(tmp_path: Path):
    target = tmp_path / "RAG.md"
    target.write_text("# RAG\n\n## Connections\n\n- existing\n", encoding="utf-8")
    original = target.read_text(encoding="utf-8")

    append_section(target, "Connections", "- new stuff")

    # Heading already exists → no change
    assert target.read_text(encoding="utf-8") == original


def test_append_section_heading_match_is_case_insensitive(tmp_path: Path):
    target = tmp_path / "RAG.md"
    target.write_text("# RAG\n\n## connections\n\n- existing\n", encoding="utf-8")
    original = target.read_text(encoding="utf-8")

    append_section(target, "Connections", "- should not be added")
    assert target.read_text(encoding="utf-8") == original


def test_append_section_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="missing vault page"):
        append_section(tmp_path / "nope.md", "H", "body")


def test_heading_exists_detects_h2_only():
    # ### H3 with the same text should NOT match — we only look at h2.
    assert _heading_exists("# T\n\n## Foo\n", "Foo")
    assert not _heading_exists("# T\n\n### Foo\n", "Foo")
    assert not _heading_exists("## Bar\n", "Foo")


def test_heading_exists_tolerates_trailing_whitespace():
    assert _heading_exists("## Foo   \n", "Foo")


# ─── describe_vault ───────────────────────────────────────────────────


def test_describe_vault_mentions_format_and_key_paths(tmp_path: Path):
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"))
    out = describe_vault(vault)
    assert "obsidian" in out.lower()
    assert "Wiki/Entities" in out
    assert "Wiki/Concepts" in out


# ─── Round-trip smoke test (issue #54 acceptance criterion) ───────────


def test_roundtrip_obsidian_vault_sync_creates_page_in_right_place(tmp_path: Path):
    """Core acceptance check — given a fresh Obsidian vault, the
    pipeline should be able to create a new entity page inside the
    vault at the configured subpath, then resolve the wikilink from
    another page to it."""
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "vault"))

    # 1. Write a new entity page
    entity_path = vault_page_path(vault, "entities", "RAG")
    write_vault_page(
        entity_path,
        "# RAG\n\nRetrieval-augmented generation.\n",
    )
    assert entity_path.is_file()
    assert entity_path.parent == vault.root / "Wiki/Entities"

    # 2. Another page's body links to it
    link = format_wikilink(vault, "entities", "RAG")
    assert link == "[[RAG]]"

    # 3. Create a source page that references the entity, then append
    #    Connections on a re-sync (idempotently)
    source_path = vault_page_path(vault, "sources", "2026-session")
    write_vault_page(source_path, "# Session\n\nToday we discussed RAG.\n")
    append_section(source_path, "Connections", f"- {link}")
    assert link in source_path.read_text(encoding="utf-8")

    # 4. Idempotency: re-running append doesn't duplicate
    append_section(source_path, "Connections", f"- {link}")
    assert source_path.read_text(encoding="utf-8").count("## Connections") == 1


def test_roundtrip_logseq_vault_uses_namespaced_filenames(tmp_path: Path):
    """Logseq version of the round-trip — wiki pages land under
    ``pages/`` with triple-underscore namespace prefixes and wikilinks
    carry the namespace."""
    vault = resolve_vault(_make_logseq_vault(tmp_path / "vault"))

    entity_path = vault_page_path(vault, "entities", "RAG")
    assert entity_path.parent == vault.root / "pages"
    assert entity_path.name == "wiki___entities___RAG.md"

    link = format_wikilink(vault, "entities", "RAG")
    assert link == "[[wiki/entities/RAG]]"

    write_vault_page(entity_path, "- RAG is retrieval-augmented generation")
    assert entity_path.is_file()


# ─── Edge cases ───────────────────────────────────────────────────────


def test_unicode_slug_preserved(tmp_path: Path):
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"))
    path = vault_page_path(vault, "entities", "日本語")
    assert path.name == "日本語.md"


def test_very_long_slug_allowed(tmp_path: Path):
    vault = resolve_vault(_make_obsidian_vault(tmp_path / "v"))
    long_slug = "A" * 120
    path = vault_page_path(vault, "entities", long_slug)
    assert path.name == f"{long_slug}.md"


# ─── CLI wiring ──────────────────────────────────────────────────────


def test_cli_sync_accepts_vault_flag():
    from llmwiki.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["sync", "--vault", "/tmp/some-vault"])
    assert str(args.vault) == "/tmp/some-vault"


def test_cli_sync_defaults_vault_to_none():
    from llmwiki.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["sync"])
    assert args.vault is None
    assert args.allow_overwrite is False


def test_cli_sync_allow_overwrite_flag():
    from llmwiki.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(
        ["sync", "--vault", "/tmp/v", "--allow-overwrite"]
    )
    assert args.allow_overwrite is True


def test_cli_build_accepts_vault_flag():
    from llmwiki.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["build", "--vault", "/tmp/v"])
    assert str(args.vault) == "/tmp/v"


def test_cli_sync_bad_vault_path_exits_with_error(tmp_path: Path, capsys):
    """cmd_sync should fail fast with exit 2 when --vault points at a
    non-existent path, not blow through conversion first."""
    from llmwiki.cli import build_parser, cmd_sync
    parser = build_parser()
    args = parser.parse_args(
        ["sync", "--vault", str(tmp_path / "does-not-exist"), "--dry-run"]
    )
    rc = cmd_sync(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "does not exist" in err


def test_cli_build_bad_vault_path_exits_with_error(tmp_path: Path, capsys):
    from llmwiki.cli import build_parser, cmd_build
    parser = build_parser()
    args = parser.parse_args(
        ["build", "--vault", str(tmp_path / "nope"), "--out", str(tmp_path / "out")]
    )
    rc = cmd_build(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "does not exist" in err


# ─── Docs guardrail ──────────────────────────────────────────────────


def test_existing_vault_doc_exists():
    from llmwiki import REPO_ROOT
    doc = REPO_ROOT / "docs" / "guides" / "existing-vault.md"
    assert doc.is_file(), (
        "docs/guides/existing-vault.md is a #54 acceptance criterion; "
        "restore it if it went missing"
    )
    text = doc.read_text(encoding="utf-8")
    # Doc must cover the three formats + the non-destructive promise +
    # the --allow-overwrite escape hatch.
    assert "Obsidian" in text and "Logseq" in text and "Plain" in text
    assert "--allow-overwrite" in text
    assert "non-destructive" in text.lower() or "Non-destructive" in text
