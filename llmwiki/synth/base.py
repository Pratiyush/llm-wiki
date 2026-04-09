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
    calling any LLM. Useful for `--dry-run` and unit tests."""

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

        # Extract wikilink-like mentions from the body
        mentions = sorted(set(re.findall(r"\[\[([^\]]+)\]\]", raw_body)))
        connections = "\n".join(
            f"- [[{m}]]" for m in mentions[:10]
        ) if mentions else "- (no connections detected)"

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

{connections}
"""

    def is_available(self) -> bool:
        return True  # Always available — no external deps
