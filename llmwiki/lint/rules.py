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
from llmwiki.text_utils import normalize_wikilink_parens

ARCHIVE_DIR = "archive/"

def _is_archived(rel: str) -> bool:
    """Check if a page is in the archive directory."""
    return rel.startswith(ARCHIVE_DIR)


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
    """[[wikilinks]] must resolve to existing pages.

    Also detects half-width parentheses in Chinese wikilinks
    (e.g. [[Foo(Bar)]] should be [[Foo（Bar）]]).
    """

    name = "link_integrity"
    severity = "warning"
    auto_fixable = True

    def run(self, pages, *, llm_callback=None):
        slugs = {_page_slug(rel) for rel in pages}
        issues = []
        for rel, page in pages.items():
            body = page["body"]
            seen_paren_warnings: set[str] = set()

            for target in set(WIKILINK_RE.findall(body)):
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

            # Check for half-width parens in Chinese wikilinks
            _, paren_warnings = normalize_wikilink_parens(body)
            for w in paren_warnings:
                if w not in seen_paren_warnings:
                    seen_paren_warnings.add(w)
                    issues.append({
                        "rule": self.name,
                        "severity": "info",
                        "page": rel,
                        "message": w,
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
            if _is_archived(rel):
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
    """Entities mentioned in body should resolve to existing pages, and
    entity pages should have proper metadata and cross-references."""

    name = "entity_consistency"
    severity = "warning"

    def run(self, pages, *, llm_callback=None):
        issues = []
        slugs = {_page_slug(rel) for rel in pages}

        for rel, page in pages.items():
            meta = page["meta"]
            page_type = meta.get("type", "")

            # 1. Entity pages must have entity_type
            if page_type == "entity" and "entity_type" not in meta:
                issues.append({
                    "rule": self.name,
                    "severity": "warning",
                    "page": rel,
                    "message": "entity page missing `entity_type` field in frontmatter",
                })

            # 2. Entity pages should have at least one [[wikilink]] in Connections
            if page_type == "entity":
                connections_match = re.search(
                    r"## Connections\n(.*?)(?:\n## |\Z)", page["body"], re.DOTALL
                )
                if connections_match:
                    conn_text = connections_match.group(1)
                    links = WIKILINK_RE.findall(conn_text)
                    for target in set(links):
                        t = target.split("#")[0].strip()
                        if t and t not in slugs:
                            issues.append({
                                "rule": self.name,
                                "severity": "info",
                                "page": rel,
                                "message": f"entity Connections links to non-existent page [[{target}]]",
                            })

            # 3. Source/synthesis pages: wikilinks in Key Claims/Summary should resolve
            if page_type in ("source", "synthesis"):
                # Extract wikilinks from body (not Connections section — those are covered by link_integrity)
                claims_match = re.search(
                    r"## Key Claims\n(.*?)(?:\n## |\Z)", page["body"], re.DOTALL
                )
                summary_match = re.search(
                    r"## Summary\n(.*?)(?:\n## |\Z)", page["body"], re.DOTALL
                )
                for section_match in (claims_match, summary_match):
                    if not section_match:
                        continue
                    links = WIKILINK_RE.findall(section_match.group(1))
                    for target in set(links):
                        t = target.split("#")[0].strip()
                        if t and t not in slugs:
                            issues.append({
                                "rule": self.name,
                                "severity": "info",
                                "page": rel,
                                "message": f"references non-existent entity [[{target}]] in claims/summary",
                            })

            # 4. Concept pages should have sources field
            if page_type == "concept" and "sources" not in meta:
                # Only warn if the page has substantial content
                if len(page["body"].strip()) > 200:
                    issues.append({
                        "rule": self.name,
                        "severity": "info",
                        "page": rel,
                        "message": "concept page with substantial content has no `sources` in frontmatter",
                    })

        return issues


@register
class DuplicateDetection(LintRule):
    """Pages with high title similarity may be duplicates.

    Skips archive pages. Different page types are never duplicates.
    Uses a higher threshold (0.90) for short Chinese titles (< 8 chars)
    to reduce false positives from character overlap.
    """

    name = "duplicate_detection"
    severity = "warning"

    THRESHOLD = 0.8
    THRESHOLD_CHINESE_SHORT = 0.90
    CHINESE_SHORT_MAX_LEN = 7  # chars, not bytes

    def run(self, pages, *, llm_callback=None):
        issues = []
        items = [(rel, p) for rel, p in pages.items() if not _is_archived(rel)]
        for i in range(len(items)):
            rel_a, page_a = items[i]
            type_a = page_a["meta"].get("type", "")
            title_a = page_a["meta"].get("title", "").lower()
            if not title_a:
                continue
            for j in range(i + 1, len(items)):
                rel_b, page_b = items[j]
                type_b = page_b["meta"].get("type", "")
                title_b = page_b["meta"].get("title", "").lower()
                if not title_b:
                    continue
                # Different types are never duplicates
                if type_a and type_b and type_a != type_b:
                    continue
                # Same directory (siblings) — likely intentional subdivisions, skip
                if self._same_parent(rel_a, rel_b):
                    continue
                ratio = SequenceMatcher(None, title_a, title_b).ratio()
                effective_threshold = self.effective_threshold(title_a, title_b)
                if ratio >= effective_threshold:
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel_a,
                        "message": (
                            f"possible duplicate of {rel_b!r} "
                            f"(title similarity {ratio:.2f}, threshold {effective_threshold:.2f})"
                        ),
                    })
        return issues

    @staticmethod
    def _same_parent(rel_a: str, rel_b: str) -> bool:
        """Check if two pages share the same wiki subdirectory (e.g. both in concepts/)."""
        pa = rel_a.rsplit("/", 1)[0] if "/" in rel_a else ""
        pb = rel_b.rsplit("/", 1)[0] if "/" in rel_b else ""
        return pa == pb and pa != ""

    def effective_threshold(self, title_a: str, title_b: str) -> float:
        """Pick threshold based on title characteristics."""
        if self._is_chinese_short(title_a) or self._is_chinese_short(title_b):
            return self.THRESHOLD_CHINESE_SHORT
        return self.THRESHOLD

    def _is_chinese_short(self, title: str) -> bool:
        """True if title is Chinese-dominant and short (high character-overlap risk)."""
        # Count CJK characters
        cjk = sum(1 for c in title if "一" <= c <= "鿿")
        return cjk > 0 and cjk <= self.CHINESE_SHORT_MAX_LEN


