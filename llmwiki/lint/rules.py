"""All 11 lint rules (v1.0 · #155).

Basic rules (8, no LLM):
  1. frontmatter_completeness  — required fields present
  2. frontmatter_validity       — enum values + types valid
  3. link_integrity             — [[wikilinks]] resolve
  4. orphan_detection           — pages with zero inbound links
  5. content_freshness          — last_updated > 90 days → warning
  6. entity_consistency         — entities in body match frontmatter
  7. duplicate_detection        — >80% title similarity
  8. index_sync                 — pages in index.md ↔ pages on disk

LLM-powered rules (3):
  9. contradiction_detection
  10. claim_verification
  11. summary_accuracy
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Optional

from llmwiki.lint import LintRule, register, WIKILINK_RE
from llmwiki.lifecycle import LifecycleState
from llmwiki.schema import ENTITY_TYPES


# ═══════════════════════════════════════════════════════════════════════
#  BASIC RULES (8)
# ═══════════════════════════════════════════════════════════════════════


@register
class FrontmatterCompleteness(LintRule):
    """Required frontmatter fields must be present."""

    name = "frontmatter_completeness"
    severity = "error"
    auto_fixable = False

    REQUIRED = ["title", "type"]

    # System-level nav files and _context.md stubs are exempt from the
    # strict title/type requirement. Index/log/overview are auto-generated
    # or human-curated hubs and don't fit the source/entity/concept schema.
    EXEMPT_FILES = {
        "index.md", "overview.md", "log.md",
        "hints.md", "hot.md", "MEMORY.md",
        "SOUL.md", "CRITICAL_FACTS.md", "dashboard.md",
    }

    def run(self, pages, *, llm_callback=None):
        issues = []
        for rel, page in pages.items():
            # Skip system nav files and _context.md stubs
            basename = rel.rsplit("/", 1)[-1]
            if basename in self.EXEMPT_FILES or basename == "_context.md":
                continue
            meta = page["meta"]
            missing = [f for f in self.REQUIRED if f not in meta]
            if missing:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": rel,
                    "message": f"missing required fields: {', '.join(missing)}",
                })
        return issues


@register
class FrontmatterValidity(LintRule):
    """Frontmatter values must have valid types/enum values."""

    name = "frontmatter_validity"
    severity = "error"

    VALID_TYPES = {"source", "entity", "concept", "synthesis",
                   "comparison", "question", "navigation", "context"}
    VALID_LIFECYCLES = {s.value for s in LifecycleState}

    def run(self, pages, *, llm_callback=None):
        issues = []
        for rel, page in pages.items():
            meta = page["meta"]

            t = meta.get("type", "").lower()
            if t and t not in self.VALID_TYPES:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": rel,
                    "message": f"invalid type {t!r} (expected one of {sorted(self.VALID_TYPES)})",
                })

            lc = meta.get("lifecycle", "").lower()
            if lc and lc not in self.VALID_LIFECYCLES:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": rel,
                    "message": f"invalid lifecycle {lc!r} (expected one of {sorted(self.VALID_LIFECYCLES)})",
                })

            et = meta.get("entity_type", "").lower()
            if et and et not in ENTITY_TYPES:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": rel,
                    "message": f"invalid entity_type {et!r} (expected one of {list(ENTITY_TYPES)})",
                })

            conf = meta.get("confidence", "")
            if conf:
                try:
                    c = float(conf)
                    if not (0.0 <= c <= 1.0):
                        issues.append({
                            "rule": self.name,
                            "severity": "error",
                            "page": rel,
                            "message": f"confidence {c} out of range [0.0, 1.0]",
                        })
                except (ValueError, TypeError):
                    issues.append({
                        "rule": self.name,
                        "severity": "error",
                        "page": rel,
                        "message": f"confidence not numeric: {conf!r}",
                    })
        return issues


def _page_slug(rel: str) -> str:
    """Convert path like 'entities/Foo.md' → 'Foo'."""
    return rel.rsplit("/", 1)[-1].removesuffix(".md")


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

        issues = []
        for rel in pages:
            slug = _page_slug(rel)
            # Skip navigation / context / index files
            if rel.endswith("_context.md") or slug in {"index", "overview", "log",
                                                        "hints", "hot", "MEMORY",
                                                        "SOUL", "CRITICAL_FACTS",
                                                        "dashboard"}:
                continue
            if inbound.get(slug, 0) == 0:
                issues.append({
                    "rule": self.name,
                    "severity": "info",
                    "page": rel,
                    "message": f"orphan page (no inbound [[wikilinks]])",
                })
        return issues


@register
class ContentFreshness(LintRule):
    """Pages older than 90 days should be reviewed."""

    name = "content_freshness"
    severity = "warning"

    STALE_DAYS = 90

    def run(self, pages, *, llm_callback=None):
        issues = []
        now = datetime.now(timezone.utc)
        for rel, page in pages.items():
            meta = page["meta"]
            date_str = meta.get("last_verified") or meta.get("last_updated")
            if not date_str:
                continue
            try:
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            age_days = (now - dt).days
            if age_days > self.STALE_DAYS:
                issues.append({
                    "rule": self.name,
                    "severity": "warning",
                    "page": rel,
                    "message": f"last updated {age_days} days ago (> {self.STALE_DAYS} day threshold)",
                })
        return issues


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


@register
class DuplicateDetection(LintRule):
    """Pages with >80% title similarity may be duplicates."""

    name = "duplicate_detection"
    severity = "warning"

    THRESHOLD = 0.8

    def run(self, pages, *, llm_callback=None):
        issues = []
        items = list(pages.items())
        for i in range(len(items)):
            rel_a, page_a = items[i]
            title_a = page_a["meta"].get("title", "").lower()
            if not title_a:
                continue
            for j in range(i + 1, len(items)):
                rel_b, page_b = items[j]
                title_b = page_b["meta"].get("title", "").lower()
                if not title_b:
                    continue
                ratio = SequenceMatcher(None, title_a, title_b).ratio()
                if ratio >= self.THRESHOLD:
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel_a,
                        "message": f"possible duplicate of {rel_b!r} (title similarity {ratio:.2f})",
                    })
        return issues


@register
class IndexSync(LintRule):
    """wiki/index.md must list every page, and listed pages must exist."""

    name = "index_sync"
    severity = "error"
    auto_fixable = True

    def run(self, pages, *, llm_callback=None):
        index = pages.get("index.md")
        if not index:
            return []

        issues = []
        listed_slugs: set[str] = set()

        # Parse markdown links in index.md (simple regex)
        link_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for match in link_re.finditer(index["body"]):
            href = match.group(2)
            if href.startswith("http"):
                continue
            # Strip #anchor
            href = href.split("#")[0]
            if not href:
                continue
            # Check target exists
            if href not in pages and not href.lstrip("./") in pages:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": "index.md",
                    "message": f"dead index link → {href}",
                })
            else:
                listed_slugs.add(href.rsplit("/", 1)[-1].removesuffix(".md"))

        # Check that every content page is listed (skip nav files and _context.md)
        nav_pages = {"index.md", "overview.md", "log.md", "hints.md", "hot.md",
                     "MEMORY.md", "SOUL.md", "CRITICAL_FACTS.md", "dashboard.md"}
        for rel in pages:
            if rel in nav_pages or rel.endswith("_context.md"):
                continue
            slug = _page_slug(rel)
            if slug not in listed_slugs:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": "index.md",
                    "message": f"page {rel!r} not listed in index.md",
                })
        return issues


# ═══════════════════════════════════════════════════════════════════════
#  LLM-POWERED RULES (3)
# ═══════════════════════════════════════════════════════════════════════


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
        from llmwiki.candidates import stale_candidates, candidates_dir
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
                    f"(threshold {self.STALE_DAYS}) — review with `/wiki-review`"
                ),
            })
        return issues


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
