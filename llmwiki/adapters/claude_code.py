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

    def is_subagent(self, jsonl_path: Path) -> bool:
        """Detect Claude Code sub-agent runs by canonical path layout (#406).

        Claude Code stores sub-agent runs at:
            ~/.claude/projects/<project>/<session-uuid>/subagents/agent-*.jsonl

        Old heuristic was a substring check on ``"subagent" in path.parts``,
        which mis-tagged any user project named e.g. ``subagent-runner`` —
        every session in such a project was demoted to sub-agent on the
        project page and excluded from session counts.

        New rule: the file MUST live in a directory literally named
        ``subagents`` (plural) AND have a filename starting with
        ``agent-``. Both conditions match the canonical Claude layout
        and exclude every false-positive case (project name "subagent",
        "subagent-runner", "agent-subagent-helper", etc.).
        """
        parts = jsonl_path.parts
        if "subagents" not in parts:
            return False
        # The 'subagents' segment must be the immediate parent directory.
        try:
            parent_idx = parts.index("subagents")
        except ValueError:
            return False
        if parent_idx >= len(parts) - 1:
            return False
        # And the filename must start with 'agent-' (the canonical pattern).
        return parts[-1].startswith("agent-")
