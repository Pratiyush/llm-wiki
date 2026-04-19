# Reader API contract (v1.2+ preview)

> Status: **contract-only**. No server yet — today the static site is the
> API. This doc locks the shape so when we add a hosted / SPA reader we
> don't have to rewrite the content model. Freezing this now protects
> the build pipeline (`site/` outputs) and the sibling `.txt` / `.json`
> files from drift (#116).

## Why a contract first

llmwiki is, and will stay, **static-site-first**. But a few near-term
bets depend on the data being reachable without HTML parsing:

- A browser extension that answers "what do I know about X" from the
  wiki's `.json` sibling of the current tab.
- A Raycast/Alfred plugin that hits `manifest.json` + `search-index.json`
  to open a page.
- A future lightweight SPA reader that can live on the same origin as
  the generated site.
- Downstream LLM agents consuming `llms-full.txt` + per-page `.json` to
  answer questions without pulling HTML.

Every one of those wants the same shape of data. This doc says what that
shape is, so refactors of `llmwiki/build.py` can't silently break
clients.

## Shipped today (v1.0+) — read-only, file-based

The static build writes these to `site/` on every `llmwiki build`:

| Path | Shape | Purpose |
|---|---|---|
| `/index.html` | HTML | Home page |
| `/<group>/index.html` | HTML | Project / sessions / models / vs index |
| `/<group>/<slug>.html` | HTML | Individual page |
| `/<group>/<slug>.txt` | Plain text | HTML-free body + first-line frontmatter |
| `/<group>/<slug>.json` | JSON | Structured metadata + body + outbound wikilinks |
| `/llms.txt` | Markdown | Short AI-agent index ([llmstxt.org spec](https://llmstxt.org)) |
| `/llms-full.txt` | Plain text | Flattened dump (≤ 5 MB) |
| `/graph.jsonld` | JSON-LD | Schema.org entity/concept/source graph |
| `/graph.html` | HTML | Interactive vis-network graph (#118) |
| `/search-index.json` | JSON | Top-level search index + facets + chunk manifest |
| `/search-chunks/<project>.json` | JSON | Per-project search chunk (lazy-loaded) |
| `/manifest.json` | JSON | Every file + SHA-256 + performance budget |
| `/sitemap.xml` | XML | Standard sitemap with `lastmod` |
| `/rss.xml` | XML | RSS 2.0 feed of newest sessions |
| `/robots.txt` | Text | AI-friendly, references `llms.txt` |
| `/ai-readme.md` | Markdown | AI-agent navigation instructions |

These are already the API. Everything below in this doc describes the
**future hosted/SPA surface** that will be fed by the same data shapes —
no new content pipeline, just new transports.

---

## Future endpoint contract

Every endpoint below maps 1:1 to a file that `llmwiki build` already
produces. The server is a thin JSON wrapper; the content model is what's
already on disk.

Base URL: `<root>/api/v1` (TBD — static deploy keeps `/api/v1/*.json` as
files).

### `GET /api/v1/bootstrap`

One-shot payload the reader fetches on first load so it doesn't have to
chain three requests before showing anything.

```json
{
  "version": "1.1.0rc2",
  "generated_at": "2026-04-19T08:34:42Z",
  "stats": {
    "sessions": 647,
    "projects": 30,
    "entities": 2,
    "concepts": 0,
    "total_bytes": 62691698
  },
  "nav": [
    { "id": "home",          "label": "Home",      "href": "/" },
    { "id": "projects",      "label": "Projects",  "href": "/projects/" },
    { "id": "sessions",      "label": "Sessions",  "href": "/sessions/" },
    { "id": "models",        "label": "Models",    "href": "/models/" },
    { "id": "vs",            "label": "Compare",   "href": "/vs/" },
    { "id": "graph",         "label": "Graph",     "href": "/graph.html" },
    { "id": "changelog",     "label": "Changelog", "href": "/changelog.html" }
  ],
  "theme": {
    "accent":  "#7C3AED",
    "default": "dark"
  },
  "search": {
    "mode":   "flat",
    "chunks": "/search-chunks/",
    "index":  "/search-index.json"
  },
  "cache_tiers": ["L1", "L2", "L3", "L4"]
}
```

**Client contract.** Safe to cache for 5 minutes. Never returns partial
data — if the site rebuilds mid-request, the server serves the previous
full payload until the new one is ready.

### `GET /api/v1/article?path=<url>`

The article shell already rendered as structured data — lets a SPA skip
HTML parsing entirely.

```json
{
  "url":   "sessions/llm-wiki/2026-04-17T10-12-llm-wiki-refactor.html",
  "slug":  "2026-04-17T10-12-llm-wiki-refactor",
  "title": "LLM Wiki refactor",
  "type":  "source",
  "project": "llm-wiki",
  "model": "claude-sonnet-4-6",
  "date": "2026-04-17",
  "last_updated": "2026-04-17",
  "confidence": 0.75,
  "lifecycle": "reviewed",
  "cache_tier": "L3",
  "entity_type": null,
  "tags": ["claude-code", "refactor"],
  "breadcrumbs": [
    { "label": "Home",     "href": "/" },
    { "label": "Projects", "href": "/projects/" },
    { "label": "llm-wiki", "href": "/projects/llm-wiki.html" },
    { "label": "LLM Wiki refactor" }
  ],
  "body_html": "<article>…</article>",
  "body_text": "Raw markdown body without frontmatter, suitable for LLM context.",
  "wikilinks_out": ["Obsidian", "Karpathy"],
  "wikilinks_in":  ["llm-wiki", "AndrejKarpathy"],
  "related": [
    { "slug": "2026-04-16T18-30-llm-wiki-seed", "title": "LLM Wiki seed", "score": 0.82 }
  ],
  "reading_time_minutes": 4,
  "summary": "First-paragraph summary for L2 pre-loading."
}
```

**Required fields:** `url`, `slug`, `title`, `type`, `body_html`,
`body_text`, `wikilinks_out`. Everything else is optional and may be
null/missing.

**Client contract.** The reader MUST gracefully render when optional
fields are missing (a newly ingested page may not have `confidence` or
`cache_tier` yet).

### `GET /api/v1/search?q=<query>&type=<optional>&project=<optional>`

Thin wrapper over the existing client-side index + chunks. Returns the
matches the palette would surface.

```json
{
  "query": "karpathy",
  "mode":  "flat",
  "total": 12,
  "hits": [
    {
      "id":    "session:llm-wiki/2026-04-16T18-30-llm-wiki-seed",
      "url":   "sessions/llm-wiki/2026-04-16T18-30-llm-wiki-seed.html",
      "title": "LLM Wiki seed",
      "type":  "source",
      "project": "llm-wiki",
      "snippet": "Karpathy's pattern spells out what…",
      "score":   0.91,
      "headings": [
        { "depth": 2, "text": "Summary" },
        { "depth": 3, "text": "Karpathy's pattern" }
      ]
    }
  ],
  "facets": {
    "entity_type": { },
    "lifecycle":   { },
    "tags":        { },
    "confidence":  { "none": 647 }
  }
}
```

**Mode.** `"flat"` vs `"tree"` — the client-side router today picks the
mode by heuristic (#53 lands the auto-router). The server MUST return
the same mode it used so the client can tell the user in the palette
footer.

**Client contract.** `hits` is capped at 100; the client does its own
pagination. `score` is 0–1 but not calibrated — use for ranking, not
thresholds.

### `POST /api/v1/sync` (internal only)

Trigger a rebuild without waiting for the next watcher tick. Used by
`/wiki-sync` after a successful ingest.

```http
POST /api/v1/sync
Authorization: Bearer <local-token>

{
  "reason": "ingest",
  "pages_changed": ["sources/llm-wiki-refactor.md"]
}
```

Response:
```json
{
  "accepted": true,
  "build_id": "2026-04-19T10:22:01Z",
  "eta_seconds": 2
}
```

**Auth.** Local bearer token only — this endpoint is never exposed to
the public internet. `manifest.json` is the read-side proof that the
build finished (its `generated_at` advances).

---

## Data model invariants

Anything a client can depend on:

1. **Slugs are stable.** A page's slug is set at ingest and never
   changes on rebuild. Renames produce a new slug and a redirect stub.
2. **Timestamps are UTC ISO-8601 with `Z` suffix.** Never local time.
3. **`cache_tier` is always one of `L1`, `L2`, `L3`, `L4`** (#52).
   Missing = treat as `L3`.
4. **`lifecycle` is always one of** `draft`, `reviewed`, `verified`,
   `stale`, `archived` (#11).
5. **`confidence` is always in `[0, 1]`** or missing. Never percent.
6. **`entity_type` (when set) is one of** `person`, `org`, `tool`,
   `concept`, `api`, `library`, `project` (#137).
7. **Wikilinks resolve to slugs, not URLs.** `[[Karpathy]]` → `"Karpathy"`
   — the client resolves to a URL via the index.
8. **Frontmatter is authoritative** for metadata. The body is authoritative
   for prose.

## Versioning

- `/api/v1/*` is the long-term contract. Breaking changes bump to `/v2/`
  and keep `/v1/` live for one minor version.
- Additive-only changes (new optional fields, new top-level keys on
  `bootstrap`) don't bump the version.
- Rename of an existing required field **is** a breaking change.

## Content negotiation

Today's static site already does this implicitly:

- `curl .../page.html`  → HTML
- `curl .../page.txt`   → plain text
- `curl .../page.json`  → structured

The future server will keep those three paths **exactly as-is**.
`Accept: application/json` on `.html` routes should redirect to
the `.json` sibling rather than serving JSON on the HTML URL —
that way caches and proxies stay simple.

---

## Migration path — static → hosted

1. **Today:** `llmwiki build` writes the JSON/txt files. External tools
   read them directly. (Done — #116 is this doc.)
2. **v1.2:** Add a tiny `llmwiki serve --api` flag that wraps the same
   files behind `/api/v1/*` paths so the reader SPA can fetch them
   uniformly in dev. No new data, just routing.
3. **v1.3+:** If a hosted multi-tenant reader ships, the server reuses
   the same routes with per-user auth. The content pipeline doesn't
   change.

At no point does the contract require a rewrite of `llmwiki/build.py` —
every endpoint maps to something build.py already emits.

## Related

- `llmwiki/build.py` — produces every file referenced above
- `llmwiki/exporters.py` — `llms.txt` + JSON-LD + per-page siblings
- `docs/reference/cache-tiers.md` — `cache_tier` invariant (#52)
- `docs/design/brand-system.md` — theme tokens returned by `/bootstrap`
- `#116` — this issue
- `#112` — reader-first article shell (one client of this contract)
