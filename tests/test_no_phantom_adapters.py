"""Tests for #493 — no phantom adapters or dead dispatch branches.

The bug: convert.py had `if path.suffix == ".pdf"` calling
`adapter.convert_pdf(path, redact=redact)`. No concrete adapter
ever implemented `convert_pdf`. README + docs both advertised
"PDF Production v0.5". Users who tried it saw confusing
'AttributeError' lines in the quarantine.

This test file is the CI guard against the phantom returning.
"""

from __future__ import annotations

import inspect

from llmwiki import convert as convert_mod
from llmwiki.adapters import REGISTRY, discover_adapters


def _strip_comments(src: str) -> str:
    """Drop full-line `#` comments + trailing `# ...` so the source-
    string scan doesn't false-positive on the historical context
    comment that mentions the deleted code."""
    out = []
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # trailing inline comment
        if "#" in line:
            line = line.split("#", 1)[0]
        out.append(line)
    return "\n".join(out)


def test_convert_all_does_not_dispatch_pdf():
    """The `if path.suffix == \".pdf\"` branch must stay deleted —
    re-adding it without a real adapter brings back the original
    confusing AttributeError quarantine entries."""
    src = _strip_comments(inspect.getsource(convert_mod.convert_all))
    assert 'path.suffix == ".pdf"' not in src, (
        "PDF dispatch branch is back in convert_all — but no adapter "
        "implements convert_pdf. Either land a real PDF adapter first "
        "(declare convert_pdf on BaseAdapter) or remove the dispatch."
    )
    assert "convert_pdf" not in src, (
        "convert_all calls convert_pdf without a concrete impl — "
        "see #493 history for why this is dead code."
    )


def test_no_registered_adapter_implements_convert_pdf():
    """As long as the registry has no convert_pdf-providing adapter,
    the dispatch branch above must stay out (paired guard)."""
    discover_adapters()
    for name, cls in REGISTRY.items():
        assert not hasattr(cls, "convert_pdf"), (
            f"Adapter {name} implements convert_pdf — re-add the "
            f"convert_all dispatch branch in the same PR."
        )


def test_pdf_adapter_not_in_registry():
    """If a real PDF adapter is added later, its name shouldn't be
    `pdf` (reserved as removed in v1.2.0). Use a more specific name
    like `pdf_files` or `pypdf`."""
    discover_adapters()
    assert "pdf" not in REGISTRY, (
        "An adapter is registered as 'pdf' — name was reserved as "
        "removed in v1.2.0. Use a more specific name."
    )
