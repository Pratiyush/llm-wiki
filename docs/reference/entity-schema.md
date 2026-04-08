# Entity schema reference (v0.7 · #55)

The wiki's entity pages are free-form markdown by default — a file
like `wiki/entities/OpenAI.md` can be whatever you want, and the
slash-command workflow just edits the body. **AI model entities**
are a special case: they carry structured frontmatter so llmwiki can
render a sortable `/models/` index, inline info-cards, and future
comparison pages (#58).

This reference describes the schema. It's opt-in — any entity page
that doesn't set `entity_kind: ai-model` is ignored by the model
pipeline and continues to render as normal markdown.

## Minimum viable model page

```yaml
---
title: "Claude Sonnet 4"
type: entity
entity_kind: ai-model
provider: Anthropic
---

Free-form markdown body here.
```

With just this, the page will appear in the `/models/` table with an
em-dash in every numeric column. Add the structured blocks below to
populate them.

## Full schema

```yaml
---
title: "Claude Sonnet 4"
type: entity
entity_kind: ai-model
provider: Anthropic

# Nested blocks are written as inline JSON so llmwiki's lightweight
# frontmatter parser can store them without a full YAML library. The
# schema validator parses them back out at build time.
model: {"context_window": 200000, "max_output": 8192, "license": "proprietary", "released": "2026-03-18"}
pricing: {"input_per_1m": 3.00, "output_per_1m": 15.00, "cache_read_per_1m": 0.30, "currency": "USD", "effective": "2026-03-18"}
modalities: [text, vision]
benchmarks: {"gpqa_diamond": 0.725, "swe_bench": 0.619, "mmlu": 0.887}
---
```

### `model` block

| Key              | Type    | Notes                                              |
|------------------|---------|----------------------------------------------------|
| `context_window` | int     | Max input context, tokens. Must be > 0.           |
| `max_output`     | int     | Max single-response output tokens.                 |
| `license`        | string  | `"proprietary"`, `"apache-2.0"`, `"mit"`, etc.    |
| `released`       | ISO date| `YYYY-MM-DD`                                       |

### `pricing` block

| Key                    | Type  | Notes                                           |
|------------------------|-------|-------------------------------------------------|
| `input_per_1m`         | float | USD per 1M input tokens. Must be ≥ 0.          |
| `output_per_1m`        | float | USD per 1M output tokens.                       |
| `cache_read_per_1m`    | float | Discounted price for cached context reads.     |
| `cache_write_per_1m`   | float | Price for writing to the prompt cache.         |
| `currency`             | string| `"USD"`, `"EUR"`, `"GBP"`, ...                 |
| `effective`            | ISO date | When this pricing took effect.              |

### `modalities`

Plain YAML list. Common values: `text`, `vision`, `audio`, `video`,
`function-calling`, `tool-use`.

### `benchmarks` block

Benchmark scores as **fractions in [0, 1]** (0.725 = 72.5%). The
validator rejects values outside that range with a warning — don't
paste raw percentages.

Known keys get pretty labels automatically:

| Key                 | Label              |
|---------------------|--------------------|
| `gpqa_diamond`      | GPQA Diamond       |
| `swe_bench`         | SWE-bench          |
| `swe_bench_verified`| SWE-bench Verified |
| `aime_2025`         | AIME 2025          |
| `livecodebench`     | LiveCodeBench      |
| `arc_agi_2`         | ARC-AGI 2          |
| `mmlu`              | MMLU               |
| `mmlu_pro`          | MMLU-Pro           |
| `humaneval`         | HumanEval          |
| `hellaswag`         | HellaSwag          |
| `drop`              | DROP               |
| `bbh`               | BIG-Bench Hard     |
| `math_500`          | MATH-500           |

**Unknown keys pass through.** You can add `my_new_bench_2027: 0.42`
and it will render with a titlecased label without requiring a code
change.

## What the build pipeline does

1. `discover_model_entities(wiki/entities/)` walks the directory and
   picks out any page where `entity_kind == "ai-model"`.
2. `parse_model_profile(meta)` validates each page's frontmatter
   against the schema, returning a `ModelProfile` TypedDict plus a
   list of warnings. Warnings are surfaced in a collapsible
   `<details>` block on the detail page — they don't block the build.
3. `render_model_info_card(profile)` inlines a structured card at the
   top of each detail page, above the free-form body.
4. `render_models_index(entries)` emits the sortable `/models/index.html`
   table with every benchmark key used anywhere as a column.
5. The nav bar gains a `Models` link so readers can jump there from
   any page.

## Example

See [`wiki/entities/ClaudeSonnet4.md`](../../wiki/entities/ClaudeSonnet4.md)
for a complete real-world page.
