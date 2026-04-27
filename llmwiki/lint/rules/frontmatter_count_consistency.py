"""frontmatter_count_consistency — source pages: counts match the rendered body."""

from __future__ import annotations

from typing import Any

from llmwiki.lint import LintRule, register
from llmwiki.lint.rules._helpers import _TOOL_BULLET_RE, _TURN_USER_RE


@register
class FrontmatterCountConsistency(LintRule):
    """Source pages: frontmatter counts must match the rendered body.

    Catches the class of bug in `issues.md` #2 where `user_messages`,
    `turn_count`, or `tool_calls` in the frontmatter claim more activity
    than the body actually contains. This matters because the values
    surface on the site, in the JSON sibling, and in the search index —
    if they're wrong everywhere downstream is wrong.

    Only runs on ``type: source`` pages. Counts come from:
      - user_messages / turn_count → ``### Turn N — User`` headings
      - tool_calls                 → ``- `ToolName`:`` bullet lines
    """

    name = "frontmatter_count_consistency"
    severity = "warning"

    def run(self, pages, *, llm_callback=None):
        issues: list[dict[str, Any]] = []
        for rel, page in pages.items():
            meta = page["meta"]
            if meta.get("type") != "source":
                continue
            body = page.get("body", "")
            actual_turns = len(_TURN_USER_RE.findall(body))
            actual_tool_calls = len(_TOOL_BULLET_RE.findall(body))

            for field, actual in (
                ("user_messages", actual_turns),
                ("turn_count", actual_turns),
                ("tool_calls", actual_tool_calls),
            ):
                claimed_raw = meta.get(field)
                if claimed_raw in (None, ""):
                    continue
                try:
                    claimed = int(claimed_raw)
                except (TypeError, ValueError):
                    continue
                if claimed != actual:
                    issues.append({
                        "rule": self.name,
                        "severity": self.severity,
                        "page": rel,
                        "message": (
                            f"frontmatter {field}={claimed} but body has "
                            f"{actual}"
                        ),
                    })
        return issues
