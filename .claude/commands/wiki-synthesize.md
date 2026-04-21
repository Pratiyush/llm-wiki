Synthesize `wiki/sources/<slug>.md` pages from raw session transcripts using the configured LLM backend.

Wraps: `python3 -m llmwiki synthesize`

Usage: `/wiki-synthesize` or any natural-language variant. Claude
translates the phrasing into flags.

## Natural-language → flags

| You say | Runs |
|---|---|
| "just show me what it would cost" | `python3 -m llmwiki synthesize --estimate` |
| "preview without writing" | `python3 -m llmwiki synthesize --dry-run` |
| "check the backend is reachable" | `python3 -m llmwiki synthesize --check` |
| "force re-synthesize everything" | `python3 -m llmwiki synthesize --force` |
| "synthesize but don't touch my wiki yet" | `python3 -m llmwiki synthesize --dry-run` |
| "list pending agent prompts" / "what's waiting on me?" | `python3 -m llmwiki synthesize --list-pending` |
| "complete pending synthesis \<uuid\>" | `python3 -m llmwiki synthesize --complete <uuid> --page <path>` (body via `--body` or stdin) |

## Expected output

First run on a fresh corpus (dummy backend):

```
Backend: DummySynthesizer
Scanned 785, new 785, synthesized 785, skipped 0
  synthesized: proj-a → 2026-04-17-slug-1
  …
```

Re-run on unchanged tree:

```
Backend: DummySynthesizer
Scanned 785, new 0, synthesized 0, skipped 0
```

## When to use

- After `/wiki-sync` produces new `raw/sessions/*.md` files and you
  want their `wiki/sources/*.md` counterparts immediately.
- After updating the prompt template under `wiki/prompts/source_page.md`
  — pair with `--force` to re-synthesize everything using the new prompt.
- After switching synthesis backends (`dummy` → `ollama` → api).

## Related

- [Tutorial 08 — Synthesize with Ollama](../../docs/tutorials/08-synthesize-with-ollama.md)
- `/wiki-build` — regenerates the static site after synthesize.
- `/wiki-lint` — finds pages with empty tags / broken wikilinks after synthesize.
- #50 (prompt-cache scaffold) · #315 (Claude API backend, in progress)
