"""claim_verification — entity/concept pages with claims should cite sources."""

from __future__ import annotations

import re

from llmwiki.lint import LintRule, register


@register
class ClaimVerification(LintRule):
    """Verify claims are supported by cited sources (LLM-powered)."""

    name = "claim_verification"
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
        # Structural proxy: check that entity/concept pages with claims
        # (## Key Facts or ## Key Claims sections) also cite sources.
        issues = []
        for rel, page in pages.items():
            meta = page["meta"]
            if meta.get("type") not in ("entity", "concept"):
                continue
            has_claims = bool(re.search(r"## Key (Facts|Claims)", page["body"]))
            has_sources = bool(meta.get("sources")) or \
                "## Sessions" in page["body"] or \
                "## Sources" in page["body"]
            if has_claims and not has_sources:
                issues.append({
                    "rule": self.name,
                    "severity": "info",
                    "page": rel,
                    "message": "page makes claims but cites no sources",
                })
        return issues
