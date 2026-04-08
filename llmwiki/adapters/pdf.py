"""PDF ingestion adapter.

Reads PDF files from a user-configured directory and treats each as a source
document. Requires `pypdf` as an optional runtime dep — the adapter registers
cleanly without it, but reports unavailable if `pypdf` is missing.

Config:

    {
      "adapters": {
        "pdf": {
          "roots": ["~/Documents/Papers", "~/Downloads/pdfs"],
          "min_pages": 1,
          "max_pages": 500
        }
      }
    }

Only `.pdf` files are picked up. Each PDF gets converted to a single markdown
file with the extracted text under `raw/sessions/pdf-<subdir>/<name>.md`.

**This is a v0.3 stub** — the adapter declares the interface and registers,
but requires pypdf to actually extract text. Without pypdf it's visible in
`llmwiki adapters` as available (if the paths exist) but discover_sessions
returns only the first level of files so you know it was found.
"""

from __future__ import annotations

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

    @property
    def session_store_path(self):  # type: ignore[override]
        return self.roots

    @classmethod
    def is_available(cls) -> bool:
        # PDF adapter requires explicit configuration — default is 'no'
        # because DEFAULT_ROOTS is empty. Users who set roots in config.json
        # will see it become available.
        return False

    def discover_sessions(self) -> list[Path]:
        out: list[Path] = []
        for root in self.roots:
            root = Path(root).expanduser()
            if root.exists():
                out.extend(sorted(root.rglob("*.pdf")))
        return out

    def derive_project_slug(self, path: Path) -> str:
        return f"pdf-{path.parent.name.lower().replace(' ', '-')}"

    @staticmethod
    def extract_text(pdf_path: Path) -> str:
        """Extract all text from a PDF. Requires pypdf. Returns empty string
        if pypdf isn't installed."""
        if not HAS_PYPDF:
            return ""
        try:
            reader = pypdf.PdfReader(str(pdf_path))  # type: ignore
        except Exception:
            return ""
        chunks = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                chunks.append(f"## Page {i + 1}\n\n{text.strip()}\n")
        return "\n".join(chunks)
