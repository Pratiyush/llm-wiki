"""Synthesizer backends — ABC + built-in implementations (v0.5 · #36).

The `BaseSynthesizer` defines the contract: given a raw session markdown
body + its frontmatter, produce a wiki source-page body (the part under
the frontmatter). The concrete backend handles the actual LLM call.

Built-in backends:
- `DummySynthesizer` — returns a canned response. Used for testing and
  for the `--dry-run` path so users can preview what would be generated.
- (Future) `OllamaSynthesizer` — calls a local Ollama instance (#35)
- (Future) `ClaudeAPISynthesizer` — calls the Anthropic API
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseSynthesizer(ABC):
    """Interface for LLM-backed wiki-page synthesizers."""

    @abstractmethod
    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        """Given a raw session body + frontmatter, return a wiki
        source-page body (markdown). The caller handles frontmatter
        generation and file writing — the backend only generates the
        prose content (Summary, Key Claims, Key Quotes, Connections).

        `prompt_template` is the contents of `prompts/source_page.md`
        with `{body}` and `{meta}` placeholders.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend is ready to use (e.g. the API
        key is set, or the Ollama server is running)."""
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class DummySynthesizer(BaseSynthesizer):
    """Test/preview backend — returns a canned wiki page without
    calling any LLM. Useful for `--dry-run` and unit tests.

    G-12 (#298): the dummy output used to copy every ``[[wikilink]]``
    mention straight out of the raw body into ``## Connections``.  That
    fabricated 371 dangling links on the compiled demo site because
    those targets almost never existed as wiki pages.  The dummy now
    emits only a single **real** connection — the project entity page,
    which the ingest workflow guarantees exists — and surfaces raw
    mentions as plain text in ``## Raw Mentions`` so the information
    isn't lost but ``check-links`` doesn't cry wolf.
    """

    def _title_case_project(self, project: str) -> str:
        """``ai-newsletter`` → ``AiNewsletter`` (matches entity filenames)."""
        return "".join(part.capitalize() for part in re.split(r"[-_\s]+", project) if part)

    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        slug = meta.get("slug", "unknown")
        project = meta.get("project", "unknown")
        date = meta.get("date", "unknown")

        # Extract a naive summary from the first 500 chars
        first_para = raw_body.strip().split("\n\n")[0][:500] if raw_body else ""

        # Plain-text mentions — kept for human readers, but NOT emitted as
        # [[wikilinks]] so check-links stays clean on auto-synthesized pages.
        mentions = sorted(set(re.findall(r"\[\[([^\]]+)\]\]", raw_body)))
        raw_mentions_block = (
            "\n".join(f"- {m}" for m in mentions[:10])
            if mentions
            else "*(no mentions detected)*"
        )

        project_entity = self._title_case_project(project) if project and project != "unknown" else ""
        if project_entity:
            connections_block = f"- [[{project_entity}]] — parent project"
        else:
            connections_block = "*(connections auto-extracted by a real synthesizer will appear here)*"

        return f"""## Summary

Auto-synthesized from session `{slug}` on {date} (project: {project}).

{first_para}

## Key Claims

- Session covered project `{project}`
- Model: {meta.get('model', 'unknown')}
- {meta.get('user_messages', '?')} user messages, {meta.get('tool_calls', '?')} tool calls

## Key Quotes

> (Auto-synthesis — replace with actual quotes from the session)

## Connections

{connections_block}

## Raw Mentions

{raw_mentions_block}
"""

    def is_available(self) -> bool:
        return True  # Always available — no external deps
