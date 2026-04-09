"""Claude Code session-store adapter.

Claude Code writes one .jsonl per session under:
    ~/.claude/projects/<project-dir-slug>/<session-uuid>.jsonl

Sub-agent runs live in:
    ~/.claude/projects/<project-dir-slug>/<session-uuid>/subagents/agent-*.jsonl

Project directory names encode the full absolute path with slashes replaced by
dashes, e.g. '-Users-USER-Desktop-2026-production-draft-ai-newsletter'.
We strip the common prefix to produce a friendly slug.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("claude_code")
class ClaudeCodeAdapter(BaseAdapter):
    """Claude Code — reads ~/.claude/projects/*/*.jsonl"""

    # Cross-platform: dot-dir works on macOS, Linux, and Windows
    session_store_path = Path.home() / ".claude" / "projects"

    def derive_project_slug(self, jsonl_path: Path) -> str:
        """Strip the '-Users-...-production-draft-' prefix from the project dir name."""
        store = Path(self.session_store_path).expanduser()
        try:
            rel = jsonl_path.relative_to(store)
        except ValueError:
            return jsonl_path.parent.name
        if not rel.parts:
            return jsonl_path.parent.name
        project_dir = rel.parts[0]
        parts = project_dir.lstrip("-").split("-")
        # Find a recognizable split point — anything after 'draft', 'production', or 'Desktop'
        for marker in ("draft", "production", "Desktop"):
            if marker in parts:
                idx = len(parts) - 1 - parts[::-1].index(marker)
                tail = parts[idx + 1 :]
                if tail:
                    return "-".join(tail)
        return "-".join(parts[-2:]) if len(parts) >= 2 else project_dir
