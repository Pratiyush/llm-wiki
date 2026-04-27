"""stale_reference_detection — dated claims about a target older than the target (G-17)."""

from __future__ import annotations

from llmwiki.lint import LintRule, register


@register
class StaleReferenceDetection(LintRule):
    """Dated claims about a target older than the target (G-17 · #303).

    A page with ``last_updated: 2026-01-01`` links to ``[[RAG]]`` and
    says ``"RAG is <100ms as of 2026-01-01"``. The ``RAG`` page is
    later updated to ``2026-04-19`` — the old 100ms claim is probably
    no longer true, but the linter couldn't tell before.

    This rule flags the pair. Pairs naturally with the ``llmwiki
    references`` CLI (``llmwiki references RAG`` enumerates every page
    that still cites it).
    """

    name = "stale_reference_detection"
    severity = "warning"

    def run(self, pages, *, llm_callback=None):
        from llmwiki.references import find_stale_references
        issues = []
        for stale in find_stale_references(pages):
            excerpt = stale.dated_claim
            if len(excerpt) > 80:
                excerpt = excerpt[:77] + "..."
            issues.append({
                "rule": self.name,
                "severity": "warning",
                "page": stale.source,
                "message": (
                    f"dated claim about [[{stale.target}]] "
                    f"(target updated {stale.target_last_updated}, "
                    f"this page updated {stale.source_last_updated}): {excerpt!r}"
                ),
            })
        return issues
