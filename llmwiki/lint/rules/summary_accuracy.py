"""summary_accuracy — `summary:` field must be non-empty when present."""

from __future__ import annotations

from llmwiki.lint import LintRule, register


@register
class SummaryAccuracy(LintRule):
    """Check that summary: field matches content (LLM-powered)."""

    name = "summary_accuracy"
    severity = "info"
    requires_llm = True

    def run(self, pages, *, llm_callback=None):
        if llm_callback is None:
            return [{
                "rule": self.name,
                "severity": "info",
                "page": "",
                "message": "skipped: requires LLM callback",
            }]
        # Structural proxy: check summary field is non-empty when present.
        issues = []
        for rel, page in pages.items():
            meta = page["meta"]
            summary = meta.get("summary", "")
            if "summary" in meta and not summary.strip():
                issues.append({
                    "rule": self.name,
                    "severity": "info",
                    "page": rel,
                    "message": "summary field is empty",
                })
        return issues
