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
      "roots": ["~/Documents/Papers", "~/Downloads/pdfs"],
      "min_pages": 1,
      "max_pages": 500
    }
  }
}
```

| Key | Default | Description |
|---|---|---|
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
```

Without `pypdf`, the adapter registers cleanly and discovers PDF files, but `extract_text()` returns an empty string. The adapter gracefully handles:

- Missing `pypdf` dependency
- Corrupt or unreadable PDFs
- Encrypted PDFs (returns empty string)
- PDFs with no extractable text (image-only scans)

## Schema versions supported

```python
SUPPORTED_SCHEMA_VERSIONS = ["v1"]
```

## Testing the adapter

```bash
python3 -m llmwiki adapters      # pdf listed as 'available: no' (needs config)
python3 -m pytest tests/test_adapter_graduation.py -k pdf -v
```

## Fixture

A minimal synthetic fixture is provided at `tests/fixtures/pdf/minimal.pdf` for adapter discovery testing. Full text-extraction tests require `pypdf`.

## Reference

- [`llmwiki/adapters/pdf.py`](../../llmwiki/adapters/pdf.py) -- the adapter source
- [`llmwiki/convert.py`](../../llmwiki/convert.py) -- the shared converter
- [README](../../README.md) -- project overview
