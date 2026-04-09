"""Auto-generated versus-comparison pages (v0.7 · closes #58).

Programmatic SEO / navigation pattern: given N structured entity pages
(from #55), emit a comparison page for every pair where both entities
have enough overlapping fields to be meaningfully compared. Each page
contains a side-by-side info table, a benchmark bar chart over shared
benchmark keys, a price delta row, and a stub `## Summary` heading
the user or LLM can fill in later.

Key design choices:

* **Combinatorial cap** — pair generation is O(n²). With hundreds of
  model entities that's tens of thousands of pages. A `max_pairs` cap
  (default 500, configurable) keeps the build budget sane. Pairs are
  selected by pair "compare score" (higher = more shared fields).
* **User override** — if `wiki/vs/<slug>.md` exists, the build uses
  that file verbatim and skips the auto-gen for that pair. Matches
  the `wiki/projects/<slug>.md` override convention.
* **Non-comparable skip** — pairs with fewer than `min_shared_fields`
  (default 3) overlapping fields are silently dropped. A provider
  comparison between "Anthropic" and "OpenAI" with no shared numeric
  fields isn't useful.
* **Symmetric naming** — slugs are sorted alphabetically so
  `ClaudeSonnet4` vs `GPT5` → `ClaudeSonnet4-vs-GPT5`, never the
  other way. This guarantees one URL per pair and avoids duplicate
  content.

Stdlib-only. Depends on `schema.py` (model profile parsing) and
`models_page.py` (entity discovery).
"""

from __future__ import annotations

import html
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Optional, TypedDict

from llmwiki.schema import (
    KNOWN_BENCHMARKS,
    ModelProfile,
    benchmark_label,
    format_price,
)


class ComparisonPair(TypedDict):
    slug_a: str
    slug_b: str
    title_a: str
    title_b: str
    profile_a: ModelProfile
    profile_b: ModelProfile
    shared_fields: list[str]
    score: int  # number of shared fields — higher ranks earlier


# ─── pair discovery ─────────────────────────────────────────────────────


def _profile_field_set(profile: ModelProfile) -> set[str]:
    """Return the set of "field paths" a profile actually has values for.
    Used to compute the intersection between two profiles."""
    out: set[str] = set()
    if profile.get("provider"):
        out.add("provider")
    model_block = profile.get("model", {})
    for k in ("context_window", "max_output", "license", "released"):
        if k in model_block:
            out.add(f"model.{k}")
    pricing = profile.get("pricing", {})
    for k in ("input_per_1m", "output_per_1m", "cache_read_per_1m", "cache_write_per_1m"):
        if k in pricing:
            out.add(f"pricing.{k}")
    if profile.get("modalities"):
        out.add("modalities")
    for k in (profile.get("benchmarks") or {}).keys():
        out.add(f"benchmarks.{k}")
    return out


def compare_pair_score(a: ModelProfile, b: ModelProfile) -> tuple[int, list[str]]:
    """Return `(score, shared_fields)` for a pair of profiles.

    The score is the count of structured fields both profiles populate.
    Benchmarks are weighted equally with other fields — having both
    MMLU and SWE-bench on both sides is worth 2 score points, same as
    both having a `context_window` and `input_per_1m`.
    """
    shared = sorted(_profile_field_set(a) & _profile_field_set(b))
    return len(shared), shared


