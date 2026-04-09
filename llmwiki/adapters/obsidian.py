"""Obsidian vault adapter.

Reads .md files from an Obsidian vault and treats each as a source document.
Unlike the Claude Code / Codex CLI adapters which parse .jsonl transcripts,
this adapter reads plain markdown that the user has already written.

It skips Obsidian's own internal files (`.obsidian/`, trash, templates) and
the `_templates/` convention seen in some vaults.

Config (in `examples/sessions_config.json`):

    {
      "adapters": {
        "obsidian": {
          "vault_paths": ["~/Documents/Obsidian Vault"],
          "exclude_folders": [".obsidian", "Templates", "_templates", ".trash"],
          "min_content_chars": 50
        }
      }
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("obsidian")
class ObsidianAdapter(BaseAdapter):
    """Obsidian — reads .md files from an Obsidian vault"""

    SUPPORTED_SCHEMA_VERSIONS = ["1.x"]

    DEFAULT_VAULT_PATHS = [
        # macOS / Linux / Windows — common default vault locations
        Path.home() / "Documents" / "Obsidian Vault",
        Path.home() / "Obsidian",
        # Windows (%APPDATA%) — some installs create vaults here
        Path.home() / "AppData" / "Local" / "Obsidian" / "Vault",
    ]

    DEFAULT_EXCLUDE_FOLDERS = {
        ".obsidian",
        ".trash",
        "Templates",
        "_templates",
        "templates",
        ".git",
        "node_modules",
    }

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("adapters", {}).get("obsidian", {})
        paths = ad_cfg.get("vault_paths") or []
        self.vault_paths: list[Path] = (
            [Path(p).expanduser() for p in paths] if paths else self.DEFAULT_VAULT_PATHS
        )
        self.exclude_folders: set[str] = set(
            ad_cfg.get("exclude_folders", self.DEFAULT_EXCLUDE_FOLDERS)
        )
        self.min_content_chars: int = int(ad_cfg.get("min_content_chars", 50))

    # Override session_store_path so is_available() works.
    @property
    def session_store_path(self):  # type: ignore[override]
        return self.vault_paths

    @classmethod
    def is_available(cls) -> bool:
        for p in cls.DEFAULT_VAULT_PATHS:
            if Path(p).expanduser().exists():
                return True
        return False

    def discover_sessions(self) -> list[Path]:
        """Walk every configured vault and return all .md files, excluding known
        internal folders. Returns a sorted list."""
        out: list[Path] = []
        for vault in self.vault_paths:
            vault = Path(vault).expanduser()
            if not vault.exists():
                continue
            for md in vault.rglob("*.md"):
                rel = md.relative_to(vault)
                # Skip anything inside excluded folders
                if any(part in self.exclude_folders for part in rel.parts):
                    continue
                # Skip empty or near-empty files
                try:
                    size = md.stat().st_size
                except OSError:
                    continue
                if size < self.min_content_chars:
                    continue
                out.append(md)
        return sorted(out)

    def derive_project_slug(self, md_path: Path) -> str:
        """Use the top-level folder under the vault as the project slug.
        Files directly in the vault root get slug 'vault-root'."""
        for vault in self.vault_paths:
            vault = Path(vault).expanduser()
            try:
                rel = md_path.relative_to(vault)
                if len(rel.parts) > 1:
                    # Use the first directory as the project slug, lowercased
                    return str(rel.parts[0]).lower().replace(" ", "-")
                return "vault-root"
            except ValueError:
                continue
        return md_path.parent.name

    def is_subagent(self, md_path: Path) -> bool:
        return False  # Obsidian notes are never subagents
