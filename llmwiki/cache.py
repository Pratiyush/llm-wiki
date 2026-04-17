"""Prompt caching + batch-API scaffolding (v1.1.0 · #50).

Every `/wiki-sync` and `/wiki-ingest` bundles the same stable prefix —
CLAUDE.md schema, `wiki/index.md`, and `wiki/overview.md` — with every
source file it asks the model to summarize. On a 500-page wiki that
prefix is ≈30k tokens per request. sage-wiki reports 50–90% savings by
marking the prefix as ``cache_control: {type: "ephemeral"}`` so
Anthropic caches and re-uses it across calls.

This module provides **only the plumbing**: header construction, token
estimation, batch-state persistence. Actual Anthropic API calls land in
a follow-up PR (v1.2) once the scaffolding lands and is exercised by
the existing Ollama / Dummy backends for testing.

Public surface
--------------
- ``make_cached_block(text)`` — wrap a string as a cached content block
- ``CachedPrompt`` — dataclass holding stable prefix + dynamic suffix
- ``build_messages(prompt)`` — render a ``CachedPrompt`` into the
  Anthropic ``messages`` array with ``cache_control`` on the prefix
- ``estimate_tokens(text)`` — char/4 heuristic (fast, no tokenizer dep)
- ``estimate_cost(...)`` — dollar estimate using the published rate card
- ``BatchState`` — pending / completed ``message_batches`` IDs on disk
- ``load_batch_state`` / ``save_batch_state`` — JSON round-trip helpers
- ``MODEL_PRICING`` — published USD/MTok rates for the models we ship

Design notes
------------
- **Stdlib-only.** We don't import ``anthropic`` here — the scaffold
  runs anywhere. The real backend will depend on ``anthropic`` and
  re-use this module.
- **Estimate-first.** ``estimate_cost()`` lets ``llmwiki sync --estimate``
  print a cached-vs-fresh breakdown *before* spending money.
- **Batch state file.** ``.llmwiki-batch-state.json`` mirrors the shape
  of ``.llmwiki-synth-state.json``: small, line-oriented, easy to grep.
- **No implicit cache writes.** Cache-control lives on the block, not
  the request; inserting ``cache_control`` is always opt-in so tests
  can drive pure prefix-vs-suffix logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TypedDict

# ─── Constants ─────────────────────────────────────────────────────────

# Anthropic's ephemeral cache block shape.
CACHE_CONTROL_EPHEMERAL = {"type": "ephemeral"}

# Rough token estimator: Anthropic's own guidance is ~4 chars/token for
# English prose. Close enough for a cost preview; real counts come back
# in the API response usage block.
CHARS_PER_TOKEN = 4

# Minimum prefix size the Anthropic cache will accept. Below this the
# ``cache_control`` header is ignored and you pay the full input price.
# (Value per Anthropic docs; kept here so ``estimate_cost`` can warn
# when the prefix is too small to benefit.)
MIN_CACHEABLE_TOKENS = 1024


# ─── Pricing ───────────────────────────────────────────────────────────

class ModelRates(TypedDict):
    """Per-model USD rates per 1 M tokens."""

    input: float           # fresh (un-cached) input tokens
    cached_input: float    # cache-hit input tokens (usually 0.1x input)
    cache_write: float     # first-time cache-write premium (usually 1.25x input)
    output: float          # model output tokens


# Published USD / MTok rates (as of v1.1.0 · 2026-04). Kept inline so
# nothing requires a network round-trip to estimate cost.
MODEL_PRICING: dict[str, ModelRates] = {
    "claude-sonnet-4-6": {
        "input": 3.00,
        "cached_input": 0.30,
        "cache_write": 3.75,
        "output": 15.00,
    },
    "claude-haiku-4": {
        "input": 0.80,
        "cached_input": 0.08,
        "cache_write": 1.00,
        "output": 4.00,
    },
    "claude-opus-4": {
        "input": 15.00,
        "cached_input": 1.50,
        "cache_write": 18.75,
        "output": 75.00,
    },
}

DEFAULT_MODEL = "claude-sonnet-4-6"
BATCH_STATE_FILENAME = ".llmwiki-batch-state.json"


# ─── Cached block / message builders ──────────────────────────────────


class ContentBlock(TypedDict, total=False):
    """Anthropic message content block (subset we care about)."""

    type: str
    text: str
    cache_control: dict[str, str]


def make_cached_block(text: str) -> ContentBlock:
    """Return a ``text`` content block with ``cache_control: ephemeral``.

    The Anthropic cache header is placed on the *last* block you want
    cached — everything up to and including that block becomes a single
    cache key.
    """
    return {
        "type": "text",
        "text": text,
        "cache_control": dict(CACHE_CONTROL_EPHEMERAL),
    }


def make_plain_block(text: str) -> ContentBlock:
    """Return an un-cached ``text`` content block."""
    return {"type": "text", "text": text}


@dataclass(frozen=True)
class CachedPrompt:
    """A prompt split into a cacheable prefix and a dynamic suffix.

    ``stable_prefix`` is everything that's identical across source files
    (CLAUDE.md schema, current ``wiki/index.md``, current
    ``wiki/overview.md``). It gets the cache header.

    ``dynamic_suffix`` is the per-source content that changes every call
    (the session body, slug, date, project). It never carries cache_control.
    """

    stable_prefix: str
    dynamic_suffix: str
    system: Optional[str] = None

    def content_blocks(self) -> list[ContentBlock]:
        """Return the list of content blocks for the user message."""
        blocks: list[ContentBlock] = []
        if self.stable_prefix:
            blocks.append(make_cached_block(self.stable_prefix))
        if self.dynamic_suffix:
            blocks.append(make_plain_block(self.dynamic_suffix))
        return blocks


def build_messages(prompt: CachedPrompt) -> list[dict[str, Any]]:
    """Render a :class:`CachedPrompt` into Anthropic's ``messages`` list.

    Returns a single-message list; the real backend will pass it straight
    to ``client.messages.create(messages=..., system=...)``.
    """
    return [{"role": "user", "content": prompt.content_blocks()}]


# ─── Token + cost estimation ──────────────────────────────────────────


def estimate_tokens(text: str) -> int:
    """Rough token count via char/4 heuristic.

    Slightly under-counts emoji-heavy text and over-counts code-heavy
    text, but it's plenty accurate for a pre-spend sanity check. Real
    counts come back in ``usage`` on each API response.
    """
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


@dataclass(frozen=True)
class CostEstimate:
    """Dollar + token breakdown for a single Anthropic call."""

    model: str
    cached_tokens: int        # prefix (paid at cached_input rate on hit)
    fresh_tokens: int         # dynamic suffix (paid at input rate)
    output_tokens: int        # expected completion length
    cache_hit: bool           # True = re-use, False = first write
    usd: float                # total estimated dollars

    def breakdown(self) -> dict[str, float]:
        """Return per-bucket dollar amounts. Useful for ``--estimate``."""
        rates = MODEL_PRICING[self.model]
        prefix_rate = rates["cached_input"] if self.cache_hit else rates["cache_write"]
        return {
            "prefix_usd": self.cached_tokens * prefix_rate / 1_000_000,
            "fresh_usd": self.fresh_tokens * rates["input"] / 1_000_000,
            "output_usd": self.output_tokens * rates["output"] / 1_000_000,
        }


def estimate_cost(
    *,
    cached_tokens: int,
    fresh_tokens: int,
    output_tokens: int,
    model: str = DEFAULT_MODEL,
    cache_hit: bool = True,
) -> CostEstimate:
    """Price out one API call given token counts.

    Parameters
    ----------
    cached_tokens : int
        Tokens in the stable prefix.
    fresh_tokens : int
        Tokens in the per-source dynamic suffix.
    output_tokens : int
        Expected response length.
    model : str
        Model id from :data:`MODEL_PRICING`.
    cache_hit : bool
        ``True`` to assume the prefix is already in cache (cheap),
        ``False`` to price the first-write premium.
    """
    if model not in MODEL_PRICING:
        raise ValueError(f"unknown model {model!r}; see MODEL_PRICING")
    if cached_tokens < 0 or fresh_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be non-negative")

    rates = MODEL_PRICING[model]
    prefix_rate = rates["cached_input"] if cache_hit else rates["cache_write"]
    usd = (
        cached_tokens * prefix_rate
        + fresh_tokens * rates["input"]
        + output_tokens * rates["output"]
    ) / 1_000_000

    return CostEstimate(
        model=model,
        cached_tokens=cached_tokens,
        fresh_tokens=fresh_tokens,
        output_tokens=output_tokens,
        cache_hit=cache_hit,
        usd=usd,
    )


def format_estimate(est: CostEstimate) -> str:
    """Pretty-print a :class:`CostEstimate` for the ``--estimate`` flag."""
    bd = est.breakdown()
    hit_label = "cache hit" if est.cache_hit else "first write"
    return (
        f"Model: {est.model} ({hit_label})\n"
        f"  Prefix:  {est.cached_tokens:>7,} tok  ${bd['prefix_usd']:.4f}\n"
        f"  Fresh:   {est.fresh_tokens:>7,} tok  ${bd['fresh_usd']:.4f}\n"
        f"  Output:  {est.output_tokens:>7,} tok  ${bd['output_usd']:.4f}\n"
        f"  Total:                ${est.usd:.4f}"
    )


def warn_prefix_too_small(cached_tokens: int) -> Optional[str]:
    """Return a one-line warning if the prefix is below the cache floor.

    Anthropic silently ignores ``cache_control`` on prefixes below
    :data:`MIN_CACHEABLE_TOKENS` tokens, so ``--estimate`` should flag
    that the prefix isn't actually being cached.
    """
    if cached_tokens < MIN_CACHEABLE_TOKENS:
        return (
            f"prefix is {cached_tokens} tok (< {MIN_CACHEABLE_TOKENS} min) — "
            f"Anthropic will not cache it; savings estimate is best-case only."
        )
    return None


# ─── Batch state persistence ──────────────────────────────────────────


@dataclass
class BatchJob:
    """One Anthropic ``message_batches`` submission in flight."""

    batch_id: str
    source_slugs: list[str] = field(default_factory=list)
    submitted_at: str = ""  # ISO-8601
    status: str = "pending"  # pending | completed | expired | failed


@dataclass
class BatchState:
    """Persistent state for the batch ingest pipeline.

    Mirrors ``.llmwiki-synth-state.json`` in spirit: small JSON file at
    the repo root, safe to grep / ``cat`` to see what's in flight.
    """

    pending: list[BatchJob] = field(default_factory=list)
    completed: list[BatchJob] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "pending": [vars(b) for b in self.pending],
            "completed": [vars(b) for b in self.completed],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BatchState":
        return cls(
            pending=[BatchJob(**b) for b in data.get("pending", [])],
            completed=[BatchJob(**b) for b in data.get("completed", [])],
        )


def batch_state_path(repo_root: Path) -> Path:
    """Return the on-disk path for the batch state file."""
    return repo_root / BATCH_STATE_FILENAME


def load_batch_state(repo_root: Path) -> BatchState:
    """Load batch state from disk, or an empty state if the file is
    missing or corrupt (mirrors ``_load_state`` in ``synth/pipeline.py``)."""
    path = batch_state_path(repo_root)
    if not path.is_file():
        return BatchState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, json.JSONDecodeError):
        return BatchState()
    return BatchState.from_json(data)


def save_batch_state(repo_root: Path, state: BatchState) -> Path:
    """Write batch state to disk and return the path."""
    path = batch_state_path(repo_root)
    path.write_text(
        json.dumps(state.to_json(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def add_pending(state: BatchState, job: BatchJob) -> None:
    """Append a new pending job (dedup by batch_id)."""
    if any(b.batch_id == job.batch_id for b in state.pending):
        return
    state.pending.append(job)


def mark_completed(state: BatchState, batch_id: str, *, status: str = "completed") -> bool:
    """Move a pending job into the completed list. Returns True if
    the job was found and moved, False otherwise."""
    for i, job in enumerate(state.pending):
        if job.batch_id == batch_id:
            job.status = status
            state.completed.append(state.pending.pop(i))
            return True
    return False
