"""Tests for the PDF adapter (production, #39)."""
import pytest
from pathlib import Path

# Skip entire module if pypdf isn't installed
pypdf = pytest.importorskip("pypdf", reason="pypdf required for PDF adapter tests")

from llmwiki.adapters.pdf import PdfAdapter


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "pdf"
SAMPLE_PDF = FIXTURE_DIR / "sample.pdf"


class TestExtractText:
    def test_extracts_two_pages(self):
        body, meta = PdfAdapter.extract_text(SAMPLE_PDF)
        assert "## Page 1" in body
        assert "## Page 2" in body
        assert meta["pages"] == 2

    def test_page_anchors_format(self):
        body, _ = PdfAdapter.extract_text(SAMPLE_PDF)
        lines = body.split("\n")
        page_headers = [l for l in lines if l.startswith("## Page ")]
        assert page_headers == ["## Page 1", "## Page 2"]

    def test_metadata_title(self):
        _, meta = PdfAdapter.extract_text(SAMPLE_PDF)
        assert meta.get("title") == "Test PDF"

    def test_metadata_source_file(self):
        _, meta = PdfAdapter.extract_text(SAMPLE_PDF)
        assert "sample.pdf" in meta["source_file"]

    def test_nonexistent_pdf(self):
        body, meta = PdfAdapter.extract_text(Path("/nonexistent.pdf"))
        assert body == ""
        assert "error" in meta


class TestConvertPdf:
    def test_produces_frontmatter(self):
        adapter = PdfAdapter({"adapters": {"pdf": {"enabled": True, "roots": [str(FIXTURE_DIR)]}}})
        md, filename = adapter.convert_pdf(SAMPLE_PDF)
        assert md.startswith("---")
        assert "slug: sample" in md
        assert "pages: 2" in md
        assert 'title: "Test PDF"' in md
        assert "type: pdf" in md
        assert filename == "sample.md"

    def test_body_contains_text(self):
        adapter = PdfAdapter({"adapters": {"pdf": {"enabled": True, "roots": [str(FIXTURE_DIR)]}}})
        md, _ = adapter.convert_pdf(SAMPLE_PDF)
        assert "Hello World" in md
        assert "Second Page" in md

    def test_redaction_applied(self):
        adapter = PdfAdapter({"adapters": {"pdf": {"enabled": True, "roots": [str(FIXTURE_DIR)]}}})
        md, _ = adapter.convert_pdf(SAMPLE_PDF, redact=lambda s: s.replace("Hello", "REDACTED"))
        assert "REDACTED World" in md

    def test_min_pages_filter(self):
        adapter = PdfAdapter({"adapters": {"pdf": {"enabled": True, "roots": [str(FIXTURE_DIR)], "min_pages": 5}}})
        md, filename = adapter.convert_pdf(SAMPLE_PDF)
        assert md == ""
        assert filename == ""

    def test_max_pages_filter(self):
        adapter = PdfAdapter({"adapters": {"pdf": {"enabled": True, "roots": [str(FIXTURE_DIR)], "max_pages": 1}}})
        md, filename = adapter.convert_pdf(SAMPLE_PDF)
        assert md == ""


class TestDiscovery:
    def test_discover_finds_sample(self):
        adapter = PdfAdapter({"adapters": {"pdf": {"enabled": True, "roots": [str(FIXTURE_DIR)]}}})
        sessions = adapter.discover_sessions()
        assert any(p.name == "sample.pdf" for p in sessions)

    def test_disabled_discovers_nothing(self):
        adapter = PdfAdapter({"adapters": {"pdf": {"enabled": False, "roots": [str(FIXTURE_DIR)]}}})
        assert adapter.discover_sessions() == []

    def test_project_slug(self):
        adapter = PdfAdapter({"adapters": {"pdf": {"enabled": True, "roots": [str(FIXTURE_DIR)]}}})
        slug = adapter.derive_project_slug(SAMPLE_PDF)
        assert slug == "pdf-pdf"  # parent dir name is "pdf"


class TestIsAvailable:
    def test_available_with_pypdf(self):
        assert PdfAdapter.is_available() is True
