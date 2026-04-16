# Obsidian Templater Templates

Four templates for creating wiki pages from inside Obsidian using the
[Templater](https://silentvoid13.github.io/Templater/) plugin.

## Templates

| File | Creates |
|------|---------|
| `source-template.md` | `wiki/sources/<slug>.md` — one page per raw source |
| `entity-template.md` | `wiki/entities/<Name>.md` — people, orgs, tools, concepts, etc. |
| `concept-template.md` | `wiki/concepts/<Name>.md` — ideas, patterns, frameworks |
| `synthesis-template.md` | `wiki/syntheses/<slug>.md` — filed query answers |

All templates produce pages matching the exact format documented in
`CLAUDE.md` and `AGENTS.md`, plus Obsidian-native enhancements:

- Obsidian callouts (`> [!info]`) for helper notes
- Dataview inline queries on entity/concept pages (show citing sources)
- Templater prompts for interactive fields (title, slug, project, entity_type)
- Seeded confidence (0.5) + lifecycle (draft) + last_updated (today)

## Installation

1. Install the [Templater](https://silentvoid13.github.io/Templater/) Obsidian plugin.
2. Copy the 4 template files into your vault's templates folder
   (default: `_templates/` or whatever you configured in Templater settings).
3. Point Templater's "Template folder location" setting at that folder.
4. Use `Ctrl/Cmd+Shift+P → Templater: Create new note from template`.

## Tip

Bind `Ctrl/Cmd+Alt+N` to "Templater: Create new note from template"
for one-keystroke access.
