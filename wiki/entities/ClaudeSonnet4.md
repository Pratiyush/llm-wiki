---
title: "Claude Sonnet 4"
type: entity
tags: [ai-model, anthropic, claude, llm, frontier-model]
entity_kind: ai-model
provider: Anthropic
model: {"context_window": 200000, "max_output": 8192, "license": "proprietary", "released": "2026-03-18"}
pricing: {"input_per_1m": 3.00, "output_per_1m": 15.00, "cache_read_per_1m": 0.30, "currency": "USD", "effective": "2026-03-18"}
modalities: [text, vision]
benchmarks: {"gpqa_diamond": 0.725, "swe_bench": 0.619, "mmlu": 0.887, "livecodebench": 0.564, "aime_2025": 0.451}
changelog: [{"date": "2026-03-18", "event": "Launched — initial pricing", "field": "model.pricing.input_per_1m", "from": null, "to": 4.00}, {"date": "2026-04-02", "event": "Input pricing cut", "field": "model.pricing.input_per_1m", "from": 4.00, "to": 3.00}, {"date": "2026-04-05", "event": "Context window expanded", "field": "model.context_window", "from": 100000, "to": 200000}, {"date": "2026-04-08", "event": "SWE-bench score updated after v2 evaluation", "field": "benchmarks.swe_bench", "from": 0.582, "to": 0.619}]
last_updated: 2026-04-09
sources: []
confidence: 0.56
lifecycle: reviewed
entity_type: tool
cache_tier: L1
reader_shell: true
---

# Claude Sonnet 4

Anthropic's 2026 mid-tier frontier model. Successor to Claude Sonnet 3.5,
sits between Haiku (fast/cheap) and Opus (max-capability). Targets the
sweet spot of cost vs. reasoning quality for agentic workloads.

## Notable features

- **200K context window** — matches the earlier 3.x generation; Opus 4.x
  pushes further for research workloads but Sonnet 4 is the default for
  most product use cases.
- **Vision** — image input supported in the same endpoint as text.
- **Cache read at $0.30/1M** — 10× cheaper than input, so long-running
  sessions with heavy context reuse can drop effective per-request cost
  by an order of magnitude.

## Benchmarks

The numbers in the frontmatter come from Anthropic's launch announcement
on 2026-03-18. Update this page (and append a time-series row to the
`changelog` field from #56 once it lands) whenever Anthropic publishes
a new set.

## Connections

- [[Anthropic]] — the provider
- [[AgenticWorkloads]] — primary use case
- [[CachePricing]] — the 10× cache-read discount changes cost models
