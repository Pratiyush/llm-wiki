"""Tests for the project-stub auto-seeder (issues-commands.md I-12).

On a real user's corpus, ``wiki/projects/<slug>.md`` files don't exist,
so every project page renders bare — no description, no topic chips, no
homepage link. The demo corpus ships curated files, so the demo site
looks richer than a fresh real one. ``ensure_project_stubs`` closes
that gap by auto-seeding an empty stub per discovered project slug.

Key invariants:

* A new stub is created when the target file does not exist.
* Existing files (hand-authored by the user) are NEVER overwritten.
* Re-running the helper is a no-op on the second call.
* The stub frontmatter is valid (parseable by ``load_project_profile``).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _groups_with(*slugs: str) -> dict[str, list]:
    """Helper: mimic the ``group_by_project`` return shape."""
    return {slug: [] for slug in slugs}


def test_ensure_project_stubs_creates_missing(tmp_path: Path):
    from llmwiki.build import ensure_project_stubs

    meta_dir = tmp_path / "wiki" / "projects"
    groups = _groups_with("alpha", "beta")

    written = ensure_project_stubs(groups, meta_dir)

    assert sorted(p.name for p in written) == ["alpha.md", "beta.md"]
    for slug in ("alpha", "beta"):
        stub = meta_dir / f"{slug}.md"
        assert stub.is_file()
        content = stub.read_text()
        assert f'title: "{slug}"' in content
        assert "type: entity" in content
        assert "entity_type: project" in content
        assert "topics: []" in content
        assert 'description: ""' in content
        assert 'homepage: ""' in content


def test_ensure_project_stubs_never_clobbers_existing(tmp_path: Path):
    from llmwiki.build import ensure_project_stubs

    meta_dir = tmp_path / "wiki" / "projects"
    meta_dir.mkdir(parents=True)

    # Hand-authored file the user already filled in.
    curated = meta_dir / "alpha.md"
    curated_text = (
        "---\n"
        'title: "alpha"\n'
        "type: entity\n"
        "entity_type: project\n"
        "project: alpha\n"
        "topics: [python, api]\n"
        'description: "real description"\n'
        'homepage: "https://example.com/alpha"\n'
        "---\n\n# alpha\n\nHand-authored content.\n"
    )
    curated.write_text(curated_text, encoding="utf-8")

    groups = _groups_with("alpha", "beta")
    written = ensure_project_stubs(groups, meta_dir)

    # Only beta should be newly created.
    assert sorted(p.name for p in written) == ["beta.md"]
    # Alpha's contents must be byte-identical.
    assert curated.read_text() == curated_text


def test_ensure_project_stubs_is_idempotent(tmp_path: Path):
    from llmwiki.build import ensure_project_stubs

    meta_dir = tmp_path / "wiki" / "projects"
    groups = _groups_with("alpha", "beta", "gamma")

    first = ensure_project_stubs(groups, meta_dir)
    assert len(first) == 3

    # Second call must be a no-op — every stub already on disk.
    second = ensure_project_stubs(groups, meta_dir)
    assert second == []


def test_ensure_project_stubs_creates_meta_dir(tmp_path: Path):
    """Helper must create the wiki/projects/ directory if it's missing."""
    from llmwiki.build import ensure_project_stubs

    meta_dir = tmp_path / "wiki" / "projects"
    assert not meta_dir.exists()

    ensure_project_stubs(_groups_with("alpha"), meta_dir)
    assert meta_dir.is_dir()
    assert (meta_dir / "alpha.md").is_file()


def test_stub_frontmatter_is_loadable_by_project_profile(tmp_path: Path):
    """Stub must parse cleanly via the existing metadata loader.

    The loader drops empty ``description`` / ``homepage`` by design so
    the hero block skips rendering them. We only assert that the call
    succeeds and that ``topics`` round-trips as an empty list — that's
    enough to prove the stub's frontmatter is syntactically valid.
    """
    from llmwiki.build import ensure_project_stubs
    from llmwiki.project_topics import load_project_profile

    meta_dir = tmp_path / "wiki" / "projects"
    ensure_project_stubs(_groups_with("my-proj"), meta_dir)

    profile = load_project_profile(meta_dir, "my-proj")
    assert profile is not None
    assert profile.get("topics") == []
    # Empty description/homepage are intentionally omitted by the loader
    # so they don't render an empty row on the project page.
    assert "description" not in profile or profile["description"] == ""
    assert "homepage" not in profile or profile["homepage"] == ""


def test_ensure_project_stubs_empty_groups(tmp_path: Path):
    from llmwiki.build import ensure_project_stubs

    meta_dir = tmp_path / "wiki" / "projects"
    assert ensure_project_stubs({}, meta_dir) == []