def generate_pairs(
    entries: list[tuple[Path, ModelProfile]],
    min_shared_fields: int = 3,
    max_pairs: int = 500,
) -> list[ComparisonPair]:
    """Walk every 2-combination of entries and emit a `ComparisonPair`
    for each one that hits the shared-fields threshold.

    Sorted by score descending (most comparable pairs first), then
    alphabetically for stability. Capped at `max_pairs` so the build
    doesn't explode on large wikis.
    """
    if len(entries) < 2:
        return []
    pairs: list[ComparisonPair] = []
    for (pa, profile_a), (pb, profile_b) in combinations(entries, 2):
        score, shared = compare_pair_score(profile_a, profile_b)
        if score < min_shared_fields:
            continue
        slug_a, slug_b = sorted([pa.stem, pb.stem])
        # Swap profiles to match the sorted slugs
        if slug_a == pa.stem:
            title_a = profile_a.get("title", pa.stem)
            title_b = profile_b.get("title", pb.stem)
            pa_profile, pb_profile = profile_a, profile_b
        else:
            title_a = profile_b.get("title", pb.stem)
            title_b = profile_a.get("title", pa.stem)
            pa_profile, pb_profile = profile_b, profile_a
        pairs.append(
            ComparisonPair(
                slug_a=slug_a,
                slug_b=slug_b,
                title_a=title_a,
                title_b=title_b,
                profile_a=pa_profile,
                profile_b=pb_profile,
                shared_fields=shared,
                score=score,
            )
        )
    pairs.sort(key=lambda p: (-p["score"], p["slug_a"], p["slug_b"]))
    return pairs[:max_pairs]


def pair_slug(pair: ComparisonPair) -> str:
    """Return the canonical URL slug for a pair:
    `<slug_a>-vs-<slug_b>` with alphabetical order enforced."""
    return f"{pair['slug_a']}-vs-{pair['slug_b']}"


# ─── render: side-by-side table ─────────────────────────────────────────


def _render_kv(label: str, val_a: Any, val_b: Any, is_numeric: bool = False) -> str:
    """Render one `<tr>` in the side-by-side info table."""
    highlight = ""
    if val_a is not None and val_b is not None and val_a != val_b:
        highlight = " class='cell-diff'"
    a_cell = html.escape(str(val_a)) if val_a is not None else '<span class="muted">—</span>'
    b_cell = html.escape(str(val_b)) if val_b is not None else '<span class="muted">—</span>'
    return (
        f'<tr><th>{html.escape(label)}</th>'
        f'<td{highlight}>{a_cell}</td>'
        f'<td{highlight}>{b_cell}</td></tr>'
    )


def _fmt_context(n: Optional[int]) -> Optional[str]:
    if n is None:
        return None
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n // 1000}K"
    return str(n)


def render_comparison_table(pair: ComparisonPair) -> str:
    """Render the side-by-side info table for a pair."""
    a, b = pair["profile_a"], pair["profile_b"]
    a_model = a.get("model", {})
    b_model = b.get("model", {})
    a_pricing = a.get("pricing", {})
    b_pricing = b.get("pricing", {})
    currency_a = a_pricing.get("currency", "USD")
    currency_b = b_pricing.get("currency", "USD")

    rows: list[str] = []
    rows.append(
        '<tr><th></th>'
        f'<th class="vs-colhead"><a href="../models/{html.escape(pair["slug_a"])}.html">'
        f'{html.escape(pair["title_a"])}</a></th>'
        f'<th class="vs-colhead"><a href="../models/{html.escape(pair["slug_b"])}.html">'
        f'{html.escape(pair["title_b"])}</a></th></tr>'
    )
    rows.append(_render_kv("Provider", a.get("provider"), b.get("provider")))
    rows.append(_render_kv(
        "Context window",
        _fmt_context(a_model.get("context_window")),
        _fmt_context(b_model.get("context_window")),
    ))
    rows.append(_render_kv(
        "Max output",
        _fmt_context(a_model.get("max_output")),
        _fmt_context(b_model.get("max_output")),
    ))
    rows.append(_render_kv("License", a_model.get("license"), b_model.get("license")))
    rows.append(_render_kv("Released", a_model.get("released"), b_model.get("released")))

    input_a = format_price(a_pricing["input_per_1m"], currency_a) if "input_per_1m" in a_pricing else None
    input_b = format_price(b_pricing["input_per_1m"], currency_b) if "input_per_1m" in b_pricing else None
    output_a = format_price(a_pricing["output_per_1m"], currency_a) if "output_per_1m" in a_pricing else None
    output_b = format_price(b_pricing["output_per_1m"], currency_b) if "output_per_1m" in b_pricing else None
    rows.append(_render_kv("Input / 1M", input_a, input_b))
    rows.append(_render_kv("Output / 1M", output_a, output_b))

    a_mod = ", ".join(a.get("modalities", [])) or None
    b_mod = ", ".join(b.get("modalities", [])) or None
    rows.append(_render_kv("Modalities", a_mod, b_mod))

    return (
        '<table class="vs-table">'
        + "".join(rows)
        + '</table>'
    )


