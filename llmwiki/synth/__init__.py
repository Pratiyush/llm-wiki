"""Synthesis engine — auto-generate wiki pages from raw sessions (v0.5 · #36).

This package provides the pipeline wiring for auto-ingesting newly-synced
sessions into the wiki layer. The actual LLM calls are abstracted behind a
`BaseSynthesizer` interface so any backend (Claude API, Ollama, or a test
dummy) can drive the generation.

Components:
- `base.py` — `BaseSynthesizer` ABC + `DummySynthesizer` for testing
- `prompts/source_page.md` — the prompt template (user-overridable)
- `pipeline.py` — the `synthesize_new_sessions()` orchestrator

The entry point is `llmwiki sync --synthesize` or `llmwiki synthesize`.
"""
