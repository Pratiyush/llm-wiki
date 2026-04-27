"""tools_consistency — source pages: tools_used and tool_counts.keys() must agree."""

from __future__ import annotations

from typing import Any

from llmwiki.lint import LintRule, register
from llmwiki.lint.rules._helpers import (
    _normalise_tool_counts_keys,
    _normalise_tools_used,
)


@register
class ToolsConsistency(LintRule):
    """Source pages: ``tools_used`` and ``tool_counts.keys()`` must agree.

    Catches the class of bug in `issues.md` #4 where a page lists a tool
    in the ``tools_used`` frontmatter array but the corresponding
    ``tool_counts`` object is missing that tool's entry (or vice-versa).
    Both surface on the session page, so divergence silently misleads
    anyone looking at the stats.
    """

    name = "tools_consistency"
    severity = "warning"

    def run(self, pages, *, llm_callback=None):
        issues: list[dict[str, Any]] = []
        for rel, page in pages.items():
            meta = page["meta"]
            if meta.get("type") != "source":
                continue
            # #410: tools_used can be list (post-parser), str (legacy),
            # or None — _normalise handles all three without a
            # TypeError on `re.search(regex, list)`.
            tools_used = _normalise_tools_used(meta.get("tools_used"))
            tool_counts_keys = _normalise_tool_counts_keys(meta.get("tool_counts"))
            if not tools_used or not tool_counts_keys:
                # One side missing — that's a different lint concern, skip.
                continue

            only_used = tools_used - tool_counts_keys
            only_counted = tool_counts_keys - tools_used
            if only_used:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": rel,
                    "message": (
                        f"tools_used has {sorted(only_used)} but tool_counts "
                        f"has no key for them"
                    ),
                })
            if only_counted:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": rel,
                    "message": (
                        f"tool_counts has keys {sorted(only_counted)} but "
                        f"tools_used does not list them"
                    ),
                })
        return issues
