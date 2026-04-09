# Demo Recording Guide

How to create demo GIFs and screen recordings for llm-wiki.

## Terminal recording with asciinema

### Install

```bash
# macOS
brew install asciinema

# pip
pip install asciinema
```

### Record the full workflow demo

Use the included script to record a polished 3-minute demo:

```bash
# Record
asciinema rec demo.cast --title "llm-wiki: Full Workflow" --cols 100 --rows 30

# Then run these commands in order:
```

### Suggested demo script (~3 min)

```bash
# 1. Show what's available (10s)
llmwiki --version
llmwiki adapters

# 2. Sync sessions from all agents (20s)
llmwiki sync

# 3. Build the static site (15s)
llmwiki build

# 4. Show what was generated (10s)
ls site/
ls site/sessions/ | head -10
wc -l site/llms.txt

# 5. Serve locally (5s)
llmwiki serve &

# 6. Show key features in terminal (30s)
# Count sessions per project
ls raw/sessions/ | while read p; do echo "$p: $(ls raw/sessions/$p/*.md 2>/dev/null | wc -l) sessions"; done

# Show model directory
ls wiki/entities/

# Show exports
cat site/llms.txt | head -20

# 7. Clean up
kill %1
```

### Convert to GIF

```bash
# Using agg (asciinema gif generator)
# Install: cargo install --git https://github.com/asciinema/agg
agg demo.cast demo.gif --cols 100 --rows 30 --speed 1.5

# Or upload to asciinema.org
asciinema upload demo.cast
```

### Convert to SVG (for README)

```bash
# Using svg-term-cli
npm install -g svg-term-cli
svg-term --in demo.cast --out demo.svg --window --width 100 --height 30
```

## Browser screen recording

For capturing the web UI (heatmap, charts, model pages):

### Using the built-in preview tools (Claude Code)

Screenshots are captured via `preview_start` + `preview_screenshot` at multiple viewports:

| Page | Desktop (1280x800) | Mobile (375x812) | Tablet (768x1024) |
|---|---|---|---|
| Home (heatmap + stats) | yes | yes | optional |
| Home (projects grid) | yes | - | - |
| Sessions index (filters) | yes | - | - |
| Session detail (tool chart) | yes | yes | - |
| Session detail (token card) | yes | - | - |
| Models directory | yes | - | - |
| Model detail (info card) | yes | - | - |
| Compare page (benchmarks) | yes | - | - |

### Manual recording (OBS / QuickTime)

1. Start the server: `llmwiki serve`
2. Open `http://localhost:8765` in browser
3. Record with OBS Studio or QuickTime Player
4. Suggested flow:
   - Home page (show heatmap, scroll to projects)
   - Click into a project
   - Click a session (show tool chart, token card)
   - Navigate to Models
   - Click a model (show info card)
   - Open compare page
   - Use Cmd+K search
   - Toggle theme
5. Export as MP4, then convert to GIF:
   ```bash
   ffmpeg -i recording.mp4 -vf "fps=10,scale=800:-1" -loop 0 demo.gif
   ```

## Screenshot inventory

Screenshots were captured on 2026-04-09 with 412 main sessions, 235 sub-agent runs, 30 projects across Claude Code, Codex CLI, Copilot Chat, Copilot CLI, Cursor, and Gemini CLI.

### Desktop (1280x800, dark mode)
1. **Home page** - Header with stats (412 sessions, 30 projects), 365-day activity heatmap, token stat cards (2.8B total, 101.6M avg, 99% best cache hit)
2. **Projects grid** - 2-column card layout with session counts per project
3. **Sessions index** - Activity timeline bar chart, filter bar (project, model, date range, slug)
4. **Session detail (header)** - CLAUDE badge, branch/model pills, tool chart (Bash 180, Write 150, Edit 64, Read 38, TodoWrite 31...)
5. **Session detail (token card)** - Token usage breakdown (423.9M total, 98% cache hit ratio)
6. **Models directory** - Sortable table with provider, context, pricing, benchmarks
7. **Model detail** - Info card (context, max output, license, released, modalities, pricing)
8. **Compare page** - Side-by-side benchmark bar charts, price delta, summary stub

### Mobile (375x812, dark mode)
1. **Home page** - Single-column layout, full-width heatmap, stacked stat cards
2. **Session detail** - Responsive header with wrapping metadata, breadcrumbs

### Light mode (desktop)
1. **Home page** - Same layout, light color scheme