# ─── render: benchmark bar chart ────────────────────────────────────────


def render_benchmark_chart(pair: ComparisonPair) -> str:
    """SVG horizontal bar chart comparing shared benchmarks."""
    a_benches = pair["profile_a"].get("benchmarks") or {}
    b_benches = pair["profile_b"].get("benchmarks") or {}
    shared_keys = sorted(set(a_benches) & set(b_benches))
    if not shared_keys:
        return ""

    # Stable order: known benchmarks in declaration order first, then unknowns
    known_order = [k for k in KNOWN_BENCHMARKS if k in shared_keys]
    unknown_order = sorted(set(shared_keys) - set(KNOWN_BENCHMARKS))
    ordered = known_order + unknown_order

    row_h = 22
    bar_h = 9
    label_w = 140
    bar_max = 260
    value_w = 54
    width = label_w + bar_max + value_w + 20
    height = len(ordered) * row_h + 20

    parts: list[str] = [
        f'<svg class="vs-bench-chart" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="Benchmark comparison: {html.escape(pair["title_a"])} vs {html.escape(pair["title_b"])}">',
        '<style>',
        '.vs-bench-chart text { font: 10px system-ui, -apple-system, sans-serif; fill: var(--text-secondary, #475569); }',
        '.vs-bench-chart .vs-bench-label { font-weight: 500; fill: var(--text, #0f172a); }',
        '.vs-bench-chart .bar-a { fill: var(--accent, #7C3AED); }',
        '.vs-bench-chart .bar-b { fill: var(--token-cache-read, #10b981); }',
        '</style>',
    ]
    for i, key in enumerate(ordered):
        a_val = a_benches[key]
        b_val = b_benches[key]
        y = 10 + i * row_h
        label = benchmark_label(key)
        parts.append(
            f'<text class="vs-bench-label" x="{label_w - 8}" '
            f'y="{y + bar_h + 2}" text-anchor="end">{html.escape(label)}</text>'
        )
        a_w = max(1, round(a_val * bar_max))
        b_w = max(1, round(b_val * bar_max))
        parts.append(
            f'<rect class="bar-a" x="{label_w}" y="{y - 1}" '
            f'width="{a_w}" height="{bar_h - 1}" rx="1">'
            f'<title>{html.escape(pair["title_a"])}: {a_val * 100:.1f}%</title>'
            f'</rect>'
        )
        parts.append(
            f'<rect class="bar-b" x="{label_w}" y="{y + bar_h}" '
            f'width="{b_w}" height="{bar_h - 1}" rx="1">'
            f'<title>{html.escape(pair["title_b"])}: {b_val * 100:.1f}%</title>'
            f'</rect>'
        )
        parts.append(
            f'<text x="{label_w + bar_max + 6}" y="{y + bar_h + 2}">'
            f'{a_val * 100:.1f}% / {b_val * 100:.1f}%</text>'
        )
    # Legend
    parts.append(
        f'<text x="{label_w}" y="{height - 4}">'
        f'<tspan fill="var(--accent, #7C3AED)">■</tspan> {html.escape(pair["title_a"])} '
        f'<tspan fill="var(--token-cache-read, #10b981)" dx="10">■</tspan> {html.escape(pair["title_b"])}'
        f'</text>'
    )
    parts.append('</svg>')
    return "\n".join(parts)


# ─── render: full comparison page body ──────────────────────────────────


