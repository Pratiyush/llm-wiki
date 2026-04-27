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
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from llmwiki import REPO_ROOT
# #py-m1 (#587) / #arch-h5 (#610): import directly from _frontmatter
# instead of via build.py. The build module pulls in 145+ transitive
# imports; the parser sits cleanly in _frontmatter.py with no deps.
from llmwiki._frontmatter import parse_frontmatter
from llmwiki.synth.base import BaseSynthesizer, DummySynthesizer


# G-21 (#307): shell- and URL-unsafe chars we scrub from slugs at
# synthesize-time. Spaces → hyphens; filesystem-reserved + Windows-
# unsafe chars → hyphens; collapse repeats.
_SLUG_UNSAFE = re.compile(r'[\s/\\:*?"<>|]+')
_SLUG_DASH_RUN = re.compile(r"-{2,}")


def _normalise_slug(raw: str) -> str:
    """Return a URL-safe + shell-safe slug. Preserves case + unicode.

    Examples:
      ``"00 - Master Framework Index"`` → ``"00-Master-Framework-Index"``
      ``"path/with/slashes"``            → ``"path-with-slashes"``
      ``"weird:chars<here>"``            → ``"weird-chars-here"``
    """
    if not raw:
        return "unknown"
    cleaned = _SLUG_UNSAFE.sub("-", raw)
    # Collapse runs of consecutive dashes so "00 - X" doesn't become
    # "00---X" — consecutive hyphens are ugly in URLs and filesystems.
    cleaned = _SLUG_DASH_RUN.sub("-", cleaned).strip("-")
    return cleaned or "unknown"


def resolve_backend(
    cfg: Optional[dict[str, Any]] = None,
) -> BaseSynthesizer:
    """Pick a synthesizer backend from ``cfg["synthesis"]["backend"]``.

    Supported values:
      - ``"dummy"`` (default) — canned offline backend for previews/tests
      - ``"ollama"`` — local Ollama HTTP backend (#35)
      - ``"agent"`` — defer to the running Claude Code / Codex CLI
        agent (#316). Writes pending prompts to
        ``.llmwiki-pending-prompts/`` for the slash-command layer to
        pick up on the next agent turn.  No HTTP, no API key.

    Unknown values fall back to the dummy backend with a warning so a
    typo in config.json doesn't crash sync.
    """
    synth_cfg = (cfg or {}).get("synthesis", {}) or {}
    name = (synth_cfg.get("backend") or "dummy").strip().lower()

    if name == "ollama":
        # Imported lazily so the `urllib`-based module isn't loaded when
        # users stick with the default dummy backend.
        from llmwiki.synth.ollama import OllamaSynthesizer, load_ollama_config

        return OllamaSynthesizer(config=load_ollama_config(cfg))

    if name in {"agent", "agent_delegate", "agent-delegate"}:
        # Imported lazily — the agent backend is a thin file-I/O layer
        # but we keep symmetry with the other backends' lazy import
        # pattern so ``import llmwiki.synth.pipeline`` stays cheap.
        from llmwiki.synth.agent_delegate import AgentDelegateSynthesizer

        return AgentDelegateSynthesizer()

    if name != "dummy":
        import logging
        logging.getLogger(__name__).warning(
            "Unknown synthesis.backend %r — falling back to dummy", name
        )
    return DummySynthesizer()

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


def _resolve_state_file(state_file: Optional[Path] = None) -> Path:
    """Return the synth state-file path.

    #420: when running in vault-overlay mode, the state file must live
    *under the vault root*, not the repo root — otherwise two different
    vaults synthesised against the same repo silently share idempotency
    state and one vault's run marks the other vault's files unchanged.
    Callers pass ``state_file`` explicitly when in vault mode; default
    falls back to the repo-root location for the no-vault case.
    """
    return state_file if state_file is not None else STATE_FILE