@register
class IndexSync(LintRule):
    """wiki/index.md must list every page, and listed pages must exist.

    Archive pages are exempt from listing requirements.
    Dead index links can be auto-removed (auto_fixable).
    """

    name = "index_sync"
    severity = "error"
    auto_fixable = True

    link_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def run(self, pages, *, llm_callback=None):
        index = pages.get("index.md")
        if not index:
            return []

        issues: list[dict[str, Any]] = []
        dead_hrefs: set[str] = set()
        listed_slugs: set[str] = set()

        for match in self.link_re.finditer(index["body"]):
            href = match.group(2)
            if href.startswith("http"):
                continue
            href = href.split("#")[0]
            if not href:
                continue
            if href not in pages and not href.lstrip("./") in pages:
                dead_hrefs.add(href)
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": "index.md",
                    "message": f"dead index link → {href}",
                })
            else:
                listed_slugs.add(href.rsplit("/", 1)[-1].removesuffix(".md"))

        # Auto-fix: remove dead links from index.md
        if dead_hrefs and self.auto_fixable:
            self._remove_dead_links(index, dead_hrefs)

        # Check unlisted pages (skip nav, _context, and archive)
        nav_pages = {"index.md", "overview.md", "log.md", "hints.md", "hot.md",
                     "MEMORY.md", "SOUL.md", "CRITICAL_FACTS.md", "dashboard.md"}
        for rel in pages:
            if rel in nav_pages or rel.endswith("_context.md") or _is_archived(rel):
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

    def _remove_dead_links(self, index: dict, dead_hrefs: set[str]) -> None:
        """Remove dead index entries by rewriting index.md body in-place."""
        index_path = index["path"]
        lines = index["text"].splitlines(keepends=True)
        new_lines = []
        for line in lines:
            m = self.link_re.search(line)
            if m:
                href = m.group(2).split("#")[0]
                if href in dead_hrefs:
                    continue  # drop this line
            new_lines.append(line)
        new_text = "".join(new_lines)
        if new_text != index["text"]:
            index_path.write_text(new_text, encoding="utf-8")
            # Refresh in-memory page dict
            index["text"] = new_text
            index["body"] = new_text.split("---\n", 2)[-1] if new_text.startswith("---") else new_text


# ═══════════════════════════════════════════════════════════════════════
#  LLM-POWERED RULES (3)
# ═══════════════════════════════════════════════════════════════════════


