---
title: "GPT-5"
type: entity
tags: [ai-model, openai, gpt, llm, multimodal, frontier-model]
entity_kind: ai-model
provider: OpenAI
model: {"context_window": 128000, "max_output": 16384, "license": "proprietary", "released": "2026-02-14"}
pricing: {"input_per_1m": 5.00, "output_per_1m": 20.00, "currency": "USD", "effective": "2026-02-14"}
modalities: [text, vision, audio]
benchmarks: {"gpqa_diamond": 0.680, "swe_bench": 0.595, "mmlu": 0.875, "livecodebench": 0.521, "aime_2025": 0.419, "arc_agi_2": 0.164}
changelog: [{"date": "2026-02-14", "event": "GA launch", "field": "model.released", "from": null, "to": "2026-02-14"}, {"date": "2026-03-01", "event": "Vision + audio modalities added", "field": "modalities", "from": "[text]", "to": "[text, vision, audio]"}]
last_updated: 2026-04-09
sources: []
confidence: 0.56
lifecycle: reviewed
entity_type: tool
cache_tier: L2
---

# GPT-5

OpenAI's 2026 flagship multimodal model. Successor to GPT-4o. Shipped
with a 128K context window, text + vision + audio input modalities,
and a pricing structure that sits slightly above Claude Sonnet 4 on
input but comparable on output.

## Notable features

- **Multimodal from day one** — text, vision, and audio in a single
  endpoint.
- **16K output cap** — double the 8K output ceiling of most
  contemporaries; useful for long-form structured generation.
- **ARC-AGI 2 score** — 16.4%, the first major model to score
  meaningfully on the upgraded ARC-AGI benchmark (most models are in
  the low single digits).

## Connections

- [[OpenAI]] — the provider
- [[MultimodalModels]] — primary category
- [[ARC-AGI 2]] — novel benchmark
