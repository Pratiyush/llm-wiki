---
title: "Cross-Session Memory"
type: navigation
last_updated: 2026-04-16
max_lines: 200
---

# MEMORY — Cross-Session State

*200-line cap. Auto-consolidated by Auto Dream (24h + 5 sessions).*
*Treat as context hints, not absolute facts — verify against current code.*

## User

- Pratiyush Kumar Singh (macOS, git author `Pratiyush`, email pratiyush1@gmail.com)
- Uses structured workflow: rough notes → requirements → design → tasks → small PRs → MVP
- Prefers per-project CLAUDE.md over global home-dir CLAUDE.md
- Cancels writes they don't want — multi-stage approval required

## Feedback

- Always use verified (GPG-signed) commits
- No Co-authored-by headers — committer is always Pratiyush
- Every PR needs a checklist for user to verify before merge
- CHANGELOG + Release Notes updated with every PR
- Always write tests for new features

## Project

- llm-wiki v0.9.0 → targeting v1.0.0 with full Obsidian integration
- 35 GitHub issues created (#131-#165) across 4 sprints
- Obsidian vault symlinked at ~/Documents/Obsidian Vault/LLM Wiki/
- Claude Code MCP config lives in ~/.claude/.mcp.json (NOT settings.json)
- Global Node/npm/Homebrew missing — drove choice of obsidian-mcp-tools (bundles binary)

## Reference

- LLM Book design docs: ~/Documents/Obsidian Vault/01 - Ideas/Open Source/LLM Book/
- 12 design docs (2,799 lines) covering architecture through benchmarks
- Karpathy LLM Wiki gist: 5,000+ stars, 3,600+ forks (April 2026)
- kepano/obsidian-skills: 23,900 stars — reference skill format