def _load_state(state_file: Optional[Path] = None) -> dict[str, float]:
    """Load the mtime state file. Returns {relative_path: mtime}.

    #sec-16 (#560): validate the schema before trusting it. A
    corrupted or hand-edited state file used to be returned verbatim,
    which then crashed every downstream consumer that expected
    `{str: float}`. Now: must be a dict, every value must be int/float,
    every key must be str. Anything else → reset to empty so synthesis
    re-runs from scratch (worst case: extra work, never wrong work).
    """
    target = _resolve_state_file(state_file)
    if not target.is_file():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, (int, float)):
            out[k] = float(v)
        # Other shapes silently dropped — caller treats as "needs synth"
    return out


def _save_state(state: dict[str, float], state_file: Optional[Path] = None) -> None:
    target = _resolve_state_file(state_file)
    target.write_text(
        json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
    )


def _append_log(
    title: str,
    *,
    log_path: Optional[Path] = None,
    operation: str = "synthesize",
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Append a rich structured entry to wiki/log.md.

    Parameters
    ----------
    title : str
        Human-readable title for the log entry (e.g. "project/slug").
    log_path : Path, optional
        Override for the log file path — used by tests to avoid writing
        to the real wiki/log.md.  Defaults to ``WIKI_LOG``.
    operation : str
        Operation type: synthesize, ingest, query, lint, build, sync.
    details : dict, optional
        Rich details — created pages, updated pages, entities extracted, etc.
    """
    target = log_path or WIKI_LOG
    if not target.parent.exists():
        return

    # Auto-archive when log exceeds 50 KB
    _auto_archive_log(target)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"\n## [{date_str}] {operation} | {title}\n"]
    if details:
        if details.get("processed"):
            lines.append(f"- Processed: {details['processed']}\n")
        if details.get("created"):
            lines.append(f"- Created: {', '.join(details['created'])}\n")
        if details.get("updated"):
            lines.append(f"- Updated: {', '.join(details['updated'])}\n")
        if details.get("entities"):
            lines.append(f"- Entities extracted: {', '.join(details['entities'])}\n")
        if details.get("errors"):
            lines.append(f"- Errors: {len(details['errors'])}\n")
    with open(target, "a", encoding="utf-8") as f:
        f.writelines(lines)


LOG_ARCHIVE_THRESHOLD = 50 * 1024  # 50 KB


def _auto_archive_log(log_path: Path) -> Optional[Path]:
    """Archive log.md when it exceeds 50 KB. Returns archive path or None."""
    if not log_path.is_file():
        return None
    if log_path.stat().st_size < LOG_ARCHIVE_THRESHOLD:
        return None

    year = datetime.now(timezone.utc).strftime("%Y")
    archive = log_path.parent / f"log-archive-{year}.md"

    content = log_path.read_text(encoding="utf-8")
    # Keep the header (first 5 lines), archive the rest
    lines = content.split("\n")
    header = "\n".join(lines[:5])
    body = "\n".join(lines[5:])

    # G-10 (#296): seed frontmatter on first write so lint's
    # frontmatter_completeness rule doesn't fail on the archive file.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    first_write = not archive.is_file()
    if first_write:
        archive.write_text(
            f'---\ntitle: "Wiki log archive — {year}"\n'
            f'type: navigation\nauto_generated: true\n'
            f'last_updated: "{today}"\n---\n',
            encoding="utf-8",
        )

    # Append to archive
    with open(archive, "a", encoding="utf-8") as f:
        f.write(f"\n# Archived from log.md — {year}\n\n")
        f.write(body)

    # Reset log to header only
    log_path.write_text(header + "\n\n---\n", encoding="utf-8")
    return archive


_SOURCES_HEADING = re.compile(r"^##\s+Sources\s*$", re.MULTILINE)
_NEXT_H2 = re.compile(r"^##\s+", re.MULTILINE)


def _rebuild_index(wiki_dir: Path) -> Optional[Path]:
    """Rewrite the ``## Sources`` section of ``wiki/index.md`` (G-09 · #295).

    Walks ``wiki_dir/sources/**/*.md`` and emits one bullet per source
    page, preserving every other section (Overview, Entities, Concepts,
    hand-curated text) untouched.  If ``wiki/index.md`` is missing the
    caller gets a freshly seeded index with just Sources in it.
    """
    index = wiki_dir / "index.md"
    sources_dir = wiki_dir / "sources"
    if not sources_dir.is_dir():
        return None

    # Collect (relpath, title, one-line-summary) for every source page.
    bullets: list[str] = []
    for p in sorted(sources_dir.rglob("*.md")):
        if p.name.startswith("_"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _ = parse_frontmatter(text)
        rel = p.relative_to(wiki_dir).as_posix()
        title = meta.get("title") or p.stem
        date = str(meta.get("date", "")).strip()
        project = meta.get("project", "")
        suffix_parts: list[str] = []
        if project:
            suffix_parts.append(str(project))
        if date:
            suffix_parts.append(date)
        suffix = f" — {' · '.join(suffix_parts)}" if suffix_parts else ""
        bullets.append(f"- [{title}]({rel}){suffix}")

    sources_block = "## Sources\n" + (
        "\n".join(bullets) if bullets else "*(none yet)*"
    ) + "\n"

    if index.is_file():
        original = index.read_text(encoding="utf-8")
    else:
        original = (
            "# Wiki Index\n\n"
            "This file is auto-maintained by synthesize. "
            "Update-in-place only inside this file — sections outside "
            "`## Sources` are preserved.\n\n"
            "## Sources\n*(placeholder)*\n"
        )

    match = _SOURCES_HEADING.search(original)
    if not match:
        # No Sources section yet — append one at the end.
        new_text = original.rstrip() + "\n\n" + sources_block
    else:
        start = match.start()
        # Find the next `## ` heading *after* the Sources heading.
        tail = original[match.end():]
        next_match = _NEXT_H2.search(tail)
        if next_match:
            end = match.end() + next_match.start()
        else:
            end = len(original)
        new_text = original[:start] + sources_block + "\n" + original[end:]

    # Only write when content changes — avoids bumping mtime needlessly.
    if not index.is_file() or index.read_text(encoding="utf-8") != new_text:
        index.write_text(new_text, encoding="utf-8")
    return index


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


# ─── #351: AI-suggested tags ──────────────────────────────────────────

# Emitted by the LLM as the first line of its response — we strip it
# from the body before writing, merge the tags into the frontmatter.
# Format: ``<!-- suggested-tags: a, b, c -->``
_SUGGESTED_TAGS_RE = re.compile(
    r"^\s*<!--\s*suggested-tags:\s*(?P<body>[^>]*?)\s*-->\s*\n?",
    re.IGNORECASE,
)

# Cap on AI-suggested tags per page (deterministic baseline is separate
# and never counted against this budget).  5 keeps the frontmatter list
# readable and prevents runaway tag-space growth on noisy sessions.
_AI_TAG_CAP = 5

# Tags the LLM sometimes proposes that duplicate the deterministic
# baseline or add no value — drop silently so we don't pollute the tag
# space with boilerplate the pipeline already emits.
_AI_TAG_STOPWORDS = frozenset({
    "session-transcript", "session", "claude-code", "codex-cli", "cursor",
    "copilot-chat", "gemini-cli", "opencode", "chatgpt", "obsidian",
    "claude", "gpt", "gemini", "llama", "opus",
    "summary", "discussion", "conversation", "transcript",
    # Empty-ish noise from malformed LLM responses.
    "", "-", "tag", "tags",
})


def _extract_suggested_tags(body: str) -> tuple[list[str], str]:
    """Pull the ``<!-- suggested-tags: … -->`` block off the top of
    ``body`` and return ``(tags, cleaned_body)``.

    Invariants:

    * Missing / malformed block → ``([], body)`` (body untouched).
    * Tags are kebab-cased + lowercased + deduped preserving order.
    * Empty strings / stop-words filtered out.
    * Hard-capped at :data:`_AI_TAG_CAP` before stop-word filtering so
      a noisy LLM can't drown out the cap check.

    Runs in pure Python — no LLM call.  This just parses whatever the
    synthesizer already produced.
    """
    m = _SUGGESTED_TAGS_RE.match(body)
    if not m:
        return [], body
    raw = m.group("body") or ""
    cleaned_body = body[m.end():]
    # Split on comma, normalise each.
    tags: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        t = part.strip().lower().replace(" ", "-")
        if not t or t in seen or t in _AI_TAG_STOPWORDS:
            continue
        tags.append(t)
        seen.add(t)
        if len(tags) >= _AI_TAG_CAP:
            break
    return tags, cleaned_body


def _merge_tags(
    baseline: list[str],
    suggested: list[str],
    existing: Optional[list[str]] = None,
) -> list[str]:
    """Merge the three tag sources into the final frontmatter list.

    Precedence (first-win, order preserved):

    1. Maintainer-curated ``existing`` tags (preserve on re-synthesize).
    2. Deterministic ``baseline`` (adapter + project + model family).
    3. AI-``suggested`` topical tags — only if they don't collide with
       or near-duplicate something already in 1 or 2.

    Near-duplicate detection uses ``tags.near_duplicate_tags`` so we
    reject ``prompt-cache`` when ``prompt-caching`` is already present.
    """
    # Local import to avoid a circular at module load.
    from llmwiki.tags import near_duplicate_tags, TagEntry

    out: list[str] = []
    seen: set[str] = set()

    def _push(tag: str) -> None:
        t = tag.strip()
        if not t:
            return
        key = t.lower()
        if key in seen:
            return
        out.append(t)
        seen.add(key)

    for t in (existing or []):
        _push(t)
    for t in baseline:
        _push(t)
    # For each suggested tag, skip if a near-duplicate already exists.
    # Uses a tighter threshold (0.80) than the CLI default (0.85) — we
    # want auto-merge to be conservative so ``prompt-cache`` (0.846 vs
    # ``prompt-caching``) gets rejected at ingest time.  Maintainers can
    # still add it explicitly via ``llmwiki tag add``.
    if suggested:
        existing_snapshot = list(out)
        for candidate in suggested:
            candidate_lc = candidate.lower()
            # Cheap prefix check: one is a prefix of the other.
            def _substr_near(a: str, b: str) -> bool:
                a_l, b_l = a.lower(), b.lower()
                if a_l == b_l:
                    return True
                shorter, longer = sorted((a_l, b_l), key=len)
                return len(shorter) >= 5 and shorter in longer
            if any(_substr_near(candidate, existing_t) for existing_t in existing_snapshot):
                continue
            # Expensive fuzzy check for other near-dupes (typos, plural, etc.).
            entries = [
                TagEntry(page=Path("/virtual"), field="tags", tag=t)
                for t in existing_snapshot + [candidate]
            ]
            dups = near_duplicate_tags(entries, threshold=0.80)
            collides = any(
                candidate_lc in (a.lower(), b.lower()) and a.lower() != b.lower()
                for (a, b, _score) in dups
            )
            if collides:
                continue
            _push(candidate)
            existing_snapshot.append(candidate)
    return out


def _derive_baseline_tags(meta: dict[str, Any]) -> list[str]:
    """Return a never-empty baseline tag list for synthesized source pages.

    Takes the raw session's ``meta["tags"]`` and augments it with tags
    derived from the project slug + model (when the raw list is empty
    or just carries the boilerplate ``[session-transcript]``).  The
    goal: **every** synthesized page leaves the pipeline with at least
    one meaningful tag so filters / graph chips / the new
    ``tags_topics_convention`` lint rule don't see empty lists.
    """
    out: list[str] = []
    seen: set[str] = set()
    # Start with whatever the raw frontmatter shipped.
    for t in meta.get("tags", []) or []:
        t = str(t).strip()
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    # Ensure the adapter source stamp (claude-code / codex-cli / obsidian / …)
    # appears at least as session-transcript so routing by source stays cheap.
    if "session-transcript" not in seen and "claude-code" not in seen:
        out.append("session-transcript")
        seen.add("session-transcript")
    # Add the project slug as a tag so filters-by-project work out-of-the-box.
    project = str(meta.get("project", "") or "").strip()
    if project and project != "unknown" and project not in seen:
        out.append(project)
        seen.add(project)
    # Model family as a coarse bucket (claude-sonnet-4-6 → claude).
    model = str(meta.get("model", "") or "").strip().lower()
    for family in ("claude", "gpt", "gemini", "llama", "opus"):
        if family in model and family not in seen:
            out.append(family)
            seen.add(family)
            break
    return out


def _build_source_page(
    meta: dict[str, Any],
    synthesized_body: str,
    existing_page_path: Optional[Path] = None,
) -> str:
    """Combine frontmatter + synthesized body into a full wiki source page.

    #351: If the ``synthesized_body`` starts with a
    ``<!-- suggested-tags: ... -->`` block (emitted by the LLM per the
    ``source_page.md`` prompt), the tags are extracted, de-duplicated
    against the deterministic baseline, and merged into the frontmatter.
    The comment is stripped from the body so it never reaches the
    rendered site.

    If ``existing_page_path`` points at an existing wiki source file,
    its current frontmatter ``tags`` are preserved verbatim (maintainer
    curation is never overwritten on re-synthesize).
    """
    slug = meta.get("slug", "unknown")
    title = meta.get("title", f"Source: {slug}")
    project = meta.get("project", "unknown")
    date = meta.get("date", "")
    model = meta.get("model", "")
    source_file = meta.get("source_file", "")

    # #351: pull AI-suggested tags off the top of the body.
    ai_tags, clean_body = _extract_suggested_tags(synthesized_body)

    # Preserve any maintainer-curated tags on re-synthesize.
    # #py-h5 (#584): the broad `except Exception` was eating real
    # parse failures + unicode errors silently, dropping the curated
    # tags on every regression. Narrow to the failures that are
    # actually expected here (file read OSError, frontmatter format
    # issues): everything else (MemoryError, KeyboardInterrupt,
    # surprise type errors) bubbles up so the regression is visible
    # instead of silently producing a tag-loss diff.
    existing_tags: list[str] = []
    if existing_page_path is not None and existing_page_path.exists():
        try:
            existing_meta, _existing_body = parse_frontmatter(
                existing_page_path.read_text(encoding="utf-8")
            )
            existing_tags = list(existing_meta.get("tags", []) or [])
        except (OSError, ValueError, UnicodeDecodeError) as e:
            # Log loud — silent drop is what #584 was about.
            import sys as _sys
            print(
                f"warning: could not preserve tags from "
                f"{existing_page_path}: {e}",
                file=_sys.stderr,
            )
            existing_tags = []

    baseline = _derive_baseline_tags(meta)
    tags = _merge_tags(baseline, ai_tags, existing_tags)

    fm = [
        "---",
        f'title: "{title}"',
        "type: source",
        f"tags: [{', '.join(tags)}]",
        f"date: {date}",
        f"source_file: {source_file}",
        f"project: {project}",
        f"model: {model}",
        f"last_updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "---",
        "",
    ]
    return "\n".join(fm) + clean_body


def synthesize_new_sessions(
    backend: Optional[BaseSynthesizer] = None,
    raw_dir: Optional[Path] = None,
    wiki_sources_dir: Optional[Path] = None,
    dry_run: bool = False,
    force: bool = False,
    log_path: Optional[Path] = None,
    state_file: Optional[Path] = None,
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
    state = {} if force else _load_state(state_file)
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
        raw_slug = meta.get("slug", p.stem)
        project = meta.get("project", p.parent.name)
        rel = str(p.relative_to(raw_dir or RAW_SESSIONS))

        # G-21 (#307): normalise slug — spaces → hyphens, strip filesystem-
        # unsafe chars so the output filename is URL-safe + shell-safe.
        slug = _normalise_slug(raw_slug)

        # G-06 (#292): prepend the session date to prevent silent slug
        # collisions. Claude Code's 3-word auto-slugs collide often (12×
        # `flickering-orbiting-fern` in one corpus). Output path now
        # `wiki/sources/<project>/<YYYY-MM-DD>-<slug>.md`. Falls back to
        # just the slug when no date is present (preserves old tests).
        date = str(meta.get("date", "")).strip()
        filename = f"{date}-{slug}" if date else slug

        try:
            # #py-h7 (#585): pass the raw template — backends own rendering.
            # The pre-render here used to interpolate {body} and {meta}
            # before handing the result to backends, but that fought with
            # the BaseSynthesizer contract ("prompt_template is the
            # contents of prompts/source_page.md with {body} and {meta}
            # placeholders"). Worse, the pipeline pre-render formatted
            # meta as `key: value\n` lines while OllamaSynthesizer's own
            # _render_prompt formats meta as JSON — so Ollama users
            # silently got the pipeline's textual format instead of the
            # JSON its prompts were tuned for. Now: pipeline hands over
            # the unrendered template; each backend renders it with the
            # format it was designed against.
            synthesized = backend.synthesize_source_page(body, meta, prompt_template)

            # Build the full wiki source page.
            # #351: pass the existing path so maintainer-curated tags
            # are preserved on re-synthesize.
            out_dir = sources_out / project
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{filename}.md"
            page_content = _build_source_page(
                meta, synthesized, existing_page_path=out_path
            )
            out_path.write_text(page_content, encoding="utf-8")

            # Update state
            state[rel] = p.stat().st_mtime
            summary["synthesized"] += 1

            # G-08 (#294): log uses a clean separator so slugs with
            # spaces don't break awk/sed parsing. See also G-20/#306
            # for the batched summary emitted after the loop.
            print(f"  synthesized: {project} → {filename}")

        except Exception as e:
            summary["errors"].append(f"{slug}: {e}")
            summary["skipped"] += 1
            print(f"  error: {slug}: {e}")

    # G-20 (#306): emit ONE summary log entry per invocation, not one
    # per page. Includes project counts + error count. The old per-page
    # entries flooded wiki/log.md (60+ lines per run).
    if summary["synthesized"] > 0 or summary["errors"]:
        projects_touched: dict[str, int] = {}
        for p, meta, _ in new_files:
            project = meta.get("project", p.parent.name)
            projects_touched[project] = projects_touched.get(project, 0) + 1
        _append_log(
            f"{summary['synthesized']} sessions across {len(projects_touched)} projects",
            log_path=log_path,
            operation="synthesize",
            details={
                "processed": summary["synthesized"],
                "created": sorted(projects_touched.keys()),
                "errors": summary["errors"],
            },
        )

    _save_state(state, state_file)

    # G-09 (#295): rebuild wiki/index.md so lint's index_sync rule
    # passes on fresh synthesized corpora. Synthesize is authoritative
    # for `## Sources` — the index reflects whatever's on disk now.
    # #arch-m7 (#619): gate behind a "did anything actually change?"
    # check. The index rebuild walks the entire wiki + parses every
    # frontmatter; on a 5k-page corpus that's seconds. Skip when zero
    # pages were synthesized in this pass.
    if summary.get("synthesized", 0) > 0:
        try:
            _rebuild_index(sources_out.parent)
        except (OSError, ValueError, RuntimeError) as e:
            summary["errors"].append(f"index rebuild: {e}")

    return summary
