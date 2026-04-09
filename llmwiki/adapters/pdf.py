"""PDF ingestion adapter (production).

Reads PDF files from user-configured directories and converts each into a
frontmatter'd markdown file under `raw/sessions/pdf-<subdir>/<name>.md`.

Requires `pypdf` as an optional runtime dep — install with:

    pip install llmwiki[pdf]

Config (`config.json`):

    {
      "adapters": {
        "pdf": {
          "enabled": true,
          "roots": ["~/Documents/Papers", "~/Downloads/pdfs"],
          "min_pages": 1,
          "max_pages": 500
        }
      }
    }

Only `.pdf` files are picked up. Encrypted or scanned PDFs (no extractable
text) are logged and skipped, never crash the pipeline.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter

try:
    import pypdf  # type: ignore
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


@register("pdf")
class PdfAdapter(BaseAdapter):
    """PDF files — reads user-configured directories (optional pypdf dep)"""

    SUPPORTED_SCHEMA_VERSIONS = ["v1"]

    DEFAULT_ROOTS: list[Path] = []  # no defaults — user must configure

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("adapters", {}).get("pdf", {})
        paths = ad_cfg.get("roots") or []
        self.roots: list[Path] = (
            [Path(p).expanduser() for p in paths] if paths else self.DEFAULT_ROOTS
        )
        self.min_pages = int(ad_cfg.get("min_pages", 1))
        self.max_pages = int(ad_cfg.get("max_pages", 500))
        self.enabled = bool(ad_cfg.get("enabled", False))

    @property
    def session_store_path(self):  # type: ignore[override]
        return self.roots

    @classmethod
    def is_available(cls) -> bool:
        return HAS_PYPDF

    def discover_sessions(self) -> list[Path]:
        if not self.enabled or not HAS_PYPDF:
            return []
        out: list[Path] = []
        for root in self.roots:
            root = Path(root).expanduser()
            if root.exists():
                out.extend(sorted(root.rglob("*.pdf")))
        return out

    def derive_project_slug(self, path: Path) -> str:
        return f"pdf-{path.parent.name.lower().replace(' ', '-')}"

    @staticmethod
    def extract_text(pdf_path: Path) -> tuple[str, dict[str, Any]]:
        """Extract all text from a PDF. Returns (body_md, metadata).

        Gracefully handles encrypted/scanned PDFs — returns empty string
        and metadata with an error key instead of crashing."""
        meta: dict[str, Any] = {"source_file": str(pdf_path), "pages": 0}
        if not HAS_PYPDF:
            meta["error"] = "pypdf not installed"
            return "", meta
        try:
            reader = pypdf.PdfReader(str(pdf_path))
        except Exception as e:
            meta["error"] = f"unreadable: {e}"
            return "", meta

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                meta["error"] = "encrypted PDF — cannot extract text"
                return "", meta

        # PDF metadata
        info = reader.metadata or {}
        if info.title:
            meta["title"] = str(info.title)
        if info.author:
            meta["author"] = str(info.author)
        if info.creation_date:
            try:
                meta["date"] = info.creation_date.strftime("%Y-%m-%d")
            except Exception:
                pass

        meta["pages"] = len(reader.pages)

        chunks = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                chunks.append(f"## Page {i + 1}\n\n{text.strip()}\n")

        return "\n".join(chunks), meta

    def convert_pdf(self, pdf_path: Path, redact=None) -> tuple[str, str]:
        """Convert a single PDF to frontmatter'd markdown.

        Returns (markdown_content, output_filename) or ("", "") if the
        PDF has no extractable text."""
        body, meta = self.extract_text(pdf_path)

        if not body.strip():
            return "", ""

        pages = meta.get("pages", 0)
        if pages < self.min_pages or pages > self.max_pages:
            return "", ""

        title = meta.get("title") or pdf_path.stem.replace("-", " ").replace("_", " ")
        date = meta.get("date", "")
        if not date:
            try:
                mtime = pdf_path.stat().st_mtime
                date = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
            except OSError:
                date = ""

        slug = pdf_path.stem.lower().replace(" ", "-").replace("_", "-")
        project = self.derive_project_slug(pdf_path)

        fm_lines = [
            "---",
            f"slug: {slug}",
            f"project: {project}",
            f'title: "{title}"',
            f"date: {date}",
            f"source_file: {pdf_path}",
            f"pages: {pages}",
            f"type: pdf",
        ]
        if meta.get("author"):
            fm_lines.append(f'author: "{meta["author"]}"')
        fm_lines.append("tools_used: []")
        fm_lines.append("is_subagent: false")
        fm_lines.append("---")
        fm_lines.append("")
        fm_lines.append(f"# {title}")
        fm_lines.append("")

        md = "\n".join(fm_lines) + body

        if redact:
            md = redact(md)

        return md, f"{slug}.md"
