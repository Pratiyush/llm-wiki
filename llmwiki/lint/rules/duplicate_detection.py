"""duplicate_detection — near-identical title + body pairs may be duplicates."""

from __future__ import annotations

import hashlib
from difflib import SequenceMatcher

from llmwiki.lint import LintRule, register


@register
class DuplicateDetection(LintRule):
    """Pages with near-identical titles **and** bodies may be duplicates.

    G-11 (#297): on a 714-page corpus the old rule emitted 76,963 pair
    warnings — roughly a third of all pairs — because two pages named
    ``CHANGELOG.md`` in different projects always scored title
    similarity 1.0. The rule is now scoped by ``project`` and demands
    **both** a high title match (≥0.95) **and** a body overlap
    (SequenceMatcher on the first 4 KB ≥0.80) before flagging. Non-
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
    # #sec-9 (#553): even after the bucket-restriction perf fix in
    # #412, a single bucket with thousands of pages (e.g. an entity
    # bucket on a 50k-page corpus) still does O(n²) body compares.
    # Bail out of the SequenceMatcher pass when a bucket exceeds this
    # threshold — fingerprint matches still flag exact duplicates,
    # we just stop the expensive near-duplicate search to keep lint
    # under a reasonable wall clock on large wikis.
    BUCKET_BAILOUT_SIZE = 500

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

            # #sec-9 (#553): bail out of the O(n²) body-compare pass
            # when the bucket is too large. Exact duplicates are still
            # caught by the fingerprint pass above; we just stop the
            # expensive near-duplicate search.
            if len(items) > self.BUCKET_BAILOUT_SIZE:
                continue
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
