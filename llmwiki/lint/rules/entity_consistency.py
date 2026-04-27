"""entity_consistency — entity pages should declare entity_type in frontmatter."""

from __future__ import annotations

from llmwiki.lint import LintRule, register


@register
class EntityConsistency(LintRule):
    """Entities mentioned in body should appear in frontmatter (for entity pages)."""

    name = "entity_consistency"
    severity = "warning"

    def run(self, pages, *, llm_callback=None):
        issues = []
        for rel, page in pages.items():
            meta = page["meta"]
            if meta.get("type") != "entity":
                continue
            # Check that `entity_type` field is present on entity pages
            if "entity_type" not in meta:
                issues.append({
                    "rule": self.name,
                    "severity": "warning",
                    "page": rel,
                    "message": "entity page missing `entity_type` field in frontmatter",
                })
        return issues
