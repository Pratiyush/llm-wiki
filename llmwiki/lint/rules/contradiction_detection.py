"""contradiction_detection — flag pages with explicit ## Contradictions sections."""

from __future__ import annotations

import re

from llmwiki.lint import LintRule, register


@register
class ContradictionDetection(LintRule):
    """Detect semantic contradictions across pages (LLM-powered)."""

    name = "contradiction_detection"
    severity = "warning"
    requires_llm = True

    def run(self, pages, *, llm_callback=None):
        if llm_callback is None:
            return [{
                "rule": self.name,
                "severity": "info",
                "page": "",
                "message": "skipped: requires LLM callback",
            }]
        # Note: full implementation wires up a real LLM. For v1.0, this
        # is a simple structural detector for explicit `## Contradictions`
        # sections (pages flagging their own contradictions).
        issues = []
        for rel, page in pages.items():
            if "## Contradictions" in page["body"]:
                # Extract the section
                section_match = re.search(
                    r"## Contradictions\n(.*?)(?:\n## |\Z)",
                    page["body"],
                    re.DOTALL,
                )
                if section_match and section_match.group(1).strip():
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel,
                        "message": "page has ## Contradictions section — review required",
                    })
        return issues
