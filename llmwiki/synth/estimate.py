"""Synthesize cost-estimate report — pulled out of cli.py (#arch-h8 / #611).

Pre-#611 ``synthesize_estimate_report`` lived inside ``cli.py``. The
function is non-trivial business logic (G-07 / #293 cost-model walk)
that belongs next to the rest of the synth pipeline.

The function is re-exported from ``llmwiki.cli`` so the existing
``from llmwiki.cli import synthesize_estimate_report`` import path keeps
working for any test or caller that reached for it.
"""

from __future__ import annotations

from typing import Any, Optional

from llmwiki import REPO_ROOT


def synthesize_estimate_report(
    *,
    raw_sessions: Optional[list[tuple[Any, dict, str]]] = None,
    state_keys: Optional[set[str]] = None,
    prefix_tokens: Optional[int] = None,
    output_tokens_per_call: int = 1000,
    model: Optional[str] = None,
) -> dict:
    """Compute the incremental vs full-force cost report (G-07 · #293).

    Returns a plain dict so the CLI can render it AND tests can inspect
    the numbers without parsing stdout. Keys:

    * ``corpus`` — total raw sessions discovered under ``raw/sessions/``
    * ``synthesized`` — count already synthesized (from state file)
    * ``new`` — ``corpus - synthesized``
    * ``incremental_usd`` — dollars to synthesize the ``new`` bucket
    * ``full_force_usd`` — dollars to re-synthesize the **whole** corpus
      with ``--force`` (one cache write + N-1 cache hits)
    * ``prefix_tokens`` — tokens in the stable CLAUDE.md + index.md +
      overview.md prefix
    * ``model`` — model id used for pricing
    * ``warnings`` — list of human-readable warnings (e.g. prefix too
      small to be cached)

    Any of the args can be injected for tests; the default reads from
    disk and is what the CLI invokes.
    """
    from llmwiki.cache import (
        DEFAULT_MODEL,
        estimate_cost,
        estimate_tokens,
        warn_prefix_too_small,
    )
    from llmwiki.synth.pipeline import RAW_SESSIONS as _RAW
    from llmwiki.synth.pipeline import _discover_raw_sessions, _load_state

    chosen_model = model or DEFAULT_MODEL
    warnings: list[str] = []

    if prefix_tokens is None:
        prefix_parts: list[str] = []
        for rel in ("CLAUDE.md", "wiki/index.md", "wiki/overview.md"):
            p = REPO_ROOT / rel
            if p.is_file():
                prefix_parts.append(p.read_text(encoding="utf-8"))
        prefix_tokens = estimate_tokens("\n".join(prefix_parts))
    prefix_warning = warn_prefix_too_small(prefix_tokens)
    if prefix_warning:
        warnings.append(prefix_warning)

    if raw_sessions is None:
        raw_sessions = _discover_raw_sessions()
    if state_keys is None:
        state_keys = set(_load_state().keys())

    corpus = len(raw_sessions)

    # The real synth state stores rel-paths under ``raw/sessions/``
    # (e.g. ``proj/2026-04-09-slug.md``). Match against those first;
    # fall back to bare filename + suffix-endswith for tests that
    # inject simpler keys. A session counts as "synthesized" if any
    # of those three keys already appears in state_keys.
    # #py-m10 (#596): single-pass walk. The previous version walked
    # raw_sessions twice — once to bucket new vs synthesised + collect
    # body strings, once via a list comprehension to materialise the
    # full-force body list — and then ran estimate_tokens(body) twice
    # on each new session inside _bucket_usd. On a 5k-corpus that's
    # 10k token-estimate calls + 2 full body materialisations in RAM.
    # The pass below computes per-session tokens once, accumulates
    # both bucket totals incrementally, and never holds more than one
    # body string at a time.
    synthed = 0
    new = 0
    incremental_usd = 0.0
    full_force_usd = 0.0
    incremental_first = True
    full_force_first = True

    def _add_to_bucket(fresh_tokens: int, first: bool) -> tuple[float, bool]:
        """Return (cost, was_first?). Cost-of-this-call uses cache_hit=
        not first, mirroring the old _bucket_usd semantics."""
        est = estimate_cost(
            cached_tokens=prefix_tokens,
            fresh_tokens=fresh_tokens,
            output_tokens=output_tokens_per_call,
            model=chosen_model,
            cache_hit=not first,
        )
        return est.usd, False  # second-and-later calls hit the cache

    for p, _meta, body in raw_sessions:
        keys_to_try: set[str] = set()
        name = getattr(p, "name", str(p))
        keys_to_try.add(name)
        if hasattr(p, "relative_to"):
            try:
                keys_to_try.add(str(p.relative_to(_RAW)))
            except (ValueError, AttributeError):
                pass
        keys_to_try.add(str(p))
        matched = bool(keys_to_try & state_keys) or any(
            isinstance(k, str) and k.endswith(name) for k in state_keys
        )
        body_tokens = estimate_tokens(body)
        # Full-force bucket: every session contributes regardless of state.
        ff_cost, full_force_first = _add_to_bucket(body_tokens, full_force_first)
        full_force_usd += ff_cost
        # Incremental bucket: only un-synthesised sessions contribute.
        if matched:
            synthed += 1
        else:
            new += 1
            inc_cost, incremental_first = _add_to_bucket(
                body_tokens, incremental_first
            )
            incremental_usd += inc_cost

    return {
        "corpus": corpus,
        "synthesized": synthed,
        "new": new,
        "incremental_usd": incremental_usd,
        "full_force_usd": full_force_usd,
        "prefix_tokens": prefix_tokens,
        "model": chosen_model,
        "warnings": warnings,
    }
