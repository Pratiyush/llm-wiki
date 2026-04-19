"""Vault-overlay mode — compile existing Obsidian / Logseq vaults in place (v1.2.0 · #54).

Users with established Obsidian or Logseq vaults shouldn't have to
migrate to a fresh ``raw/`` + ``wiki/`` tree. This module lets the rest
of the pipeline treat an existing vault directory as **both source and
output**:

- `llmwiki sync --vault <path>` writes new entity / concept / source
  pages *inside* the vault at user-configured subpaths.
- `llmwiki build --vault <path>` compiles a static site from the vault.
- Raw session transcripts still land in the repo-local ``raw/sessions/``
  (we don't pollute the user's notes with auto-generated transcripts).

Two formats are supported today; format detection is structural (no
config file required):

- **Obsidian** — vault has a ``.obsidian/`` directory. Wikilinks are
  bare slugs (``[[RAG]]``), pages live at arbitrary depth, title comes
  from filename.
- **Logseq** — vault has a ``logseq/`` directory *or* a ``config.edn``
  file. Wikilinks are namespace-aware (``[[Wiki/Tech/RAG]]``), pages
  live under ``pages/`` with either folder nesting or flat
  ``namespace___slug.md`` filenames.
- **Plain markdown** — neither marker exists. Treat as Obsidian-like
  but refuse destructive writes without ``--allow-overwrite`` for
  extra safety.

Non-destructive by default: :func:`write_vault_page` refuses to clobber
an existing file unless the caller opts in. Callers that want to fold
new knowledge into a page the user owns should append under a
``## Connections`` block rather than rewrite — :func:`append_section`
handles that.

Public API
----------
- :class:`VaultFormat` — enum with ``OBSIDIAN``, ``LOGSEQ``, ``PLAIN``
- :class:`Vault` — a vault root + its resolved write layout
- :func:`detect_vault_format` — pick format from the directory contents
- :func:`resolve_vault` — build a ``Vault`` ready to hand to the pipeline
- :func:`vault_page_path` — where a given entity / concept / source slug
  should land inside the vault
- :func:`format_wikilink` — render a bare slug as the right wikilink
  syntax for the detected format
- :func:`write_vault_page` — non-destructive write with ``overwrite`` opt-in
- :func:`append_section` — append a `## <heading>` block if missing

Design notes
------------
- **Stdlib only.** No YAML parser (we don't read Logseq `config.edn`
  beyond "file exists"), no markdown parser.
- **All paths relative to the vault root.** The caller resolves to
  absolute paths before any disk write so tests + windows paths work.
- **Separate tree + slug flavors.** ``Obsidian`` and ``Plain`` use
  folder-nested writes (``Wiki/Entities/Foo.md``); ``Logseq`` uses flat
  namespace-triple-underscore writes (``pages/wiki___entities___Foo.md``)
  to match Logseq's page-id convention.
- **Config-overridable layout.** ``VaultLayout`` carries the prefix for
  each page type so teams can point everything at ``LLM Wiki/`` or
  whatever their vault convention uses.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─── Format detection ─────────────────────────────────────────────────


class VaultFormat(enum.Enum):
    """Supported vault formats. New formats get their own enum value."""

    OBSIDIAN = "obsidian"
    LOGSEQ = "logseq"
    PLAIN = "plain"


def detect_vault_format(vault_dir: Path) -> VaultFormat:
    """Pick :class:`VaultFormat` for ``vault_dir`` based on the files
    at the root.

    Detection order matters: Logseq's marker is more specific than
    Obsidian's (``.obsidian/`` can sneak in if a user opens the Logseq
    vault in Obsidian once), so we check Logseq first.

    Raises ``FileNotFoundError`` if ``vault_dir`` doesn't exist —
    callers get a precise error instead of a silent "plain" default.
    """
    if not vault_dir.exists():
        raise FileNotFoundError(f"vault directory does not exist: {vault_dir}")
    if not vault_dir.is_dir():
        raise NotADirectoryError(f"vault path is not a directory: {vault_dir}")

    # Logseq markers — either a `logseq/` directory or a `config.edn`
    # (Logseq ships both; one is enough).
    if (vault_dir / "logseq").is_dir() or (vault_dir / "config.edn").is_file():
        return VaultFormat.LOGSEQ

    # Obsidian marker is just a `.obsidian/` config dir.
    if (vault_dir / ".obsidian").is_dir():
        return VaultFormat.OBSIDIAN

    return VaultFormat.PLAIN


# ─── Layout config ────────────────────────────────────────────────────


@dataclass(frozen=True)
class VaultLayout:
    """Where in the vault the sync pipeline writes each kind of page.

    Default values follow the convention most users expect ("llmwiki
    drops its stuff under a top-level ``Wiki/`` folder"). Teams can
    override per-vault by passing custom values to :func:`resolve_vault`.
    """

    entities: str = "Wiki/Entities"
    concepts: str = "Wiki/Concepts"
    sources: str = "Wiki/Sources"
    syntheses: str = "Wiki/Syntheses"
    candidates: str = "Wiki/Candidates"

    def path_for(self, kind: str) -> str:
        """Return the subpath for a given page kind (e.g. ``"entities"``)."""
        mapping = {
            "entities": self.entities,
            "concepts": self.concepts,
            "sources": self.sources,
            "syntheses": self.syntheses,
            "candidates": self.candidates,
        }
        if kind not in mapping:
            raise ValueError(
                f"unknown page kind {kind!r}; expected one of "
                f"{sorted(mapping.keys())}"
            )
        return mapping[kind]


# ─── Resolved vault ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Vault:
    """A detected vault plus the layout we'll write into.

    ``root`` is absolute. ``layout`` is already resolved (default or
    user-overridden). Everything the pipeline needs is on this dataclass
    — callers never need to re-probe the filesystem.
    """

    root: Path
    format: VaultFormat
    layout: VaultLayout = field(default_factory=VaultLayout)

    @property
    def is_obsidian(self) -> bool:
        return self.format is VaultFormat.OBSIDIAN

    @property
    def is_logseq(self) -> bool:
        return self.format is VaultFormat.LOGSEQ

    @property
    def uses_namespace_triple_underscore(self) -> bool:
        """True iff page filenames use ``foo___bar___baz.md`` instead of
        nested folders. Only Logseq uses this convention by default."""
        return self.format is VaultFormat.LOGSEQ


def resolve_vault(
    vault_dir: Path,
    *,
    layout: Optional[VaultLayout] = None,
) -> Vault:
    """Detect + build a :class:`Vault` ready for the pipeline.

    Missing / non-directory paths raise immediately so CLI output is
    readable.
    """
    fmt = detect_vault_format(vault_dir)
    return Vault(
        root=vault_dir.resolve(),
        format=fmt,
        layout=layout or VaultLayout(),
    )


# ─── Page-path resolution ─────────────────────────────────────────────


# Slugs can include unicode letters / digits / underscores / hyphens.
# We don't enforce any particular case convention — the caller already
# normalized the slug via the naming rules elsewhere.
_NAMESPACE_SEP = "___"  # Logseq convention for flat namespace files


def _sanitize_filename(slug: str) -> str:
    """Strip characters that break on macOS / Windows filesystems.

    We're permissive — most slugs are already fine. We only touch the
    literal six characters that break Windows (`<>:"|?*`), the forward
    slash (path separator), and the backslash.
    """
    return re.sub(r'[<>:"/\\|?*]', "-", slug).strip()


def vault_page_path(vault: Vault, kind: str, slug: str) -> Path:
    """Return the absolute path where ``slug`` of the given kind should
    live inside the vault.

    Example — Obsidian entity:
        ``~/MyVault/Wiki/Entities/RAG.md``

    Example — Logseq entity (same slug):
        ``~/MyVault/pages/wiki___entities___RAG.md``
    """
    if not slug:
        raise ValueError("slug must be non-empty")
    clean = _sanitize_filename(slug)
    if not clean:
        raise ValueError(f"slug {slug!r} sanitised to empty string")

    if vault.uses_namespace_triple_underscore:
        # Logseq: flat file under pages/ with triple-underscore separator.
        # Lowercase the prefix (Logseq convention); preserve the slug casing.
        prefix = vault.layout.path_for(kind).lower().replace("/", _NAMESPACE_SEP)
        return vault.root / "pages" / f"{prefix}{_NAMESPACE_SEP}{clean}.md"

    # Obsidian + Plain: nested folders, filename preserves slug casing.
    subpath = vault.layout.path_for(kind)
    return vault.root / subpath / f"{clean}.md"


# ─── Wikilink formatting ──────────────────────────────────────────────


def format_wikilink(vault: Vault, kind: str, slug: str) -> str:
    """Render a wikilink string that the vault's editor will resolve.

    - Obsidian / Plain: ``[[Foo]]`` (Obsidian resolves unqualified
      slugs by vault-wide search; no path needed).
    - Logseq: ``[[wiki/entities/Foo]]`` — Logseq is namespace-aware
      and needs the full page id.

    The ``kind`` parameter is ignored for Obsidian/Plain (Obsidian
    doesn't care which subpath the target lives in) but required so
    Logseq can build the namespace prefix.
    """
    if not slug:
        raise ValueError("slug must be non-empty")
    if vault.is_logseq:
        prefix = vault.layout.path_for(kind).lower()
        # Logseq treats `/` as namespace separator in link syntax
        return f"[[{prefix}/{slug}]]"
    return f"[[{slug}]]"


# ─── Non-destructive writes ───────────────────────────────────────────


def write_vault_page(
    path: Path,
    content: str,
    *,
    overwrite: bool = False,
) -> Path:
    """Write ``content`` to ``path``, refusing to clobber unless asked.

    Non-destructive default is the whole point of vault-overlay mode:
    we never want to silently overwrite a note the user typed.

    Raises :class:`FileExistsError` when the target already exists and
    ``overwrite`` is ``False`` — callers that want to merge with the
    existing page should use :func:`append_section` instead.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"vault page already exists: {path}. "
            "Pass overwrite=True (CLI: --allow-overwrite) to replace, "
            "or use append_section() to merge."
        )
    path.write_text(content, encoding="utf-8")
    return path


# ─── Section append (merge into existing user page) ───────────────────


# Matches a specific H2 heading at line start. Used by append_section()
# to check whether the user already has a section by the target name.
def _heading_exists(body: str, heading: str) -> bool:
    # Case-insensitive; must be at line start, followed by newline or EOF.
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    return bool(pattern.search(body))


def append_section(
    path: Path,
    heading: str,
    body: str,
) -> Path:
    """Append a ``## <heading>`` block with ``body`` to an existing
    vault page, but only if the page doesn't already have that heading.

    Idempotent: calling twice with the same heading is a no-op on the
    second call. The user's existing content is never rewritten.

    Raises :class:`FileNotFoundError` if ``path`` doesn't exist —
    callers should :func:`write_vault_page` first or combine via the
    pipeline-level "create-or-merge" helper.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"cannot append to missing vault page: {path}"
        )
    existing = path.read_text(encoding="utf-8")
    if _heading_exists(existing, heading):
        return path  # nothing to do

    trailer = existing.rstrip()
    if trailer:
        trailer += "\n\n"
    trailer += f"## {heading}\n\n{body.rstrip()}\n"
    path.write_text(trailer, encoding="utf-8")
    return path


# ─── Summary for CLI output ───────────────────────────────────────────


def describe_vault(vault: Vault) -> str:
    """One-line summary for the CLI to print after resolving a vault."""
    return (
        f"vault: {vault.root} "
        f"(format: {vault.format.value}, "
        f"entities→{vault.layout.entities}, concepts→{vault.layout.concepts})"
    )
