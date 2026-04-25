Run the full llmwiki pipeline end-to-end: build → graph → export all → lint.

Usage: /wiki-all [flags]

`$ARGUMENTS` is forwarded verbatim to `python3 -m llmwiki all`. Common flags:

- `--graph-engine builtin` — skip optional Graphify (use when `pip install llm-notebook[graph]` has not been run)
- `--skip-graph` — skip the graph step entirely
- `--strict` — exit non-zero if lint reports any errors/warnings (good for CI)
- `--fail-fast` — stop at the first non-zero step instead of continuing to the next
- `--out <dir>` — output directory (default: `site/`)

Run:

```bash
python3 -m llmwiki all $ARGUMENTS
```

The command runs these steps in order and surfaces their combined output:

1. **build** — compile the static HTML site from `raw/` + `wiki/`
2. **graph** — build the knowledge graph (`graph/graph.json` + interactive `graph.html`)
3. **export all** — write every AI-consumable format (`llms.txt`, `llms-full.txt`, `graph.jsonld`, `sitemap.xml`, `rss.xml`, `robots.txt`, `ai-readme.md`)
4. **lint** — run every registered lint rule against the wiki

Report to the user:

- Output directory and total file / size count from the build step
- Graph stats (pages · edges · broken · orphans)
- Which export files were written
- Lint summary (errors / warnings / info)
- Overall exit code — `0` means every step succeeded

If any step fails, surface the failing step's output and the pipeline exit code.

Use this instead of chaining `/wiki-build` + `/wiki-graph` + `/wiki-lint` manually.
It is the canonical one-shot "CI-ready site" command to run after `/wiki-sync`.
