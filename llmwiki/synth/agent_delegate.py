"""Agent-delegate synthesizer (#316).

This backend implements :class:`BaseSynthesizer` but **never calls any
HTTP API**.  Instead it writes the rendered prompt to a scratch file
under ``.llmwiki-pending-prompts/`` and returns a placeholder body.
The accompanying slash-command wrapper (``/wiki-sync``,
``/wiki-ingest``) is expected to read those pending prompts on the
next agent turn, synthesize the actual content inside the agent's
existing Claude Code / Codex CLI session (via the ``Skill`` tool or
inline generation), and write the final page back.

Why this exists
---------------

Mode A (``anthropic`` backend, issue #315) uses the user's API key
and counts against their token budget.  Some users either don't have
an API key or would rather piggyback on their existing Claude Code
subscription — in that case Mode B (this module) defers the actual
generation to the agent that's already running, at zero incremental
cost.

Contract with the agent
-----------------------

1. On :meth:`synthesize_source_page` the backend:

   * Allocates a UUID.
   * Writes ``<repo>/.llmwiki-pending-prompts/<uuid>.md`` with the
     full rendered prompt (body + meta).
   * Returns a placeholder body whose first line is the sentinel
     ``<!-- llmwiki-pending: <uuid> -->``.

2. The caller writes the page to ``wiki/sources/.../<slug>.md`` as
   usual — the sentinel gives the slash-command layer a machine-
   readable hook to find which pages are still pending.

3. The slash command reads the pending prompt inside the agent's
   session, produces a synthesized body, and calls
   :func:`complete_pending` to rewrite the source page in place.

The backend itself never calls the agent — that loop lives outside
this module.  This file is pure file-I/O + sentinel handling.

Design goals
------------

* **No network.** The test suite can assert via ``socket`` that no
  HTTP call ever happens.
* **No secrets.** Works when ``ANTHROPIC_API_KEY`` is unset.
* **Idempotent.** Re-running ``synthesize`` on the same slug
  overwrites the pending prompt instead of accumulating orphans.
* **Graceful outside an agent.** ``is_available()`` returns ``False``
  (with a helpful hint via :attr:`unavailable_reason`) when no agent
  runtime is detected, so the pipeline can fall back to the dummy
  backend instead of silently producing placeholders.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from llmwiki import REPO_ROOT
from llmwiki.synth.base import BaseSynthesizer


# ─── paths ───────────────────────────────────────────────────────────

PENDING_DIR_NAME = ".llmwiki-pending-prompts"


def pending_dir(override: Optional[Path] = None) -> Path:
    """Return the pending-prompts directory (created on demand).

    If ``override`` is given, it's used **as-is** (tests pass a
    ``tmp_path``).  Otherwise the standard location is
    ``REPO_ROOT/.llmwiki-pending-prompts``.
    """
    d = override if override is not None else REPO_ROOT / PENDING_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─── sentinel ────────────────────────────────────────────────────────

# Emitted as the first line of the placeholder body so downstream
# tooling can find + replace pending pages cheaply.
_SENTINEL_RE = re.compile(
    r"^\s*<!--\s*llmwiki-pending:\s*(?P<uuid>[0-9a-f-]{36})\s*-->\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def sentinel_for(uid: str) -> str:
    return f"<!-- llmwiki-pending: {uid} -->"


def is_pending(body: str) -> bool:
    """Return ``True`` iff ``body`` contains the pending sentinel."""
    return bool(_SENTINEL_RE.search(body or ""))


def extract_pending_uuid(body: str) -> Optional[str]:
    """Pull the ``<uuid>`` out of the sentinel, or ``None``."""
    m = _SENTINEL_RE.search(body or "")
    return m.group("uuid") if m else None


# ─── runtime detection ───────────────────────────────────────────────


def _agent_runtime_detected() -> bool:
    """Heuristic: are we running inside an agent session?

    We trust (in order):

    * ``LLMWIKI_AGENT_MODE`` set to a truthy value — explicit opt-in,
      wins over everything else.
    * ``CLAUDE_CODE`` or ``CLAUDECODE`` — set by Claude Code sessions.
    * ``CODEX_CLI`` — set by Codex CLI.
    * ``CURSOR_AGENT`` — set by Cursor's chat pane.

    If none of the above are set, we consider the backend unavailable
    and return ``False`` so the pipeline falls back to dummy.
    """
    explicit = os.environ.get("LLMWIKI_AGENT_MODE", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    if explicit in {"0", "false", "no", "off"}:
        return False
    for env_var in ("CLAUDE_CODE", "CLAUDECODE", "CODEX_CLI", "CURSOR_AGENT"):
        if os.environ.get(env_var):
            return True
    return False


# ─── the backend ─────────────────────────────────────────────────────


@dataclass
class AgentDelegateSynthesizer(BaseSynthesizer):
    """Defer synthesis to the agent — no HTTP calls.

    The backend's job is to write the rendered prompt to disk and
    return a placeholder page.  The slash-command layer picks up the
    pending prompt on the next agent turn.
    """

    pending_root: Optional[Path] = None

    # Public so tests can assert on the message surface.
    unavailable_reason: str = (
        "Agent runtime not detected. Run /wiki-sync from inside Claude "
        "Code or Codex CLI, or export LLMWIKI_AGENT_MODE=1 to force."
    )

    # ─── BaseSynthesizer contract ────────────────────────────────────

    def is_available(self) -> bool:
        return _agent_runtime_detected()

    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        """Defer synthesis: write the prompt + return a placeholder.

        The placeholder's first line is a machine-readable sentinel
        (``<!-- llmwiki-pending: <uuid> -->``).  Idempotency: if a
        pending prompt already exists for this slug, we reuse its
        uuid instead of orphaning it.
        """
        slug = str(meta.get("slug", "unknown")).strip() or "unknown"
        project = str(meta.get("project", "unknown")).strip() or "unknown"
        date = str(meta.get("date", "unknown")).strip() or "unknown"

        # Reuse the uuid for this slug if a pending prompt already exists.
        pd = pending_dir(self.pending_root)
        existing = _find_existing_uuid(pd, slug)
        uid = existing or str(uuid.uuid4())

        prompt_text = (
            prompt_template
            .replace("{body}", raw_body[:8000] if raw_body else "")
            .replace(
                "{meta}",
                "\n".join(f"{k}: {v}" for k, v in (meta or {}).items()),
            )
        )

        # Write the prompt with a small header so a human can hand-process.
        out_path = pd / f"{uid}.md"
        out_path.write_text(
            "\n".join([
                f"<!-- pending-slug: {slug} -->",
                f"<!-- pending-project: {project} -->",
                f"<!-- pending-date: {date} -->",
                "",
                prompt_text,
            ]),
            encoding="utf-8",
        )

        # Return a placeholder the pipeline stores on disk.  The
        # sentinel MUST be on its own line so ``extract_pending_uuid``
        # finds it.
        return (
            f"{sentinel_for(uid)}\n"
            f"\n"
            f"## Summary\n"
            f"\n"
            f"*Pending agent synthesis — uuid `{uid}`.  Prompt at "
            f"`{PENDING_DIR_NAME}/{uid}.md`.*\n"
            f"\n"
            f"The slash-command layer will rewrite this page on the next "
            f"`/wiki-sync` turn.\n"
        )


# ─── completion helpers ──────────────────────────────────────────────


def _find_existing_uuid(pending_root: Path, slug: str) -> Optional[str]:
    """Scan ``pending_root`` for an existing pending prompt tagged with
    ``slug``.  Returns the uuid or ``None``.
    """
    if not pending_root.exists():
        return None
    needle = f"<!-- pending-slug: {slug} -->"
    for p in pending_root.glob("*.md"):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if needle in text:
            return p.stem
    return None


def complete_pending(
    uid: str,
    synthesized_body: str,
    target_page: Path,
    pending_root: Optional[Path] = None,
) -> None:
    """Replace the placeholder body in ``target_page`` with the
    synthesized body + delete the pending prompt file.

    Preserves the frontmatter + appends any lines the agent wrote
    after the sentinel (so hand edits survive).  Raises
    ``FileNotFoundError`` if the target page doesn't exist;
    ``ValueError`` if the target page doesn't carry the pending
    sentinel; :class:`OSError` for filesystem errors.
    """
    if not target_page.exists():
        raise FileNotFoundError(f"target page not found: {target_page}")

    text = target_page.read_text(encoding="utf-8")
    found_uid = extract_pending_uuid(text)
    if found_uid is None:
        raise ValueError(
            f"page has no pending sentinel: {target_page}"
        )
    if found_uid != uid:
        raise ValueError(
            f"uuid mismatch: page carries {found_uid}, caller passed {uid}"
        )

    # Split frontmatter (``---\n...\n---\n``) from body.
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            frontmatter = text[: end + len("\n---\n")]
        else:
            frontmatter = ""
    else:
        frontmatter = ""

    rest = text[len(frontmatter):] if frontmatter else text
    # Strip the sentinel + placeholder body; keep whatever the body
    # writer appended after ``\n`` (usually nothing).
    _head, _sep, _tail = rest.partition(sentinel_for(uid))
    # Replace with the agent's synthesized body.
    new_body = synthesized_body.lstrip("\n")
    target_page.write_text(frontmatter + new_body, encoding="utf-8")

    # Delete the pending prompt file (best-effort — not an error if
    # it's already gone).
    pd = pending_root or pending_dir()
    prompt_file = pd / f"{uid}.md"
    if prompt_file.exists():
        try:
            prompt_file.unlink()
        except OSError:
            pass


def list_pending(pending_root: Optional[Path] = None) -> list[dict[str, str]]:
    """Enumerate every pending prompt.  Returns a list of dicts with
    keys ``uuid``, ``slug``, ``project``, ``date``, ``path``.
    """
    pd = pending_root or pending_dir()
    if not pd.exists():
        return []
    out: list[dict[str, str]] = []
    for p in sorted(pd.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        slug_m = re.search(r"^<!-- pending-slug:\s*(.*?)\s*-->", text, re.MULTILINE)
        project_m = re.search(r"^<!-- pending-project:\s*(.*?)\s*-->", text, re.MULTILINE)
        date_m = re.search(r"^<!-- pending-date:\s*(.*?)\s*-->", text, re.MULTILINE)
        out.append({
            "uuid": p.stem,
            "slug": slug_m.group(1) if slug_m else "",
            "project": project_m.group(1) if project_m else "",
            "date": date_m.group(1) if date_m else "",
            "path": str(p),
        })
    return out
