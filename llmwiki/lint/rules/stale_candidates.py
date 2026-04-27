"""stale_candidates — flag candidate pages older than N days (#51)."""

from __future__ import annotations

from pathlib import Path

from llmwiki.lint import LintRule, register


@register
class StaleCandidates(LintRule):
    """Flag candidate pages older than N days (#51).

    Candidates are new entity/concept pages waiting for human approval.
    Anything sitting in wiki/candidates/ for > 30 days likely indicates
    the reviewer forgot about it. Reports as info severity (not blocking).
    """

    name = "stale_candidates"
    severity = "info"
    STALE_DAYS = 30

    def run(self, pages, *, llm_callback=None):
        from llmwiki.candidates import candidates_dir, stale_candidates
        # load_pages gives us the real wiki dir from page[path]
        issues = []
        if not pages:
            return issues
        # Infer wiki_dir from first page path
        sample_page = next(iter(pages.values()))
        page_path = sample_page.get("path")
        if not isinstance(page_path, Path):
            return issues
        # Walk up to find wiki/ root
        wiki_dir = page_path.parent
        for _ in range(6):
            if wiki_dir.name == "wiki":
                break
            if wiki_dir == wiki_dir.parent:
                return issues
            wiki_dir = wiki_dir.parent
        if not candidates_dir(wiki_dir).is_dir():
            return issues
        for cand in stale_candidates(wiki_dir, threshold_days=self.STALE_DAYS):
            issues.append({
                "rule": self.name,
                "severity": "info",
                "page": cand["rel_path"],
                "message": (
                    f"candidate '{cand['slug']}' is {cand['age_days']} days old "
                    f"(threshold {self.STALE_DAYS}) — review with `/wiki-candidates`"
                ),
            })
        return issues


# CacheTierConsistency rule removed — cache_tiers module deleted in
# simplification epic (#359). The rule depended on llmwiki.cache_tiers
# which no longer exists.
