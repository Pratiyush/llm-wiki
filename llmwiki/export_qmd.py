"""qmd export adapter — ship llmwiki output as a [tobi/qmd](https://github.com/tobi/qmd)
collection (v0.6 · closes #59).

Karpathy's LLM Wiki gist explicitly recommends qmd for "local search engines
for wiki traversal at scale". Our own search index is a client-side fuzzy
JSON blob — fine up to ~500 pages, degrades past that. qmd ships a mature
hybrid-search stack (BM25 + vector embeddings + LLM reranking) plus MCP
integration so Claude Desktop / Cursor can query it directly.

Rather than competing with qmd, this exporter makes it trivial for a user
to point qmd at their compiled llmwiki and get the big-boy search stack
for free. Run:

    python3 -m llmwiki export-qmd --out /tmp/my-wiki-qmd
    cd /tmp/my-wiki-qmd
    ./index.sh          # runs qmd index against the copied markdown
    # follow the printed Claude Desktop MCP snippet to wire it up

The exporter does not depend on qmd being installed — it just writes a
self-contained directory that qmd can consume. We stay stdlib-only and
let the user bring their own qmd binary.

What lands in the export directory:

    <out>/
    ├── qmd.yaml              # collection manifest (glob patterns + metadata)
    ├── README.md             # how to index + how to wire into Claude Desktop
    ├── index.sh              # optional one-liner for running `qmd index .`
    └── wiki/                 # copy of every .md file from the source wiki
        ├── sources/
        ├── entities/
        ├── concepts/
        ├── syntheses/
        ├── projects/
        ├── _context.md       # folder context files survive the copy (#60)
        ├── index.md
        ├── overview.md
        └── log.md

The folder context `.md` files from #60 are preserved in the copy so qmd's
own context system can read them — the two conventions are deliberately
compatible (both borrowed from qmd's original pattern).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from llmwiki import REPO_ROOT

# Glob patterns that qmd will index as part of the collection. One
# pattern per "layer" of the wiki so the user can weight / filter by
# type if they want. Keep these stable — downstream qmd configs may
# reference them by name.
_GLOB_PATTERNS = [
    ("sources", "wiki/sources/**/*.md"),
    ("entities", "wiki/entities/**/*.md"),
    ("concepts", "wiki/concepts/**/*.md"),
    ("syntheses", "wiki/syntheses/**/*.md"),
    ("projects", "wiki/projects/**/*.md"),
    ("top_level", "wiki/*.md"),
]


# ─── manifest + readme + shell script render ─────────────────────────────


def render_qmd_manifest(collection_name: str = "llmwiki") -> str:
    """Return the contents of `qmd.yaml` — the collection manifest.

    Format is a minimal YAML doc: collection name, version, description,
    and a list of glob patterns grouped by layer. Follows the shape in
    tobi/qmd's examples (keys: `collection`, `version`, `description`,
    `patterns`)."""
    lines = [
        f"collection: {collection_name}",
        "version: 1",
        'description: "LLM wiki compiled from Claude Code / Codex CLI / Cursor / Obsidian sessions, exported for hybrid qmd search."',
        "patterns:",
    ]
    for name, pattern in _GLOB_PATTERNS:
        lines.append(f"  - name: {name}")
        lines.append(f'    glob: "{pattern}"')
    lines.append("")  # trailing newline
    return "\n".join(lines)


def render_qmd_readme(collection_name: str = "llmwiki") -> str:
    """Return the contents of the exported `README.md`. Explains how to
    index the collection and how to wire qmd into Claude Desktop as an
    MCP server pointing at this directory."""
    return f"""# {collection_name} — qmd export

