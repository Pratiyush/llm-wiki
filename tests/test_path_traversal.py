"""Path-traversal regression tests (#405 + #428).

A poisoned `raw/sessions/*.md` carrying `project: ../../etc/passwd` or
`slug: ../passwd` could write under `out_dir/../../...` because
`build.py` and `exporters.py` use these frontmatter fields verbatim
in path composition. The fix routes them through ``_safe_slug`` at the
discovery boundary so every downstream consumer sees a sanitized value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.build import _safe_slug, discover_sources


# ─── _safe_slug unit tests ───────────────────────────────────────────────


@pytest.mark.parametrize("bad", [
    "../etc/passwd",
    "../../passwd",
    "/absolute/path",
    "\\absolute\\path",
    "..",
    ".",
    "",
    "  ",
    "foo/bar",
    "foo\\bar",
    "foo bar",       # space — not in safe alphabet
    "foo;rm -rf /",  # shell metachar
    "foo\x00bar",    # null byte
    "<script>",
    "foo\nbar",      # newline
    "../" * 100,     # repeated traversal
])
def test_safe_slug_rejects_unsafe_input(bad):
    assert _safe_slug(bad, fallback="_X") == "_X"


@pytest.mark.parametrize("good", [
    "demo-blog-engine",
    "agent-1",
    "v1.2.0",
    "PascalCase",
    "lower_snake",
    "kebab-case",
    "alpha_beta-1.0",
    "Anthropic",
    "Claude_Sonnet_4",
    "ARC-AGI-2",
    "1234",
    "_underscore",
    ".dotprefix",
])
def test_safe_slug_accepts_safe_input(good):
    assert _safe_slug(good, fallback="_X") == good


def test_safe_slug_strips_quotes():
    assert _safe_slug('"quoted"') == "quoted"
    assert _safe_slug("'single'") == "single"


def test_safe_slug_handles_unicode_by_rejecting():
    # Unicode chars (CJK / emoji) are outside [A-Za-z0-9._-] → fallback.
    # This is conservative; safe Unicode handling is out-of-scope.
    assert _safe_slug("日本語") == "_unknown"
    assert _safe_slug("project🦀") == "_unknown"


def test_safe_slug_handles_none():
    assert _safe_slug(None) == "_unknown"


# ─── discover_sources end-to-end ─────────────────────────────────────────


def _write_source(root: Path, name: str, project: str, slug: str | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    fm_lines = [
        '---',
        'title: "Test"',
        'type: source',
        f'project: {project}',
    ]
    if slug is not None:
        fm_lines.append(f'slug: {slug}')
    fm_lines.append('---')
    fm_lines.append('')
    fm_lines.append('body')
    p = root / name
    p.write_text("\n".join(fm_lines), encoding="utf-8")
    return p


def test_discover_sources_sanitizes_traversal_project(tmp_path):
    raw = tmp_path / "raw" / "sessions"
    _write_source(raw, "evil1.md", project="../../etc/passwd")
    _write_source(raw, "evil2.md", project="/absolute/path")
    _write_source(raw, "evil3.md", project="..")
    _write_source(raw, "ok.md", project="demo-blog-engine")

    sources = discover_sources(raw)
    projects = [meta["project"] for _, meta, _ in sources]

    # No traversal segments survive
    assert "../../etc/passwd" not in projects
    assert "/absolute/path" not in projects
    assert ".." not in projects
    # Safe project survived as-is
    assert "demo-blog-engine" in projects
    # Adversarial entries fell back to safe names
    assert all("/" not in p and "\\" not in p and ".." not in p for p in projects)


def test_discover_sources_sanitizes_traversal_slug(tmp_path):
    raw = tmp_path / "raw" / "sessions"
    _write_source(raw, "evil.md", project="demo", slug="../../passwd")
    _write_source(raw, "ok.md", project="demo", slug="my-session")

    sources = discover_sources(raw)
    slugs = [meta.get("slug") for _, meta, _ in sources if "slug" in meta]
    assert "../../passwd" not in slugs
    assert "my-session" in slugs


def test_discover_sources_no_path_escapes_out_dir(tmp_path):
    """Property-style: every (project, slug) combination from sources, when
    joined to a hypothetical out_dir, stays under out_dir.resolve()."""
    raw = tmp_path / "raw" / "sessions"
    out_dir = (tmp_path / "site").resolve()
    out_dir.mkdir()

    adversarial_inputs = [
        ("../../etc/passwd", "ok"),
        ("ok", "../../passwd"),
        ("..", ".."),
        ("/abs", "/abs"),
        ("\\back\\slash", "\\back\\slash"),
        ("ok;rm", "ok;rm"),
        ("ok\x00", "ok\x00"),
    ]
    for i, (proj, slug) in enumerate(adversarial_inputs):
        _write_source(raw, f"adv-{i}.md", project=proj, slug=slug)

    sources = discover_sources(raw)
    for _, meta, _ in sources:
        proj = meta["project"]
        slug = meta.get("slug", "stub")
        composed = (out_dir / "sessions" / proj / f"{slug}.html").resolve()
        # composed must stay under out_dir
        try:
            composed.relative_to(out_dir)
        except ValueError:
            pytest.fail(f"path escapes out_dir: project={proj!r} slug={slug!r} → {composed}")
