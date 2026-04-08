"""llmwiki — LLM-powered knowledge base from Claude Code and Codex CLI sessions.

Follows Andrej Karpathy's LLM Wiki pattern:
    https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Public API:
    - llmwiki.cli.main()              — the command-line entry point
    - llmwiki.convert.convert_all()   — .jsonl → markdown
    - llmwiki.build.build_site()      — markdown → HTML
    - llmwiki.serve.serve_site()      — local HTTP server
    - llmwiki.adapters.REGISTRY       — adapter registry
"""

__version__ = "0.3.0"
__author__ = "Pratiyush"
__license__ = "MIT"

from pathlib import Path

# Repo root (llmwiki/ clone), resolved from this file's location.
REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parent
