"""Obsidian output mode — write the compiled wiki back into an Obsidian vault.

This is the OUTPUT side of the Obsidian adapter. v0.1 only reads FROM a vault
(input mode). v0.2 closes the loop: after you've run /wiki-ingest and have a
compiled wiki under wiki/, this module copies that wiki into a folder inside
your Obsidian vault so you can browse it with Obsidian's graph view, backlinks
panel, and full-text search.

Design:
- Non-destructive by default. It copies files into a target folder inside the
  vault; it never modifies your existing notes.
- Idempotent. Re-running the export overwrites the previous copy.
- Preserves wikilinks. Obsidian's [[wikilink]] syntax is native to this wiki.
- Adds a `## Source` backlink at the bottom of every exported page that links
  back to the generating session for traceability.

Usage:

    from llmwiki.obsidian_output import export_to_vault
    export_to_vault(vault="~/Documents/Obsidian Vault", subfolder="LLM Wiki")

#arch-h3 (#609): the ``llmwiki export-obsidian`` CLI subcommand was
removed in v1.2.0 alongside ``llmwiki watch`` (see docs/UPGRADING.md).
Use the function above directly, or run ``llmwiki sync --vault PATH``
which writes through to Obsidian as part of the regular sync pipeline.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT

WIKI_SOURCE = REPO_ROOT / "wiki"
DEFAULT_SUBFOLDER = "LLM Wiki"

# Directories under wiki/ that we export
EXPORTED_DIRS = ["sources", "entities", "concepts", "syntheses", "comparisons", "questions"]
EXPORTED_ROOT_FILES = ["index.md", "overview.md", "log.md"]


def export_to_vault(
    vault: str | Path,
    subfolder: str = DEFAULT_SUBFOLDER,
    wiki_source: Path = WIKI_SOURCE,
    dry_run: bool = False,
    clean: bool = False,
) -> int:
    """Copy every wiki page into a subfolder of an Obsidian vault.

    Args:
        vault: Path to the Obsidian vault root (the directory that contains
               `.obsidian/`).
        subfolder: Folder name to create inside the vault. Defaults to 'LLM Wiki'.
        wiki_source: Directory to export from. Defaults to `wiki/` in the repo root.
        dry_run: If True, report what would happen without writing.
        clean: If True, delete the target subfolder before copying.

    Returns:
        0 on success, non-zero on error.
    """
    vault_path = Path(vault).expanduser().resolve()
    if not vault_path.exists():
        print(f"error: vault does not exist: {vault_path}", file=sys.stderr)
        return 2

    obsidian_marker = vault_path / ".obsidian"
    if not obsidian_marker.exists():
        print(
            f"warning: {vault_path} does not contain a .obsidian/ folder — "
            "this may not be an Obsidian vault",
            file=sys.stderr,
        )

    if not wiki_source.exists():
        print(f"error: wiki source does not exist: {wiki_source}", file=sys.stderr)
        return 2

    target = vault_path / subfolder
    print(f"==> exporting {wiki_source} → {target}")

    if clean and target.exists():
        if dry_run:
            print(f"  [dry-run] would delete existing {target}")
        else:
            shutil.rmtree(target)
            print(f"  cleaned {target}")

    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)

    n_pages = 0
    n_skipped = 0

    # Export root files (index.md, overview.md, log.md)
    for name in EXPORTED_ROOT_FILES:
        src = wiki_source / name
        if not src.exists():
            n_skipped += 1
            continue
        dst = target / name
        if dry_run:
            print(f"  [dry-run] {src.relative_to(REPO_ROOT)} → {dst.relative_to(vault_path)}")
        else:
            content = src.read_text(encoding="utf-8")
            content = _add_source_backlink(content, src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
        n_pages += 1

    # Export subdirectories
    for sub in EXPORTED_DIRS:
        src_dir = wiki_source / sub
        if not src_dir.exists():
            continue
        dst_dir = target / sub
        for src_file in sorted(src_dir.rglob("*.md")):
            rel = src_file.relative_to(src_dir)
            dst_file = dst_dir / rel
            if dry_run:
                print(f"  [dry-run] {src_file.relative_to(REPO_ROOT)} → {dst_file.relative_to(vault_path)}")
            else:
                content = src_file.read_text(encoding="utf-8")
                content = _add_source_backlink(content, src_file)
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                dst_file.write_text(content, encoding="utf-8")
            n_pages += 1

    # Write a README.md at the root of the exported folder
    readme = _build_readme(n_pages, wiki_source)
    if not dry_run:
        (target / "README.md").write_text(readme, encoding="utf-8")

    print()
    print(
        f"summary: {n_pages} pages exported, {n_skipped} skipped "
        f"(target: {target})"
    )
    return 0


def _add_source_backlink(content: str, source_path: Path) -> str:
    """Append a `## Source` section linking back to the llmwiki source file.

    This gives Obsidian backlinks a stable anchor pointing at the raw markdown
    that generated this page.
    """
    try:
        rel = source_path.relative_to(REPO_ROOT)
    except ValueError:
        rel = source_path
    backlink = (
        f"\n\n---\n\n## llmwiki Source\n\n"
        f"Generated from `{rel}` by [llmwiki](https://github.com/Pratiyush/llm-wiki).\n"
        f"Do not edit directly — re-run `llmwiki build` and `export-obsidian` "
        f"to refresh.\n"
    )
    # If already appended, don't duplicate
    if "## llmwiki Source" in content:
        return content
    return content.rstrip() + backlink


def _build_readme(n_pages: int, wiki_source: Path) -> str:
    return f"""# LLM Wiki (exported)

This folder contains a **read-only export** of an LLM Wiki compiled by
[llmwiki](https://github.com/Pratiyush/llm-wiki) from Claude Code session
transcripts.

- **{n_pages}** pages exported
- **Source:** `{wiki_source}`
- **Do not edit directly.** Changes here will be overwritten the next time you
  run `llmwiki sync --vault PATH` (the dedicated `export-obsidian` subcommand
  was removed in v1.2.0; vault sync now lives under the main `sync` flow).

## Structure

- `index.md` — catalog of all pages
- `overview.md` — living synthesis
- `log.md` — append-only operation log
- `sources/` — one summary per ingested source
- `entities/` — people, projects, tools (TitleCase.md)
- `concepts/` — ideas, patterns (TitleCase.md)
- `syntheses/` — saved query answers
- `comparisons/` — side-by-side diffs
- `questions/` — open questions with state tracking

## How this works with Obsidian

- **Wikilinks** (`[[Name]]`) work natively. Obsidian's graph view will
  display the wiki's internal cross-references.
- **Backlinks** update automatically. Every page has a backlink to the
  llmwiki source at the bottom (`## llmwiki Source`).
- **Search** — Obsidian's full-text search indexes the entire export.
- **Graph view** — every `[[wikilink]]` becomes a node connection.

## Re-exporting

From the llmwiki repo:

```bash
python3 -m llmwiki sync --vault "~/Documents/Obsidian Vault"
```
"""
