# examples/scripts

Stdlib-only Python recipes that consume the artefacts `llmwiki build` emits.

Each script is fully self-contained — no third-party deps, no llmwiki import — so you can copy one into your own project as a starting point for whatever aggregation you need.

## Scripts

| File | Reads | Prints |
|---|---|---|
| `tree_from_graph.py` | `site/graph.jsonld` | A `tree`-style ASCII view of every project and its sessions, sorted by session count then date. |

## Run

```bash
# from the repo root, after `llmwiki build`
python3 examples/scripts/tree_from_graph.py
```

The default input path is `site/graph.jsonld`; pass an explicit path to read from elsewhere:

```bash
python3 examples/scripts/tree_from_graph.py path/to/graph.jsonld
```

## Why these exist

`site/graph.jsonld` is one of the AI-consumable exports the static site ships alongside the HTML. The shape is JSON-LD with `@graph` flat structure (root → projects → sessions). These scripts illustrate the access pattern so you can write your own — count sessions per model, list every entity that appears in 3+ sessions, slice by date range, etc.
