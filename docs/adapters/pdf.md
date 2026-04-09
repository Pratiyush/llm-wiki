# PDF adapter

**Status:** Production (v0.5)
**Module:** `llmwiki.adapters.pdf`
**Source:** [`llmwiki/adapters/pdf.py`](../../llmwiki/adapters/pdf.py)
**Tracking issue:** #39

## What it reads

The PDF adapter reads `.pdf` files from user-configured directories and treats each as a source document. Unlike the session-transcript adapters (Claude Code, Codex CLI, Cursor, Gemini CLI), PDF ingestion produces source documents rather than conversation transcripts.

## No default paths

The PDF adapter has **no default roots** -- users must explicitly configure paths in `config.json`. This is intentional: we don't want to accidentally ingest every PDF on the machine.

## Configuration

```json
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
```

| Key | Default | Description |
|---|---|---|
| `enabled` | `false` | Must be `true` for the adapter to discover and convert PDFs |
| `roots` | `[]` | Directories to scan for `.pdf` files |
| `min_pages` | `1` | Skip PDFs with fewer pages |
| `max_pages` | `500` | Skip PDFs with more pages |

## Project slug derivation

Uses the parent directory name, lowercased, spaces replaced with dashes, prefixed with `pdf-`:

```
~/Documents/Research Papers/attention.pdf
  -> pdf-research-papers
```

## Text extraction

Text extraction requires `pypdf` as an optional runtime dependency:

```bash
pip install pypdf
# or install via the extras group:
pip install llmwiki[pdf]
```

Without `pypdf`, the adapter registers cleanly but `extract_text()` returns an empty string with `error: "pypdf not installed"` in metadata. The adapter gracefully handles:

- Missing `pypdf` dependency
- Corrupt or unreadable PDFs
- Encrypted PDFs (attempts empty-password decrypt; skips on failure)
- PDFs with no extractable text (image-only scans)

Each page is rendered as a `## Page N` section with extracted text. PDF metadata (title, author, creation date) is pulled from the document info dictionary when available.

## Output format

`convert_pdf()` produces frontmatter'd markdown with:

```yaml
---
slug: attention-is-all-you-need
project: pdf-research-papers
title: "Attention Is All You Need"
date: 2017-06-12
source_file: /path/to/attention-is-all-you-need.pdf
pages: 15
author: "Vaswani et al."
tools_used: []
is_subagent: false
---
```

The title falls back to the filename (with hyphens/underscores → spaces) when the PDF has no metadata title. The date falls back to the file's modification time.

## Schema versions supported

```python
SUPPORTED_SCHEMA_VERSIONS = ["v1"]
```

## Redaction

`convert_pdf()` accepts an optional `redact` callable applied to the final markdown string. This integrates with llmwiki's existing redaction pipeline so personal data in PDFs is scrubbed before wiki ingestion.

## Testing the adapter

```bash
python3 -m llmwiki adapters      # pdf listed as 'available: no' (needs config)
python3 -m pytest tests/test_pdf_adapter.py -v           # 14 production tests
python3 -m pytest tests/test_adapter_graduation.py -k pdf -v  # discovery tests
```

## Fixtures

- `tests/fixtures/pdf/sample.pdf` — 2-page PDF with title "Test PDF", pages containing "Hello World" and "Second Page" text. Used by the 14 production tests for extraction, conversion, discovery, and filter logic.
- `tests/fixtures/pdf/minimal.pdf` — minimal synthetic fixture for adapter discovery testing.

## Reference

- [`llmwiki/adapters/pdf.py`](../../llmwiki/adapters/pdf.py) -- the adapter source
- [`llmwiki/convert.py`](../../llmwiki/convert.py) -- the shared converter
- [README](../../README.md) -- project overview