@register
class ContradictionDetection(LintRule):
    """Detect semantic contradictions across source pages (LLM-powered).

    Strategy:
    1. Group source pages by topic (using tags or parent directory).
    2. For each group, extract Key Claims and feed pairs to LLM.
    3. LLM reports specific contradictions in numeric values, thresholds,
       process steps, etc.
    """

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

        issues = []
        # First run structural check
        issues.extend(self._structural_check(pages))

        # Group source pages by topic
        llm_calls = 0
        MAX_LLM_CALLS = 10
        groups = self._group_by_topic(pages)
        for topic, group_pages in groups.items():
            if len(group_pages) < 2 or llm_calls >= MAX_LLM_CALLS:
                continue
            # Compare pairs (limit to first 5 pages per group)
            group_pages = group_pages[:5]
            for i in range(len(group_pages)):
                for j in range(i + 1, len(group_pages)):
                    if llm_calls >= MAX_LLM_CALLS:
                        break
                    rel_a, page_a = group_pages[i]
                    rel_b, page_b = group_pages[j]
                    claims_a = self._extract_claims(page_a)
                    claims_b = self._extract_claims(page_b)
                    if not claims_a or not claims_b:
                        continue
                    try:
                        result = llm_callback(
                            f"以下是知识库中两个页面的关键声明，请检查是否存在数值、流程、标准、门槛等方面的矛盾。\n"
                            f"只报告确定的矛盾，每行一条，格式：\n"
                            f"CONTRADICTION: 页面A说「XXX」，但页面B说「YYY」\n"
                            f"如果没有矛盾，只回答：NO_CONTRADICTION\n\n"
                            f"页面「{page_a['meta'].get('title', rel_a)}」的声明：\n{claims_a[:1500]}\n\n"
                            f"页面「{page_b['meta'].get('title', rel_b)}」的声明：\n{claims_b[:1500]}"
                        )
                        if result and "NO_CONTRADICTION" not in result:
                            for line in result.strip().split("\n"):
                                line = line.strip()
                                if line.startswith("CONTRADICTION:"):
                                    issues.append({
                                        "rule": self.name,
                                        "severity": "warning",
                                        "page": rel_a,
                                        "message": f"与 {rel_b} 存在矛盾: {line[len('CONTRADICTION:'):].strip()}",
                                    })
                    except Exception:
                        pass  # LLM call failed, skip
                    finally:
                        llm_calls += 1
        return issues

    def _structural_check(self, pages):
        """Fallback: check for explicit Contradictions sections."""
        issues = []
        for rel, page in pages.items():
            if "## Contradictions" in page["body"]:
                section_match = re.search(
                    r"## Contradictions\n(.*?)(?:\n## |\Z)", page["body"], re.DOTALL,
                )
                if section_match and section_match.group(1).strip():
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel,
                        "message": "page has ## Contradictions section — review required",
                    })
        return issues

    def _group_by_topic(self, pages):
        """Group source pages by their parent directory or tags."""
        groups: dict[str, list] = {}
        for rel, page in pages.items():
            meta = page["meta"]
            if meta.get("type") != "source":
                continue
            # Use parent directory as topic
            parts = rel.split("/")
            topic = parts[1] if len(parts) > 1 else "root"
            groups.setdefault(topic, []).append((rel, page))
        return groups

    def _extract_claims(self, page):
        """Extract Key Claims section text."""
        match = re.search(r"## Key Claims\n(.*?)(?:\n## |\Z)", page["body"], re.DOTALL)
        if match:
            return match.group(1).strip()[:2000]
        return ""


