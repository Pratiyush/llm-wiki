Sync Claude Code (and Codex CLI) session transcripts into the llmwiki, then ingest the new ones into `wiki/`.

Usage: /wiki-sync [project-substring]

Steps (run in this order, report progress to the user):

1. **Convert new sessions to markdown** by running:
   ```bash
   python3 -m llmwiki sync $ARGUMENTS
   ```
   Capture the summary line (`N converted, M unchanged, K live, J filtered, X errors`).

2. **If `N == 0`**: report "wiki is already up to date" and continue to step 6 (pending-prompt scan). Don't run ingest.

3. **If `N > 0`**: for each newly written markdown file under `raw/sessions/`, follow the **Ingest Workflow** from `CLAUDE.md`. Process one project at a time. If there are more than 20 new files total, ask the user whether to process them all or a subset first.

4. **Append to `wiki/log.md`**:
   ```
   ## [YYYY-MM-DD] sync | <N> sessions across <M> projects
   ```

5. **Report** to the user:
   - How many sessions were converted
   - Which projects got updated
   - Which wiki pages were created or updated
   - Any contradictions flagged under `## Contradictions` on wiki pages

6. **Complete any pending agent-delegate syntheses (#316)** — the `agent` synthesis backend writes pending prompts to `.llmwiki-pending-prompts/<uuid>.md` that need you (the agent) to finalise. Run:

   ```bash
   python3 -m llmwiki synthesize --list-pending
   ```

   **If the output is "No pending prompts"**: skip to step 7.

   **Otherwise** — for each pending prompt:

   a. Read `.llmwiki-pending-prompts/<uuid>.md` — it contains the rendered prompt (body + frontmatter) that the pipeline already filled in.

   b. Synthesize the wiki page body by following the prompt instructions. Emit the `<!-- suggested-tags: ... -->` comment as the first line per the prompt.

   c. Write the synthesized body to a scratch file, then finalise:

      ```bash
      python3 -m llmwiki synthesize --complete <uuid> --page wiki/sources/<project>/<date>-<slug>.md --body /tmp/synth-<uuid>.md
      ```

   d. The CLI verifies the uuid matches the page's sentinel, rewrites the placeholder in place, and deletes `.llmwiki-pending-prompts/<uuid>.md`.

   Process all pending prompts serially — the agent is single-conversation.

7. **Done.** Run `/wiki-build` if the caller asked for fresh HTML.
