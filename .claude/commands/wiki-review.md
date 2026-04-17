Review and triage candidate wiki pages — promote, merge, or discard.

Candidate pages live under `wiki/candidates/<kind>/<slug>.md` and were
created by `/wiki-ingest` for new entities/concepts the LLM detected. They
are **not** part of the trusted wiki layer until a human approves them.

Usage: `/wiki-review`

## Workflow

1. List all pending candidates:
   ```
   python3 -m llmwiki candidates list
   ```
   Or filter to stale (age > 30 days):
   ```
   python3 -m llmwiki candidates list --stale
   ```

2. For each candidate, decide:

   - **promote** — candidate is legitimate and not a duplicate.
     Moves it into the trusted tree (`wiki/entities/` or `wiki/concepts/`)
     and rewrites `status: candidate` → `status: reviewed`.
     ```
     python3 -m llmwiki candidates promote --slug MyEntity
     ```

   - **merge** — candidate is essentially a duplicate of an existing page.
     Appends the candidate's body under a `## Candidate merge — <date>`
     heading in the target page, then archives the candidate.
     ```
     python3 -m llmwiki candidates merge --slug DuplicateFoo --into Foo
     ```

   - **discard** — candidate is a hallucination or noise.
     Moves it to `wiki/archive/candidates/<timestamp>/` with a
     `.reason.txt` audit-trail file.
     ```
     python3 -m llmwiki candidates discard --slug BogusEntity \
       --reason "not a real company; LLM hallucinated"
     ```

3. After any promote/merge, run `/wiki-lint` to catch broken wikilinks
   from pages that used to point at the candidate location.

4. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] review | <N> promoted, <M> merged, <K> discarded
   ```

## Related

- #51 — the issue that added this workflow
- `/wiki-lint` — finds stale candidates (age > 30 days) automatically
- `/wiki-ingest` — routes new pages to `candidates/` instead of direct
