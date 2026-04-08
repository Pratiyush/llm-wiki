"""Structured entity schema (v0.7 · closes #55).

Optional frontmatter schema for entity pages so llmwiki can render
queryable info-cards and a sortable `/models/` index. The schema is
opt-in — pages without `entity_kind: ai-model` are unaffected.

Design choices:

* **Stdlib-only validation** — we don't pull in pydantic. Validation
  is a plain function returning `(valid_profile, warnings)`. Bad data
  degrades to warnings logged at build time, never crashes the build.
* **Inline JSON for nested fields** — the existing frontmatter parser
  stores string values; the `model`, `pricing`, and `benchmarks` blocks
  are written as inline JSON (same pattern as `tool_counts` from #63).
  Consumers call `parse_model_profile()` to get a typed dict back.
* **Forward-compatible benchmark keys** — known keys get nice labels
  in the UI; unknown keys pass through as-is so users can add new
  benchmarks without waiting for a release.

Schema (frontmatter):

```yaml
---
title: "Claude Sonnet 4"
type: entity
entity_kind: ai-model
provider: Anthropic
model: {"context_window": 200000, "license": "proprietary", "released": "2026-03-18"}
pricing: {"input_per_1m": 3.00, "output_per_1m": 15.00, "currency": "USD", "effective": "2026-01-15"}
modalities: [text, vision]
benchmarks: {"gpqa_diamond": 0.725, "swe_bench": 0.619, "mmlu": 0.887}
---
```
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional, TypedDict

ENTITY_KIND_AI_MODEL = "ai-model"

# Known benchmark keys get pretty labels in the UI. Unknown keys pass
# through verbatim (forward-compatible).
KNOWN_BENCHMARKS: dict[str, str] = {
    # Frontier benchmarks (2025-2026)
    "gpqa_diamond": "GPQA Diamond",
    "swe_bench": "SWE-bench",
    "swe_bench_verified": "SWE-bench Verified",
    "aime_2025": "AIME 2025",
    "livecodebench": "LiveCodeBench",
    "arc_agi_2": "ARC-AGI 2",
    # Mid-tier
    "mmlu": "MMLU",
    "mmlu_pro": "MMLU-Pro",
    "humaneval": "HumanEval",
    "hellaswag": "HellaSwag",
    "drop": "DROP",
    "bbh": "BIG-Bench Hard",
    "math_500": "MATH-500",
}


class PricingProfile(TypedDict, total=False):
    input_per_1m: float
    output_per_1m: float
    cache_read_per_1m: float
    cache_write_per_1m: float
    currency: str
    effective: str  # ISO date


class ModelDetails(TypedDict, total=False):
    context_window: int
    max_output: int
    license: str
    released: str  # ISO date


class ModelProfile(TypedDict, total=False):
    """The full structured profile for an `ai-model` entity page."""
    title: str
    provider: str
    model: ModelDetails
    pricing: PricingProfile
    modalities: list[str]
    benchmarks: dict[str, float]


# ─── validation ─────────────────────────────────────────────────────────


def _try_parse_json(value: Any) -> Any:
    """If `value` is a JSON-string dict/list, parse it. Otherwise return as-is."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return json.loads(stripped)
            except (ValueError, json.JSONDecodeError):
                return value
    return value


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_model_entity(meta: Mapping[str, Any]) -> bool:
    """True if this page is an AI-model entity page (has
    `type: entity` + `entity_kind: ai-model`)."""
    return (
        str(meta.get("type", "")).strip() == "entity"
        and str(meta.get("entity_kind", "")).strip() == ENTITY_KIND_AI_MODEL
    )


def parse_model_profile(
    meta: Mapping[str, Any],
) -> tuple[ModelProfile, list[str]]:
    """Parse + validate a page's model frontmatter.

    Returns `(profile, warnings)`. `profile` always contains whatever
    fields were parseable, even if the input was partial. `warnings`
    contains human-readable messages for any field that failed
    validation — the caller logs them and keeps building.
    """
    warnings: list[str] = []
    profile: ModelProfile = {}

    title = meta.get("title")
    if title:
        profile["title"] = str(title)

    provider = meta.get("provider")
    if provider:
        profile["provider"] = str(provider)

    # Nested blocks are inline JSON in the frontmatter
    model_block = _try_parse_json(meta.get("model"))
    if isinstance(model_block, dict):
        details: ModelDetails = {}
        cw = _coerce_int(model_block.get("context_window"))
        if cw is not None and cw > 0:
            details["context_window"] = cw
        elif model_block.get("context_window") is not None:
            warnings.append("model.context_window must be a positive integer")

        mo = _coerce_int(model_block.get("max_output"))
        if mo is not None and mo > 0:
            details["max_output"] = mo
        elif model_block.get("max_output") is not None:
            warnings.append("model.max_output must be a positive integer")

        for k in ("license", "released"):
            v = model_block.get(k)
            if v:
                details[k] = str(v)  # type: ignore[literal-required]

        if details:
            profile["model"] = details
    elif model_block:
        warnings.append("model block must be a JSON object")

    pricing_block = _try_parse_json(meta.get("pricing"))
    if isinstance(pricing_block, dict):
        pricing: PricingProfile = {}
        for k in ("input_per_1m", "output_per_1m",
                  "cache_read_per_1m", "cache_write_per_1m"):
            v = pricing_block.get(k)
            if v is None:
                continue
            f = _coerce_float(v)
            if f is None or f < 0:
                warnings.append(f"pricing.{k} must be a non-negative number")
                continue
            pricing[k] = f  # type: ignore[literal-required]
        if pricing_block.get("currency"):
            pricing["currency"] = str(pricing_block["currency"])
        if pricing_block.get("effective"):
            pricing["effective"] = str(pricing_block["effective"])
        if pricing:
            profile["pricing"] = pricing
    elif pricing_block:
        warnings.append("pricing block must be a JSON object")

    modalities = meta.get("modalities")
    if isinstance(modalities, list):
        profile["modalities"] = [str(m) for m in modalities if m]
    elif isinstance(modalities, str) and modalities:
        # Comma-separated fallback
        profile["modalities"] = [
            m.strip() for m in modalities.strip("[]").split(",") if m.strip()
        ]

    benchmarks_block = _try_parse_json(meta.get("benchmarks"))
    if isinstance(benchmarks_block, dict):
        benches: dict[str, float] = {}
        for k, v in benchmarks_block.items():
            f = _coerce_float(v)
            if f is None:
                warnings.append(f"benchmarks.{k} must be a number")
                continue
            if f < 0 or f > 1:
                warnings.append(
                    f"benchmarks.{k}={f} should be in [0, 1] (fraction, not percent)"
                )
                continue
            benches[str(k)] = f
        if benches:
            profile["benchmarks"] = benches
    elif benchmarks_block:
        warnings.append("benchmarks block must be a JSON object")

    return profile, warnings


def benchmark_label(key: str) -> str:
    """Return a human-readable label for a known benchmark key, or the
    raw key (with underscores → spaces + titlecased) for unknown ones."""
    if key in KNOWN_BENCHMARKS:
        return KNOWN_BENCHMARKS[key]
    return key.replace("_", " ").title()


def format_price(value: float, currency: str = "USD") -> str:
    """Format a per-1M-token price. Always 2 decimals, currency prefix."""
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    prefix = symbols.get(currency.upper(), f"{currency} ")
    return f"{prefix}{value:.2f}"
