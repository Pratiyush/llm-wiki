"""Synthesis pipeline — orchestrates auto-ingest from raw → wiki (v0.5 · #36).

The main entry point is `synthesize_new_sessions()` which:

1. Scans `raw/sessions/` for markdown files
2. Compares against an mtime state file to find NEW files since the last run
3. For each new file, calls the configured synthesizer backend to produce
   a wiki source page
4. Writes `wiki/sources/<slug>.md` with proper frontmatter
5. Updates the mtime state file so re-runs are a no-op
6. Appends to `wiki/log.md`

Idempotency: the pipeline uses `.llmwiki-synth-state.json` (same pattern
as the converter's `.llmwiki-state.json`) to track which files have been
synthesized. Re-running on an unchanged tree is a sub-second no-op.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from llmwiki import REPO_ROOT
from llmwiki.build import parse_frontmatter
from llmwiki.synth.base import BaseSynthesizer, DummySynthesizer

RAW_SESSIONS = REPO_ROOT / "raw" / "sessions"
WIKI_SOURCES = REPO_ROOT / "wiki" / "sources"
WIKI_LOG = REPO_ROOT / "wiki" / "log.md"
STATE_FILE = REPO_ROOT / ".llmwiki-synth-state.json"
PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "source_page.md"

# Allow user override of the prompt template: if
# `wiki/prompts/source_page.md` exists, use it instead of the
# built-in one. This lets users customize the synthesis prompt
# without forking the codebase.
USER_PROMPT_OVERRIDE = REPO_ROOT / "wiki" / "prompts" / "source_page.md"


def _load_prompt_template() -> str:
    """Load the synthesis prompt template. User override wins."""
    if USER_PROMPT_OVERRIDE.is_file():
        return USER_PROMPT_OVERRIDE.read_text(encoding="utf-8")
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _load_state() -> dict[str, float]:
    """Load the mtime state file. Returns {relative_path: mtime}."""
    if not STATE_FILE.is_file():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (ValueError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, float]) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
    )


def _append_log(title: str) -> None:
    """Append a synthesis entry to wiki/log.md."""
    if not WIKI_LOG.parent.exists():
        return
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"\n## [{date_str}] synthesize | {title}\n"
    with open(WIKI_LOG, "a", encoding="utf-8") as f:
        f.write(entry)


def _discover_raw_sessions(
    raw_dir: Optional[Path] = None,
) -> list[tuple[Path, dict[str, Any], str]]:
    """Walk raw/sessions/ and return (path, meta, body) for each .md file."""
    root = raw_dir or RAW_SESSIONS
    if not root.is_dir():
        return []
    out: list[tuple[Path, dict[str, Any], str]] = []
    for p in sorted(root.rglob("*.md")):
        if p.name.startswith("_"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        out.append((p, meta, body))
    return out


def _build_source_page(
    meta: dict[str, Any],
    synthesized_body: str,
) -> str:
    """Combine frontmatter + synthesized body into a full wiki source page."""
    slug = meta.get("slug", "unknown")
    title = meta.get("title", f"Source: {slug}")
    project = meta.get("project", "unknown")
    date = meta.get("date", "")
    model = meta.get("model", "")
    source_file = meta.get("source_file", "")

    fm = [
        "---",
        f'title: "{title}"',
        "type: source",
        f"tags: [{', '.join(meta.get('tags', []))}]",
        f"date: {date}",
        f"source_file: {source_file}",
        f"project: {project}",
        f"model: {model}",
        f"last_updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "---",
        "",
    ]
    return "\n".join(fm) + synthesized_body


def synthesize_new_sessions(
    backend: Optional[BaseSynthesizer] = None,
    raw_dir: Optional[Path] = None,
    wiki_sources_dir: Optional[Path] = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Main entry point. Returns a summary dict:

    {
        "total_scanned": int,
        "new_files": int,
        "synthesized": int,
        "skipped": int,
        "errors": list[str],
        "backend": str,
    }
    """
    if backend is None:
        backend = DummySynthesizer()

    if not backend.is_available():
        return {
            "total_scanned": 0,
            "new_files": 0,
            "synthesized": 0,
            "skipped": 0,
            "errors": [f"Backend {backend.name} is not available"],
            "backend": backend.name,
        }

    sources_out = wiki_sources_dir or WIKI_SOURCES
    prompt_template = _load_prompt_template()
    state = {} if force else _load_state()
    sessions = _discover_raw_sessions(raw_dir)

    new_files: list[tuple[Path, dict[str, Any], str]] = []
    for p, meta, body in sessions:
        rel = str(p.relative_to(raw_dir or RAW_SESSIONS))
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if rel in state and state[rel] >= mtime and not force:
            continue
        new_files.append((p, meta, body))

    summary: dict[str, Any] = {
        "total_scanned": len(sessions),
        "new_files": len(new_files),
        "synthesized": 0,
        "skipped": 0,
        "errors": [],
        "backend": backend.name,
    }

    if dry_run:
        summary["skipped"] = len(new_files)
        print(
            f"[dry-run] Would synthesize {len(new_files)} new sessions "
            f"using {backend.name}"
        )
        for p, meta, _ in new_files:
            print(f"  {meta.get('slug', p.stem)}")
        return summary

    for p, meta, body in new_files:
        slug = meta.get("slug", p.stem)
        project = meta.get("project", p.parent.name)
        rel = str(p.relative_to(raw_dir or RAW_SESSIONS))

        try:
            # Call the synthesizer backend
            prompt = prompt_template.replace("{body}", body[:8000])
            prompt = prompt.replace(
                "{meta}",
                "\n".join(f"{k}: {v}" for k, v in meta.items()),
            )
            synthesized = backend.synthesize_source_page(body, meta, prompt)

            # Build the full wiki source page
            page_content = _build_source_page(meta, synthesized)

            # Write to wiki/sources/<project>/<slug>.md
            out_dir = sources_out / project
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{slug}.md"
            out_path.write_text(page_content, encoding="utf-8")

            # Update state
            state[rel] = p.stat().st_mtime
            summary["synthesized"] += 1

            # Append to log
            _append_log(f"{project}/{slug}")

            print(f"  synthesized: {project}/{slug}")

        except Exception as e:
            summary["errors"].append(f"{slug}: {e}")
            summary["skipped"] += 1
            print(f"  error: {slug}: {e}")

    _save_state(state)
    return summary
