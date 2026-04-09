"""Models page + info-card rendering (v0.7 · closes #55).

Discovers entity pages under `wiki/entities/` that carry the new
`entity_kind: ai-model` schema, validates each one via `schema.py`,
and emits:

* A per-model detail page `site/models/<slug>.html` with a structured
  info-card alongside the free-form markdown body.
* A sortable index `site/models/index.html` with every valid model
  profile as a row — sort by context window, input/output price, or
  any benchmark score.

Unlike the session pipeline (which reads from `raw/sessions/`), this
module reads from `wiki/entities/` — the LLM-maintained knowledge
layer. Pages without the ai-model schema are ignored entirely.

Stdlib-only. No new dependencies.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from llmwiki.schema import (
    ENTITY_KIND_AI_MODEL,
    ModelProfile,
    benchmark_label,
    format_price,
    is_model_entity,
    parse_model_profile,
)

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Lightweight frontmatter parser — mirrors the one in build.py so this
    module stays self-contained and can be tested without touching build.py.
    Supports key: value pairs (optionally quoted) and bracketed list values."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    meta: dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key.strip()] = (
                [x.strip() for x in inner.split(",") if x.strip()] if inner else []
            )
        else:
            meta[key.strip()] = value
    return meta, body


def discover_model_entities(
    entities_dir: Path,
) -> list[tuple[Path, ModelProfile, list[str], str]]:
    """Walk `entities_dir` and return every page that validates as an
    `ai-model` entity.

    Returns a list of `(path, profile, warnings, body)` tuples. Pages
    without the right `entity_kind` are silently skipped. Parse errors
    surface as warnings — the page is still returned.

    Note: `build.py` also needs the raw meta dict for #56 (changelog
    timeline). Use `discover_model_entities_with_meta()` when you
    need the full frontmatter, not just the validated profile.
    """
    return [
        (path, profile, warnings, body)
        for path, _meta, profile, warnings, body in discover_model_entities_with_meta(
            entities_dir
        )
    ]


def discover_model_entities_with_meta(
    entities_dir: Path,
) -> list[tuple[Path, dict[str, Any], ModelProfile, list[str], str]]:
    """Same walker as `discover_model_entities` but also yields the raw
    frontmatter dict so callers can extract fields outside the core
    schema (e.g. `changelog:` for #56)."""
    out: list[tuple[Path, dict[str, Any], ModelProfile, list[str], str]] = []
    if not entities_dir.is_dir():
        return out
    for path in sorted(entities_dir.glob("*.md")):
        if path.name == "_context.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _parse_frontmatter(text)
        if not is_model_entity(meta):
            continue
        profile, warnings = parse_model_profile(meta)
        out.append((path, meta, profile, warnings, body))
    return out


# ─── info-card render ──────────────────────────────────────────────────


def render_model_info_card(profile: ModelProfile) -> str:
    """Render a standalone HTML info-card for a single model profile.

    Used on both the per-model detail page and inlined into the
    `/models/` index when the user clicks a row. Empty profile returns
    an empty string — the caller decides whether to show a placeholder.
    """
    if not profile:
        return ""

    rows: list[str] = []

    title = profile.get("title")
    provider = profile.get("provider")
    if title or provider:
        header_bits = []
        if title:
            header_bits.append(f'<span class="model-card-title">{html.escape(title)}</span>')
        if provider:
            header_bits.append(f'<span class="model-card-provider muted">{html.escape(provider)}</span>')
        rows.append(f'<div class="model-card-header">{" · ".join(header_bits)}</div>')

    details = profile.get("model", {})
    details_bits: list[str] = []
    if "context_window" in details:
        details_bits.append(
            f'<div class="model-card-kv"><span class="muted">Context</span>'
            f'<span>{_format_tokens(details["context_window"])}</span></div>'
        )
    if "max_output" in details:
        details_bits.append(
            f'<div class="model-card-kv"><span class="muted">Max output</span>'
            f'<span>{_format_tokens(details["max_output"])}</span></div>'
        )
    if "license" in details:
        details_bits.append(
            f'<div class="model-card-kv"><span class="muted">License</span>'
            f'<span>{html.escape(details["license"])}</span></div>'
        )
    if "released" in details:
        details_bits.append(
            f'<div class="model-card-kv"><span class="muted">Released</span>'
            f'<span>{html.escape(details["released"])}</span></div>'
        )
    modalities = profile.get("modalities", [])
    if modalities:
        details_bits.append(
            f'<div class="model-card-kv"><span class="muted">Modalities</span>'
            f'<span>{html.escape(", ".join(modalities))}</span></div>'
        )

    pricing = profile.get("pricing", {})
    if pricing:
        currency = pricing.get("currency", "USD")
        price_parts: list[str] = []
        if "input_per_1m" in pricing:
            price_parts.append(
                f'<span class="model-price-cell">'
                f'<span class="muted">input</span> '
                f'{format_price(pricing["input_per_1m"], currency)}/1M</span>'
            )
        if "output_per_1m" in pricing:
            price_parts.append(
                f'<span class="model-price-cell">'
                f'<span class="muted">output</span> '
                f'{format_price(pricing["output_per_1m"], currency)}/1M</span>'
            )
        if "cache_read_per_1m" in pricing:
            price_parts.append(
                f'<span class="model-price-cell">'
                f'<span class="muted">cache read</span> '
                f'{format_price(pricing["cache_read_per_1m"], currency)}/1M</span>'
            )
        effective = pricing.get("effective", "")
        effective_txt = (
            f' <span class="muted">· effective {html.escape(effective)}</span>'
            if effective else ""
        )
        details_bits.append(
            f'<div class="model-card-row">'
            f'<span class="muted model-card-row-label">Pricing</span>'
            f'<span class="model-card-row-val">{" · ".join(price_parts)}{effective_txt}</span>'
            f'</div>'
        )

    if details_bits:
        rows.append('<div class="model-card-grid">' + "".join(details_bits) + '</div>')

    benches = profile.get("benchmarks", {})
    if benches:
        bench_rows = []
        for key, score in sorted(benches.items(), key=lambda kv: -kv[1]):
            pct = f"{score * 100:.1f}%"
            bench_rows.append(
                f'<div class="model-bench-row">'
                f'<span class="model-bench-label">{html.escape(benchmark_label(key))}</span>'
                f'<span class="model-bench-bar"><span class="model-bench-fill" style="width: {score * 100:.1f}%"></span></span>'
                f'<span class="model-bench-value">{pct}</span>'
                f'</div>'
            )
        rows.append(
            '<div class="model-card-benches">'
            '<div class="model-card-section-title muted">Benchmarks</div>'
            + "".join(bench_rows) +
            '</div>'
        )

    return f'<div class="model-card">{"".join(rows)}</div>'


def _format_tokens(n: int) -> str:
    """Format a token count with K/M suffix. Mirrors viz_tokens.format_tokens
    but kept local to avoid a circular import."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n // 1000}K"
    return str(n)


# ─── /models/index.html ────────────────────────────────────────────────


def render_models_index(
    entries: list[tuple[Path, ModelProfile, list[str], str]],
) -> str:
    """Render the body section for `/models/index.html` — a sortable
    table of every model entity discovered."""
    if not entries:
        return (
            '<section class="section">\n'
            '  <div class="container">\n'
            '    <h2>Models</h2>\n'
            '    <p class="muted">No model-entity pages found under '
            '<code>wiki/entities/</code>. Add a page with '
            '<code>entity_kind: ai-model</code> to populate this index.</p>\n'
            '  </div>\n'
            '</section>\n'
        )

    # Collect every benchmark key across all entries so the table shows
    # consistent columns.
    all_bench_keys: set[str] = set()
    for _, profile, _, _ in entries:
        all_bench_keys.update((profile.get("benchmarks") or {}).keys())
    # Sort benchmarks: known ones in their declared order, then unknowns alpha.
    from llmwiki.schema import KNOWN_BENCHMARKS
    known_order = [k for k in KNOWN_BENCHMARKS if k in all_bench_keys]
    unknown_order = sorted(all_bench_keys - set(KNOWN_BENCHMARKS))
    bench_cols = known_order + unknown_order

    header = ['<th>Model</th>', '<th>Provider</th>', '<th>Context</th>',
              '<th>Input / 1M</th>', '<th>Output / 1M</th>']
    for bk in bench_cols:
        header.append(f'<th>{html.escape(benchmark_label(bk))}</th>')

    rows: list[str] = []
    for path, profile, _, _ in entries:
        slug = path.stem
        title = profile.get("title", slug)
        provider = profile.get("provider", "—")
        details = profile.get("model", {})
        pricing = profile.get("pricing", {})
        currency = pricing.get("currency", "USD")
        context = _format_tokens(details["context_window"]) if "context_window" in details else "—"
        inp = format_price(pricing["input_per_1m"], currency) if "input_per_1m" in pricing else "—"
        outp = format_price(pricing["output_per_1m"], currency) if "output_per_1m" in pricing else "—"

        cells = [
            f'<td><a href="{html.escape(slug)}.html">{html.escape(title)}</a></td>',
            f'<td>{html.escape(provider)}</td>',
            f'<td>{context}</td>',
            f'<td>{inp}</td>',
            f'<td>{outp}</td>',
        ]
        bench = profile.get("benchmarks") or {}
        for bk in bench_cols:
            v = bench.get(bk)
            cells.append(
                f'<td>{v * 100:.1f}%</td>' if v is not None else '<td class="muted">—</td>'
            )
        rows.append('<tr>' + "".join(cells) + '</tr>')

    return (
        '<section class="section">\n'
        '  <div class="container">\n'
        '    <h2>Models</h2>\n'
        '    <p class="muted">Sortable directory of every AI-model entity '
        'in the wiki. Click a model name to see its full page with inline '
        'info-card. Schema lives in <code>llmwiki/schema.py</code>.</p>\n'
        '    <div class="models-table-wrap">\n'
        '      <table class="models-table sortable">\n'
        '        <thead><tr>' + "".join(header) + '</tr></thead>\n'
        '        <tbody>\n'
        '          ' + "\n          ".join(rows) + '\n'
        '        </tbody>\n'
        '      </table>\n'
        '    </div>\n'
        '  </div>\n'
        '</section>\n'
    )
