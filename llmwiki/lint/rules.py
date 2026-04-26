"""All registered lint rules (v1.0 · #155).

Basic rules (8, no LLM):
  1. frontmatter_completeness  — required fields present
  2. frontmatter_validity       — enum values + types valid
  3. link_integrity             — [[wikilinks]] resolve
  4. orphan_detection           — pages with zero inbound links
  5. content_freshness          — last_updated > 90 days → warning
  6. entity_consistency         — entities in body match frontmatter
  7. duplicate_detection        — same-project + title + body similarity
  8. index_sync                 — pages in index.md ↔ pages on disk

LLM-powered rules (3):
  9. contradiction_detection
  10. claim_verification
  11. summary_accuracy

Post-v1.0 rules:
  12. stale_candidates            (v1.1 · #51)
  13. cache_tier_consistency      (v1.2 · #52)
  14. tags_topics_convention      (G-16 · #302)
  15. stale_reference_detection   (G-17 · #303)
  16. frontmatter_count_consistency  (v1.2 · issues.md #2)
  17. tools_consistency              (v1.2 · issues.md #4)

The live rule count lives in ``llmwiki.lint.REGISTRY`` — prefer
``len(REGISTRY)`` over hard-coded numbers in docs + help strings.
"""

from __future__ import annotations

import hashlib
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
    """Pages with near-identical titles **and** bodies may be duplicates.

    G-11 (#297): on a 714-page corpus the old rule emitted 76,963 pair
    warnings — roughly a third of all pairs — because two pages named
    ``CHANGELOG.md`` in different projects always scored title
    similarity 1.0.  The rule is now scoped by ``project`` and demands
    **both** a high title match (≥0.95) **and** a body overlap
    (SequenceMatcher on the first 4 KB ≥0.80) before flagging.  Non-
    source pages (entities, concepts, syntheses) still cross-compare as
    before, since sharing the same project doesn't apply there.
    """

    name = "duplicate_detection"
    severity = "warning"

    # Titles must be near-identical (not just >80% — "CLAUDE.md" vs
    # "CHANGELOG.md" was tripping the old 0.8 threshold).
    TITLE_THRESHOLD = 0.95
    # Bodies must also overlap — cheap hedge against same-titled
    # boilerplate files that are otherwise unrelated.
    BODY_THRESHOLD = 0.80
    BODY_SAMPLE_BYTES = 4096

    def _bucket_key(self, page: dict) -> tuple[str, str]:
        """Return the comparison-bucket key for a page.

        Source pages compare only within the same project; everything
        else compares within type. Pages from different buckets never
        get compared, which collapses the cross-bucket O(n²) behaviour.
        """
        t = str(page["meta"].get("type") or "")
        if t == "source":
            return (t, str(page["meta"].get("project") or ""))
        return (t, "")

    @staticmethod
    def _body_fingerprint(body: str, sample_bytes: int) -> str:
        """Cheap whitespace-normalised md5 of the first ``sample_bytes``.

        Two pages with identical fingerprints are likely duplicates;
        only those pairs justify the expensive ``SequenceMatcher`` call.
        Whitespace normalisation makes the fingerprint stable across
        CRLF/LF and accidental indentation drift, so duplicate detection
        survives format-only edits.
        """
        if not body:
            return ""
        sample = body[:sample_bytes]
        normalised = " ".join(sample.split())
        return hashlib.md5(normalised.encode("utf-8")).hexdigest()

    def run(self, pages, *, llm_callback=None):
        # #412 perf fix: bucket first, fingerprint second, SequenceMatcher
        # only on collisions. The old code did n² SequenceMatcher calls
        # over the full corpus — on a 500-page wiki it was the slowest
        # lint rule by an order of magnitude.
        issues: list[dict] = []
        buckets: dict[tuple[str, str], list[tuple[str, dict, str, str]]] = {}
        for rel, page in pages.items():
            title = (page["meta"].get("title") or "").lower()
            if not title:
                continue
            body = (page.get("body") or "")
            fp = self._body_fingerprint(body, self.BODY_SAMPLE_BYTES)
            buckets.setdefault(self._bucket_key(page), []).append(
                (rel, page, title, fp)
            )

        for items in buckets.values():
            if len(items) < 2:
                continue
            # Pages with identical fingerprints are near-certain
            # duplicates — flag without re-comparing bodies.
            by_fp: dict[str, list[int]] = {}
            for idx, (_, _, _, fp) in enumerate(items):
                if fp:
                    by_fp.setdefault(fp, []).append(idx)

            flagged_pairs: set[tuple[int, int]] = set()
            for fp, idxs in by_fp.items():
                if len(idxs) < 2:
                    continue
                for i_pos in range(len(idxs)):
                    for j_pos in range(i_pos + 1, len(idxs)):
                        i, j = idxs[i_pos], idxs[j_pos]
                        rel_a, _, title_a, _ = items[i]
                        rel_b, _, title_b, _ = items[j]
                        title_ratio = SequenceMatcher(
                            None, title_a, title_b
                        ).ratio()
                        if title_ratio < self.TITLE_THRESHOLD:
                            continue
                        flagged_pairs.add((i, j))
                        issues.append({
                            "rule": self.name,
                            "severity": "warning",
                            "page": rel_a,
                            "message": (
                                f"possible duplicate of {rel_b!r} "
                                f"(title {title_ratio:.2f}, body 1.00)"
                            ),
                        })

            # Fingerprints differed — fall back to SequenceMatcher only
            # for pairs whose titles already match. Body comparisons
            # over the bucket-restricted slice cap the cost.
            for i in range(len(items)):
                rel_a, _, title_a, fp_a = items[i]
                body_a = (items[i][1].get("body") or "")[: self.BODY_SAMPLE_BYTES]
                if not body_a:
                    continue
                for j in range(i + 1, len(items)):
                    if (i, j) in flagged_pairs:
                        continue
                    rel_b, _, title_b, fp_b = items[j]
                    if fp_a and fp_b and fp_a == fp_b:
                        continue  # already handled above
                    title_ratio = SequenceMatcher(
                        None, title_a, title_b
                    ).ratio()
                    if title_ratio < self.TITLE_THRESHOLD:
                        continue
                    body_b = (items[j][1].get("body") or "")[: self.BODY_SAMPLE_BYTES]
                    if not body_b:
                        continue
                    body_ratio = SequenceMatcher(None, body_a, body_b).ratio()
                    if body_ratio < self.BODY_THRESHOLD:
                        continue
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel_a,
                        "message": (
                            f"possible duplicate of {rel_b!r} "
                            f"(title {title_ratio:.2f}, body {body_ratio:.2f})"
                        ),
                    })
        return issues


