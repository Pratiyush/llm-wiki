"""link_integrity — [[wikilinks]] must resolve to existing pages."""

from __future__ import annotations

from llmwiki.lint import LintRule, WIKILINK_RE, register
from llmwiki.lint.rules._helpers import _page_slug


@register
class LinkIntegrity(LintRule):
    """[[wikilinks]] must resolve to existing pages."""

    name = "link_integrity"
    severity = "warning"
    auto_fixable = True

    def run(self, pages, *, llm_callback=None):
        # Build set of known page slugs
        slugs = {_page_slug(rel) for rel in pages}
        issues = []
        for rel, page in pages.items():
            for target in set(WIKILINK_RE.findall(page["body"])):
                # Strip any embedded section anchors
                t = target.split("#")[0].strip()
                if not t:
                    continue
                if t not in slugs:
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel,
                        "message": f"broken wikilink [[{target}]]",
                    })
        return issues
