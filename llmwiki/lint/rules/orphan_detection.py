"""orphan_detection — pages with zero inbound [[wikilinks]] are orphans."""

from __future__ import annotations

from llmwiki.lint import LintRule, WIKILINK_RE, register
from llmwiki.lint.rules._helpers import _page_slug


@register
class OrphanDetection(LintRule):
    """Pages with zero inbound [[wikilinks]] are orphans."""

    name = "orphan_detection"
    severity = "info"

    def run(self, pages, *, llm_callback=None):
        # Collect all outbound links from every page
        inbound: dict[str, int] = {}
        for rel, page in pages.items():
            for target in set(WIKILINK_RE.findall(page["body"])):
                t = target.split("#")[0].strip()
                inbound[t] = inbound.get(t, 0) + 1

        # #py-l5 (#603): pull the skip list from the canonical
        # SYSTEM_PAGE_SLUGS so dashboard.md can't get lint-flagged as
        # an orphan in one rule while exempt in another (it WAS being
        # flagged here even though MetadataValidator's EXEMPT_FILES
        # already exempted it from the strict title/type check).
        from llmwiki._system_pages import SYSTEM_PAGE_SLUGS
        issues = []
        for rel in pages:
            slug = _page_slug(rel)
            # Skip navigation / context / index files (canonical list).
            if rel.endswith("_context.md") or slug in SYSTEM_PAGE_SLUGS:
                continue
            if inbound.get(slug, 0) == 0:
                issues.append({
                    "rule": self.name,
                    "severity": "info",
                    "page": rel,
                    "message": "orphan page (no inbound [[wikilinks]])",
                })
        return issues