def _resolve_index_href(href: str) -> str:
    """Normalise an index.md markdown link href to a repo-relative path.

    Strips ``#anchor`` and ``?query`` fragments, drops the leading
    ``./`` prefix, and collapses ``..`` segments using ``PurePosixPath``
    (POSIX-only — every wiki path is forward-slash). Returns ``""``
    when the href is empty or escapes the wiki root.

    Closes #411 — the previous one-liner ``href.lstrip("./")`` only
    handled bare ``./`` and false-positive'd on ``../path``,
    ``path#anchor``, and ``path?query``.
    """
    from pathlib import PurePosixPath

    href = href.split("#", 1)[0].split("?", 1)[0].strip()
    if not href:
        return ""
    # PurePosixPath collapses `.` segments but preserves `..`. We need
    # to evaluate the result against the wiki root explicitly, and
    # reject any href that escapes the root (negative steps go to "..").
    parts: list[str] = []
    for seg in PurePosixPath(href).parts:
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                # href escapes the wiki root — treat as unresolvable.
                return ""
            parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


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

        # #411: index.md lives at the wiki root, so the resolver works
        # against PurePosixPath("") as the base. We collapse `..`,
        # drop `#anchor` and `?query`, and look the resulting
        # repo-relative path up in `pages`. The old `href.lstrip("./")`
        # only handled bare `./` and false-positive'd on every other
        # form (`../`, `#anchor`, `?query`).
        # Parse markdown links in index.md (simple regex)
        link_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for match in link_re.finditer(index["body"]):
            href = match.group(2)
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = _resolve_index_href(href)
            if not resolved:
                continue
            if resolved in pages:
                listed_slugs.add(resolved.rsplit("/", 1)[-1].removesuffix(".md"))
            else:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": "index.md",
                    "message": f"dead index link → {href}",
                })

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
        from pathlib import Path
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
                    f"(threshold {self.STALE_DAYS}) — review with `/wiki-candidates`"
                ),
            })
        return issues


# CacheTierConsistency rule removed — cache_tiers module deleted in
# simplification epic (#359). The rule depended on llmwiki.cache_tiers
# which no longer exists.


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


@register
class TagsTopicsConvention(LintRule):
    """Projects use `topics:`, everything else uses `tags:` (G-16 · #302).

    `wiki/projects/<slug>.md` carries curated stack labels
    (React, ML, Java) under ``topics:``.
    `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/syntheses/`
    carry freeform per-page labels under ``tags:``.  Mixing the two
    breaks filtering in the site UI and makes the graph viewer's chip
    rendering inconsistent — this rule flags the mismatch.
    """

    name = "tags_topics_convention"
    severity = "warning"

    _PROJECT_PREFIX = "projects/"
    _TAG_PREFIXES = (
        "sources/", "entities/", "concepts/", "syntheses/",
    )

    def run(self, pages, *, llm_callback=None):
        issues = []
        for rel, page in pages.items():
            rel_posix = rel.replace("\\", "/")
            meta = page["meta"]
            has_tags = "tags" in meta
            has_topics = "topics" in meta
            if rel_posix.startswith(self._PROJECT_PREFIX):
                if has_tags and not has_topics:
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel,
                        "message": (
                            "project pages should use `topics:` not `tags:` — "
                            "run `llmwiki tag rename <value> <value>` to fix "
                            "or set topics: directly"
                        ),
                    })
            elif any(rel_posix.startswith(p) for p in self._TAG_PREFIXES):
                if has_topics and not has_tags:
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel,
                        "message": (
                            f"{rel_posix.split('/')[0]} pages should use `tags:` "
                            "not `topics:`"
                        ),
                    })
        return issues