@register
class ClaimVerification(LintRule):
    """Verify claims in synthesis/entity/concept pages are supported by sources.

    Strategy:
    1. Find pages with Key Claims/Key Facts sections.
    2. Locate their cited sources (via frontmatter sources or wikilinks).
    3. Ask LLM if each claim is supported by the source content.
    """

    name = "claim_verification"
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

        issues = []
        issues.extend(self._structural_check(pages))

        # Build slug → page lookup
        slug_to_page = {}
        for rel, page in pages.items():
            slug_to_page[_page_slug(rel)] = page
            slug_to_page[rel] = page

        # Check pages that have claims and cite sources
        checked = 0
        for rel, page in pages.items():
            if checked >= 15:
                break  # Limit LLM calls
            meta = page["meta"]
            page_type = meta.get("type", "")
            if page_type not in ("synthesis", "entity", "concept"):
                continue

            claims_text = self._extract_claims(page)
            if not claims_text:
                continue

            # Find source content
            source_content = self._find_source_content(page, pages, slug_to_page)
            if not source_content:
                continue

            try:
                result = llm_callback(
                    f"以下是知识库中一个页面的声明和它的来源文件摘要。\n"
                    f"请判断每个声明是否被来源支撑。逐条检查，格式：\n"
                    f"SUPPORTED: 声明内容概要\n"
                    f"UNSUPPORTED: 声明内容概要 — 缺少什么\n\n"
                    f"声明（来自 {meta.get('title', rel)}）：\n{claims_text[:1500]}\n\n"
                    f"来源摘要：\n{source_content[:2000]}"
                )
                if result and "UNSUPPORTED" in result:
                    for line in result.strip().split("\n"):
                        line = line.strip()
                        if line.startswith("UNSUPPORTED:"):
                            issues.append({
                                "rule": self.name,
                                "severity": "warning",
                                "page": rel,
                                "message": f"声明缺乏来源支撑: {line[len('UNSUPPORTED:'):].strip()}",
                            })
                checked += 1
            except Exception:
                pass
        return issues

    def _structural_check(self, pages):
        """Fallback: check that claim pages cite sources."""
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

    def _extract_claims(self, page):
        """Extract Key Claims or Key Facts section text."""
        for section in ("Key Claims", "Key Facts"):
            match = re.search(
                rf"## {section}\n(.*?)(?:\n## |\Z)", page["body"], re.DOTALL
            )
            if match and match.group(1).strip():
                return match.group(1).strip()[:2000]
        return ""

    def _find_source_content(self, page, pages, slug_to_page):
        """Find and concatenate content from cited source pages."""
        meta = page["meta"]
        parts = []

        # Check frontmatter sources
        sources_str = meta.get("sources", "")
        if sources_str:
            # Parse YAML-like list: [slug1, slug2]
            source_slugs = [s.strip().strip('"').strip("'") for s in sources_str.strip("[]").split(",")]
            for slug in source_slugs:
                slug = slug.strip()
                if not slug:
                    continue
                # Try to find matching page
                for rel, src_page in pages.items():
                    if slug in rel or slug == _page_slug(rel):
                        parts.append(src_page["body"][:2000])
                        if len(parts) >= 2:
                            break

        # Check wikilinks to source pages
        if not parts:
            links = WIKILINK_RE.findall(page["body"])
            seen = set()
            for target in links:
                t = target.split("#")[0].strip()
                if t in seen or not t:
                    continue
                seen.add(t)
                slug = _page_slug(t)
                for rel, src_page in pages.items():
                    if _page_slug(rel) == slug and src_page["meta"].get("type") == "source":
                        parts.append(src_page["body"][:2000])
                        if len(parts) >= 2:
                            break

        return "\n\n".join(parts) if parts else ""


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
                    f"(threshold {self.STALE_DAYS}) — review with `/wiki-review`"
                ),
            })
        return issues


@register
class SummaryAccuracy(LintRule):
    """Check that ## Summary section accurately reflects page content.

    Strategy:
    1. Find pages with a ## Summary section.
    2. Send summary + body to LLM for comparison.
    3. Flag summaries that miss key points or contain inaccuracies.
    """

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

        issues = []
        issues.extend(self._structural_check(pages))

        checked = 0
        for rel, page in pages.items():
            if checked >= 20:
                break  # Limit LLM calls
            meta = page["meta"]
            page_type = meta.get("type", "")
            if page_type not in ("source", "entity", "concept", "synthesis"):
                continue

            summary = self._extract_summary(page)
            if not summary:
                continue

            body = page["body"]
            if len(body.strip()) < 100:
                continue

            try:
                result = llm_callback(
                    f"以下是知识库页面的 Summary 段落和页面正文。\n"
                    f"请判断 Summary 是否准确概括了正文核心内容。关注：\n"
                    f"1. 是否遗漏了重要的数值、门槛、流程\n"
                    f"2. 是否包含正文中没有的信息\n"
                    f"3. 是否有与正文矛盾的内容\n\n"
                    f"回答 MATCH 或 MISMATCH。\n"
                    f"如果是 MISMATCH，说明具体哪里不匹配以及建议修改。\n\n"
                    f"当前 Summary:\n{summary[:1000]}\n\n"
                    f"页面正文:\n{body[:4000]}"
                )
                if result and "MISMATCH" in result:
                    # Extract mismatch details
                    detail = result.replace("MISMATCH", "").strip().strip(":").strip()
                    issues.append({
                        "rule": self.name,
                        "severity": "info",
                        "page": rel,
                        "message": f"summary 与正文不匹配: {detail[:200]}",
                    })
                checked += 1
            except Exception:
                pass
        return issues

    def _structural_check(self, pages):
        """Fallback: check summary section exists and is non-empty."""
        issues = []
        for rel, page in pages.items():
            meta = page["meta"]
            # Check frontmatter summary
            summary_fm = meta.get("summary", "")
            if "summary" in meta and not summary_fm.strip():
                issues.append({
                    "rule": self.name,
                    "severity": "info",
                    "page": rel,
                    "message": "frontmatter summary field is empty",
                })
            # Check ## Summary section
            summary_section = self._extract_summary(page)
            page_type = meta.get("type", "")
            if page_type in ("source", "entity", "concept") and not summary_section:
                if len(page["body"].strip()) > 500:
                    issues.append({
                        "rule": self.name,
                        "severity": "info",
                        "page": rel,
                        "message": "substantial page lacks ## Summary section",
                    })
        return issues

    def _extract_summary(self, page):
        """Extract ## Summary section text."""
        match = re.search(r"## Summary\n(.*?)(?:\n## |\Z)", page["body"], re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