This directory is a [tobi/qmd](https://github.com/tobi/qmd) collection
exported from an [llmwiki](https://github.com/Pratiyush/llm-wiki). Point
qmd at this folder and you get a hybrid BM25 + vector + LLM-rerank search
index over every page in the original wiki, plus MCP integration so
Claude Desktop, Cursor, or any other MCP-aware agent can query it
directly.

## 1. Build the qmd index

You need qmd installed. See [qmd's README](https://github.com/tobi/qmd#installation)
for install instructions (Node / TypeScript).

Then, from this directory:

```bash
./index.sh            # or: qmd index .
```

That builds a local vector index from the `wiki/` subtree under the patterns
declared in `qmd.yaml`. Re-run after any `llmwiki build` to pick up new
pages.

## 2. Query from the command line

```bash
qmd search . "why did we pick rust for the blog engine"
```

qmd returns a ranked list of matching pages with scores and excerpts.

## 3. Wire qmd into Claude Desktop

Add this block to your Claude Desktop MCP config
(`~/Library/Application Support/Claude/claude_desktop_config.json` on
macOS):

```json
{{
  "mcpServers": {{
    "{collection_name}": {{
      "command": "qmd",
      "args": ["mcp", "--collection", "{collection_name}", "--root", "{{ABSOLUTE_PATH_TO_THIS_DIR}}"]
    }}
  }}
}}
```

Replace `{{ABSOLUTE_PATH_TO_THIS_DIR}}` with the real path of this folder.
Restart Claude Desktop; you'll see a new MCP server listed and can ask
Claude to search the wiki by name.

## 4. Re-export when the wiki changes

Re-run `llmwiki export-qmd --out <path>` whenever you rebuild the wiki,
or add a git hook / watcher to do it automatically. The export is
idempotent: existing files are overwritten, and unchanged content
produces byte-identical output.

## File layout

```
{collection_name}/
├── qmd.yaml        # qmd collection manifest
├── README.md       # this file
├── index.sh        # one-liner: `qmd index .`
└── wiki/           # copy of every markdown page from the source wiki
    ├── sources/
    ├── entities/
    ├── concepts/
    ├── syntheses/
    ├── projects/
    ├── _context.md # folder context files survive the copy
    ├── index.md
    ├── overview.md
    └── log.md
```

Folder-context files (`_context.md` from llmwiki's #60) are preserved in
the export. qmd's own context system reads them — the two conventions
are deliberately compatible, since llmwiki's `_context.md` convention
was borrowed from qmd.

## Why?

Karpathy's LLM Wiki gist explicitly recommends qmd for "local search
engines for wiki traversal at scale." llmwiki's built-in search is a
client-side JSON fuzzy index, fine up to a few hundred pages. Past
that, qmd's hybrid stack wins by a mile. Rather than re-implementing
qmd's search inside llmwiki, this exporter makes it trivial to run
both side by side.
"""


def render_index_script() -> str:
    """Return a tiny shell script that runs `qmd index .` in the
    collection directory. Saves the user one command."""
    return (
        "#!/usr/bin/env bash\n"
        "# llmwiki qmd exporter — one-liner to build the qmd index.\n"
        "# Requires qmd to be installed: https://github.com/tobi/qmd\n"
        'set -e\n'
        'cd "$(dirname "$0")"\n'
        'if ! command -v qmd >/dev/null 2>&1; then\n'
        '  echo "error: qmd not found on PATH. Install it first:" >&2\n'
        '  echo "  https://github.com/tobi/qmd#installation" >&2\n'
        '  exit 1\n'
        'fi\n'
        'qmd index .\n'
    )


# ─── file copying ────────────────────────────────────────────────────────


def _iter_wiki_markdown(wiki_dir: Path) -> Iterable[Path]:
    """Yield every `.md` file under `wiki_dir`. Stable order for
    deterministic exports."""
    if not wiki_dir.is_dir():
        return
    for path in sorted(wiki_dir.rglob("*.md")):
        yield path


def copy_wiki_tree(
    source_wiki: Path,
    dest_root: Path,
) -> int:
    """Copy every `.md` file under `source_wiki` into `dest_root/wiki/`,
    preserving the relative directory structure. Returns the number of
    files copied. Creates the destination tree as needed."""
    if not source_wiki.is_dir():
        return 0
    dest_wiki = dest_root / "wiki"
    n = 0
    for src in _iter_wiki_markdown(source_wiki):
        rel = src.relative_to(source_wiki)
        dst = dest_wiki / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    return n


# ─── entry point ─────────────────────────────────────────────────────────


def export_qmd(
    out_dir: Path,
    source_wiki: Path | None = None,
    collection_name: str = "llmwiki",
) -> dict[str, int | str]:
    """Write a self-contained qmd collection to `out_dir`.

    Returns a summary dict so the CLI can print something useful:
    `{"collection": name, "files_copied": N, "out_dir": str}`.

    Empty wiki trees still produce a valid export (manifest + README +
    script + empty `wiki/` folder) so the user can re-run after
    populating pages without re-configuring the export directory.
    """
    if source_wiki is None:
        source_wiki = REPO_ROOT / "wiki"

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qmd.yaml").write_text(
        render_qmd_manifest(collection_name), encoding="utf-8"
    )
    (out_dir / "README.md").write_text(
        render_qmd_readme(collection_name), encoding="utf-8"
    )
    script_path = out_dir / "index.sh"
    script_path.write_text(render_index_script(), encoding="utf-8")
    # Make index.sh executable. shutil.copy2 preserves mode, but we
    # wrote the file fresh so stat it and chmod +x.
    import os
    os.chmod(script_path, 0o755)

    # Copy wiki/ subtree (preserving folder structure for sources/,
    # entities/, etc.). Empty wiki tree is valid — produces an empty
    # wiki/ folder in the export.
    (out_dir / "wiki").mkdir(exist_ok=True)
    files_copied = copy_wiki_tree(source_wiki, out_dir)

    return {
        "collection": collection_name,
        "files_copied": files_copied,
        "out_dir": str(out_dir),
    }