@register
class StaleReferenceDetection(LintRule):
    """Dated claims about a target older than the target (G-17 · #303).

    A page with ``last_updated: 2026-01-01`` links to ``[[RAG]]`` and
    says ``"RAG is <100ms as of 2026-01-01"``.  The ``RAG`` page is
    later updated to ``2026-04-19`` — the old 100ms claim is probably
    no longer true, but the linter couldn't tell before.

    This rule flags the pair.  Pairs naturally with the ``llmwiki
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


# ═══════════════════════════════════════════════════════════════════════
#  RULE 16 — frontmatter_count_consistency  (issues.md #2)
# ═══════════════════════════════════════════════════════════════════════


_TURN_USER_RE = re.compile(r"^### Turn \d+ — User\s*$", re.MULTILINE)
_TOOL_BULLET_RE = re.compile(
    r"^- `(Read|Write|Edit|Bash|Glob|Grep|Task|WebFetch|WebSearch|TodoWrite)`:",
    re.MULTILINE,
)


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


# ═══════════════════════════════════════════════════════════════════════
#  RULE 17 — tools_consistency  (issues.md #4)
# ═══════════════════════════════════════════════════════════════════════


_TOOLS_USED_RE = re.compile(r"\[([^\]]*)\]")
_TOOL_COUNTS_KEYS_RE = re.compile(r'"([A-Za-z_]+)"\s*:')


def _normalise_tools_used(value: Any) -> set[str]:
    """Coerce a frontmatter ``tools_used`` value into a set of tool names.

    Frontmatter parsers return either a Python ``list`` (when the value
    is parsed as ``[a, b]``) or a raw ``str`` (legacy paths or
    string-typed coercion). Older code did
    ``re.search(_TOOLS_USED_RE, value)`` directly — which raises
    ``TypeError`` on a list and silently aborted the whole lint rule
    (#410). This helper normalises both shapes plus the other types
    that have appeared in real frontmatter (number, bool, dict, None).
    Anything that isn't sensibly stringifiable returns an empty set.
    """
    if value is None or value == "":
        return set()
    if isinstance(value, list):
        return {str(x).strip().strip('"\'') for x in value if str(x).strip()}
    if isinstance(value, str):
        m = _TOOLS_USED_RE.search(value)
        if not m:
            return set()
        return {
            t.strip().strip('"\'')
            for t in m.group(1).split(",")
            if t.strip()
        }
    # Numbers, bools, dicts — not a tools list.
    return set()


def _normalise_tool_counts_keys(value: Any) -> set[str]:
    """Coerce a frontmatter ``tool_counts`` value into the set of keys.

    Symmetric to :func:`_normalise_tools_used`. Frontmatter often ships
    ``tool_counts`` as the raw inline JSON-looking string the converter
    wrote, but some pipelines (or future fixes) may return a real dict.
    """
    if value is None or value == "":
        return set()
    if isinstance(value, dict):
        return {str(k) for k in value.keys()}
    if isinstance(value, str):
        return set(_TOOL_COUNTS_KEYS_RE.findall(value))
    return set()


@register
class ToolsConsistency(LintRule):
    """Source pages: ``tools_used`` and ``tool_counts.keys()`` must agree.

    Catches the class of bug in `issues.md` #4 where a page lists a tool
    in the ``tools_used`` frontmatter array but the corresponding
    ``tool_counts`` object is missing that tool's entry (or vice-versa).
    Both surface on the session page, so divergence silently misleads
    anyone looking at the stats.
    """

    name = "tools_consistency"
    severity = "warning"

    def run(self, pages, *, llm_callback=None):
        issues: list[dict[str, Any]] = []
        for rel, page in pages.items():
            meta = page["meta"]
            if meta.get("type") != "source":
                continue
            # #410: tools_used can be list (post-parser), str (legacy),
            # or None — _normalise handles all three without a
            # TypeError on `re.search(regex, list)`.
            tools_used = _normalise_tools_used(meta.get("tools_used"))
            tool_counts_keys = _normalise_tool_counts_keys(meta.get("tool_counts"))
            if not tools_used or not tool_counts_keys:
                # One side missing — that's a different lint concern, skip.
                continue

            only_used = tools_used - tool_counts_keys
            only_counted = tool_counts_keys - tools_used
            if only_used:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": rel,
                    "message": (
                        f"tools_used has {sorted(only_used)} but tool_counts "
                        f"has no key for them"
                    ),
                })
            if only_counted:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": rel,
                    "message": (
                        f"tool_counts has keys {sorted(only_counted)} but "
                        f"tools_used does not list them"
                    ),
                })
        return issues