def render_comparison_body(pair: ComparisonPair) -> str:
    """Render the `<article>`-ready body of a comparison page, without
    the page chrome. The caller wraps it in the standard layout."""
    bench_chart = render_benchmark_chart(pair)
    bench_block = ""
    if bench_chart:
        bench_block = (
            '<section class="vs-section">'
            '<h2>Benchmarks</h2>'
            f'{bench_chart}'
            '</section>'
        )

    # Price delta
    a_pricing = pair["profile_a"].get("pricing", {})
    b_pricing = pair["profile_b"].get("pricing", {})
    price_block = ""
    if "input_per_1m" in a_pricing and "input_per_1m" in b_pricing:
        pa = a_pricing["input_per_1m"]
        pb = b_pricing["input_per_1m"]
        if pa != pb:
            cheaper = pair["title_a"] if pa < pb else pair["title_b"]
            pct = abs(pa - pb) / max(pa, pb) * 100
            price_block = (
                '<section class="vs-section">'
                '<h2>Price delta</h2>'
                f'<p><strong>{html.escape(cheaper)}</strong> is '
                f'<strong>{pct:.1f}%</strong> cheaper per 1M input tokens '
                f'({format_price(min(pa, pb))} vs '
                f'{format_price(max(pa, pb))}).</p>'
                '</section>'
            )

    title = f'{pair["title_a"]} vs {pair["title_b"]}'
    return (
        f'<section class="vs-section">\n'
        f'<h2>Side-by-side</h2>\n'
        f'{render_comparison_table(pair)}\n'
        f'</section>\n'
        + bench_block + "\n"
        + price_block + "\n"
        + '<section class="vs-section vs-summary-stub">\n'
        f'<h2>Summary</h2>\n'
        f'<p class="muted"><em>This section is a stub — fill it in with '
        f'your perspective on {html.escape(title)}. The auto-generated '
        f'comparison above gives the structured facts; the narrative '
        f'belongs to you.</em></p>\n'
        '</section>'
    )


# ─── index page + discovery of user overrides ──────────────────────────


def render_comparisons_index(pairs: list[ComparisonPair]) -> str:
    """Emit the `vs/index.html` body — a table of every generated pair
    with titles, shared-field count, and a link."""
    if not pairs:
        return (
            '<section class="section"><div class="container">'
            '<h2>Model comparisons</h2>'
            '<p class="muted">No comparable model pairs found. Add more '
            'model-entity pages under <code>wiki/entities/</code> with '
            '<code>entity_kind: ai-model</code> and this index will '
            'populate automatically.</p>'
            '</div></section>'
        )
    rows: list[str] = []
    for pair in pairs:
        slug = pair_slug(pair)
        rows.append(
            f'<tr>'
            f'<td><a href="{html.escape(slug)}.html">'
            f'{html.escape(pair["title_a"])} vs {html.escape(pair["title_b"])}</a></td>'
            f'<td>{pair["score"]}</td>'
            f'</tr>'
        )
    return (
        '<section class="section"><div class="container">'
        '<h2>Model comparisons</h2>'
        '<p class="muted">Auto-generated head-to-head pages for every '
        'pair of model-entity pages with enough shared structured '
        'fields to be meaningfully compared. Pairs with a user-authored '
        '<code>wiki/vs/&lt;slug&gt;.md</code> override replace the '
        'auto-gen for that URL.</p>'
        '<table class="vs-index-table">'
        '<thead><tr><th>Comparison</th><th>Shared fields</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody>'
        '</table>'
        '</div></section>'
    )


def discover_user_overrides(overrides_dir: Path) -> dict[str, str]:
    """Walk `overrides_dir` (usually `wiki/vs/`) and return a
    `{slug: body_text}` map. The slug is the file stem; the body is
    the raw markdown (frontmatter not supported here — overrides are
    prose-only)."""
    out: dict[str, str] = {}
    if not overrides_dir.is_dir():
        return out
    for path in sorted(overrides_dir.glob("*.md")):
        try:
            out[path.stem] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return out
