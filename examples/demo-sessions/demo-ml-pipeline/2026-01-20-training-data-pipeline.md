---
title: "Session: training-data-pipeline — 2026-01-20"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-01-20
source_file: raw/sessions/demo-ml-pipeline/2026-01-20-training-data-pipeline.md
sessionId: demo-000000000000000000000000000021
slug: training-data-pipeline
project: demo-ml-pipeline
started: 2026-01-20T09:15:00+00:00
ended: 2026-01-20T12:30:00+00:00
cwd: /Users/demo/code/demo-ml-pipeline
gitBranch: main
permissionMode: default
model: gpt-5.4
user_messages: 2
tool_calls: 5
tools_used: [Bash, Write]
tool_counts: {"Write": 4, "Bash": 1}
token_totals: {"input": 14000, "cache_creation": 22000, "cache_read": 52000, "output": 6400}
turn_count: 2
hour_buckets: {"2026-01-20T09": 8, "2026-01-20T10": 10, "2026-01-20T11": 4, "2026-01-20T12": 2}
duration_seconds: 11700
is_subagent: false
---

# Session: training-data-pipeline — 2026-01-20

**Project:** `demo-ml-pipeline` · **Branch:** `main` · **Mode:** `default` · **Model:** `claude-opus-4-6`

## Summary

Wrote a data-prep pipeline for a small text classification model. Loads Parquet from S3 (LocalStack in dev), deduplicates, tokenizes with the `tiktoken` `cl100k_base` encoder, and writes training shards in HuggingFace datasets format.

## Conversation

### Turn 1 — User

I need a data pipeline that takes our Parquet files and produces train/val shards suitable for a small BERT fine-tune.

### Turn 1 — Assistant

I'll structure it as four stages:

1. **Load** — `pyarrow.parquet.read_table` over an S3 prefix
2. **Dedupe** — exact-match hash on `(text, label)`
3. **Tokenize** — `tiktoken` `cl100k_base`; batch in chunks of 1024 for throughput
4. **Shard** — 80/20 stratified split, write via `datasets.Dataset.save_to_disk`

The stages will be composable so we can run any subset (e.g. just re-tokenize without re-loading).

### Turn 2 — User

Write it.

### Turn 2 — Assistant

Done. Each stage is a function in `pipeline/stages/`. There's a top-level `pipeline.run()` that reads a `config.yaml` and dispatches. Local test on 10k rows runs in 3.2s end to end.

**Tools used in this turn:**
- `Write`: `pipeline/stages/load.py` (5-line preview)
- `Write`: `pipeline/stages/dedupe.py` (5-line preview)
- `Write`: `pipeline/stages/tokenize.py` (5-line preview)
- `Write`: `pipeline/stages/shard.py` (5-line preview)
- `Bash`: `python -m pipeline --config configs/dev.yaml` — exit 0

## Connections

- [[demo-ml-pipeline]] — project
- [[tiktoken]] — library
- [[HuggingFaceDatasets]] — library
- [[DataPipeline]] — concept
