Apply labels + milestone + priority to a new issue using the llmwiki triage rules.

Usage: /triage-issue <issue-number>

This slash command loads `docs/maintainers/TRIAGE.md` and applies
the label taxonomy to the given issue. The goal is to give every
new issue a type, a priority, and a layer label within 24 hours —
not to fully resolve it.

## Workflow

1. **Fetch the issue** — `gh issue view <N>` for the title, body,
   author, current labels, and comment count. Note whether it's
   actually new or a re-surfaced old issue.

2. **Read the governance docs first** — load:
   - `docs/maintainers/TRIAGE.md` (label taxonomy + rules)
   - `docs/maintainers/ARCHITECTURE.md` (layer definitions)
   - `docs/maintainers/DECLINED.md` (check for prior rejection)
   - `docs/maintainers/ROADMAP.md` (current milestone themes)

3. **Check for duplicates** — before labeling, run:
   ```bash
   gh issue list --search "<keywords from title>" --state all --limit 20
   ```
   If it's a duplicate, close the new one with a comment linking to
   the original and stop. Don't apply labels to a duplicate.

4. **Check DECLINED.md** — if the idea has already been declined,
   close with a comment linking to the entry and ask the reporter
   what's changed since the decline. Don't silently close.

5. **Apply the required labels** — every issue gets exactly one of
   each category:
   - **Type**: `enhancement` / `bug` / `docs` / `chore` / `epic` /
     `question` / `wontfix`
   - **Priority**: `priority:must` / `priority:should` /
     `priority:could` / `priority:wont`
   - **Layer**: `layer-0` through `layer-7` (required for
     anything actionable; `question` and `epic` can skip)

6. **Assign a milestone** — for `priority:must` + `priority:should`
   items, assign the current release milestone from
   `docs/maintainers/ROADMAP.md`. `priority:could` items stay
   unmilestoned until a contributor picks them up.

7. **Post a triage comment** — use the template below.

8. **Append to log** — one line to `wiki/log.md`:

       ## [YYYY-MM-DD] triage | #<N>: <labels> → <milestone>

## Triage comment template

```markdown
Triaged by /triage-issue:

- **Type:** <enhancement | bug | docs | chore | epic | question>
- **Priority:** <must | should | could | wont>
- **Layer:** <layer-0 | layer-1 | ... | layer-7>
- **Milestone:** <v0.X.0 or "unmilestoned">

<!-- If wontfix or duplicate, link to the relevant doc / original -->

<!-- If this is a good-first-issue or help-wanted, mention it -->
```

## Escalation

Flag any of these to maintainer attention IMMEDIATELY — don't
wait for the regular triage pass:

- **Security vulnerability** → point the reporter to `SECURITY.md`
  and alert the maintainer directly. Do not discuss the details
  in a public issue comment.
- **User data loss** (e.g. a bad converter mangling `raw/` files)
  → label `priority:must` and `layer-0`, ping the maintainer.
- **CI red and staying red** → label `priority:must` and
  `layer-7`.
- **Contributor PR stuck > 7 days** → ping the maintainer in a
  comment (not a new issue) and unblock the review.
