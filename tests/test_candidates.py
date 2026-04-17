"""Tests for wiki/candidates/ approval workflow (v1.1.0, #51)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from llmwiki.candidates import (
    CANDIDATES_DIR_NAME,
    ARCHIVE_DIR_NAME,
    MIRRORED_SUBDIRS,
    DEFAULT_STALE_DAYS,
    Candidate,
    is_candidate,
    candidates_dir,
    archive_dir,
    list_candidates,
    promote,
    merge,
    discard,
    stale_candidates,
    _parse_frontmatter,
    _age_days,
    _rewrite_status,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


def _mk_wiki(tmp_path: Path) -> Path:
    """Create a wiki/ tree with candidates/ + entities/ + concepts/."""
    wiki = tmp_path / "wiki"
    for sub in MIRRORED_SUBDIRS:
        (wiki / sub).mkdir(parents=True, exist_ok=True)
        (wiki / "candidates" / sub).mkdir(parents=True, exist_ok=True)
    return wiki


def _write_candidate(
    wiki: Path,
    kind: str,
    slug: str,
    *,
    body: str = "",
    date: str = "2026-04-17",
    title: str | None = None,
) -> Path:
    path = wiki / "candidates" / kind / f"{slug}.md"
    title = title or slug
    path.write_text(
        f'---\ntitle: "{title}"\ntype: {kind[:-1]}\nstatus: candidate\n'
        f'last_updated: {date}\n---\n\n{body or f"# {title}\\n\\nCandidate body."}\n',
        encoding="utf-8",
    )
    return path


# ─── Constants ────────────────────────────────────────────────────────


def test_constants_defined():
    assert CANDIDATES_DIR_NAME == "candidates"
    assert ARCHIVE_DIR_NAME == "archive"
    assert DEFAULT_STALE_DAYS == 30
    assert "entities" in MIRRORED_SUBDIRS
    assert "concepts" in MIRRORED_SUBDIRS


# ─── is_candidate / dir helpers ──────────────────────────────────────


def test_is_candidate_true_for_candidates_path():
    assert is_candidate(Path("/x/wiki/candidates/entities/Foo.md")) is True


def test_is_candidate_false_for_normal_path():
    assert is_candidate(Path("/x/wiki/entities/Foo.md")) is False


def test_candidates_dir_returns_right_path(tmp_path: Path):
    wiki = tmp_path / "wiki"
    assert candidates_dir(wiki) == wiki / "candidates"


def test_archive_dir_returns_right_path(tmp_path: Path):
    wiki = tmp_path / "wiki"
    assert archive_dir(wiki) == wiki / "archive" / "candidates"


# ─── list_candidates ─────────────────────────────────────────────────


def test_list_empty_wiki(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    assert list_candidates(wiki) == []


def test_list_missing_candidates_dir(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    # No candidates/ subdir
    assert list_candidates(wiki) == []


def test_list_returns_pending_entities(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "NewEntity")
    _write_candidate(wiki, "concepts", "NewConcept")
    items = list_candidates(wiki)
    assert len(items) == 2
    kinds = {c["kind"] for c in items}
    assert kinds == {"entities", "concepts"}


def test_list_skips_context_md(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Real")
    (wiki / "candidates" / "entities" / "_context.md").write_text(
        "---\ntitle: Context\n---\n", encoding="utf-8"
    )
    items = list_candidates(wiki)
    assert len(items) == 1
    assert items[0]["slug"] == "Real"


def test_list_includes_body_preview(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "X", body="# X\n\nDetails about X entity.")
    items = list_candidates(wiki)
    assert "Details about X entity" in items[0]["body_preview"]


def test_list_computes_age_days(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Old", date="2026-04-01")
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    items = list_candidates(wiki, now=now)
    assert items[0]["age_days"] == 16


# ─── promote ────────────────────────────────────────────────────────


def test_promote_moves_candidate_to_entities(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    candidate = _write_candidate(wiki, "entities", "ApprovedFoo")

    promoted = promote("ApprovedFoo", wiki)
    assert promoted == wiki / "entities" / "ApprovedFoo.md"
    assert promoted.is_file()
    assert not candidate.exists()


def test_promote_rewrites_status_to_reviewed(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Foo")
    path = promote("Foo", wiki)
    content = path.read_text(encoding="utf-8")
    assert "status: reviewed" in content
    assert "status: candidate" not in content


def test_promote_infers_kind_from_candidate_location(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "concepts", "Idea")
    path = promote("Idea", wiki)
    assert path.parent.name == "concepts"


def test_promote_respects_explicit_kind(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Foo")
    path = promote("Foo", wiki, kind="entities")
    assert path.parent.name == "entities"


def test_promote_raises_when_candidate_missing(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    with pytest.raises(FileNotFoundError):
        promote("Ghost", wiki)


# ─── merge ──────────────────────────────────────────────────────────


def test_merge_appends_body_to_target(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    target = wiki / "entities" / "Main.md"
    target.write_text(
        '---\ntitle: "Main"\ntype: entity\n---\n\n# Main\n\nOriginal content.\n',
        encoding="utf-8",
    )
    _write_candidate(wiki, "entities", "Duplicate", body="# Duplicate\n\nExtra info.")

    result = merge("Duplicate", wiki, into_slug="Main")
    assert result == target
    text = target.read_text(encoding="utf-8")
    assert "Original content" in text
    assert "## Candidate merge" in text
    assert "Extra info" in text


def test_merge_archives_candidate_after(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "Main.md").write_text(
        '---\ntitle: Main\ntype: entity\n---\nbody\n', encoding="utf-8"
    )
    candidate = _write_candidate(wiki, "entities", "Dup")
    merge("Dup", wiki, into_slug="Main")
    assert not candidate.exists()


def test_merge_raises_when_target_missing(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Dup")
    with pytest.raises(FileNotFoundError):
        merge("Dup", wiki, into_slug="Nonexistent")


# ─── discard ────────────────────────────────────────────────────────


def test_discard_moves_to_archive(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    candidate = _write_candidate(wiki, "entities", "Bogus")
    archived = discard("Bogus", wiki, reason="hallucinated")

    assert not candidate.exists()
    assert archived.is_file()
    # Archive structure: wiki/archive/candidates/<timestamp>/Bogus.md
    assert "archive" in archived.parts
    assert "candidates" in archived.parts
    assert archived.name == "Bogus.md"


def test_discard_writes_reason_file(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Fake")
    archived = discard("Fake", wiki, reason="not a real thing")

    reason_file = archived.with_suffix(".reason.txt")
    assert reason_file.is_file()
    text = reason_file.read_text(encoding="utf-8")
    assert "not a real thing" in text
    assert "Discarded at:" in text


def test_discard_raises_when_candidate_missing(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    with pytest.raises(FileNotFoundError):
        discard("Ghost", wiki, reason="x")


# ─── stale_candidates ────────────────────────────────────────────────


def test_stale_returns_only_old_candidates(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Old", date="2026-01-01")
    _write_candidate(wiki, "entities", "New", date="2026-04-15")
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    stale = stale_candidates(wiki, threshold_days=30, now=now)
    assert len(stale) == 1
    assert stale[0]["slug"] == "Old"


def test_stale_custom_threshold(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Medium", date="2026-04-05")
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    # age = 12 days; threshold 10 → stale; threshold 30 → not stale
    assert len(stale_candidates(wiki, threshold_days=10, now=now)) == 1
    assert len(stale_candidates(wiki, threshold_days=30, now=now)) == 0


# ─── Internals ───────────────────────────────────────────────────────


def test_parse_frontmatter_valid():
    meta, body = _parse_frontmatter('---\ntitle: "Foo"\ntype: entity\n---\n\nBody.\n')
    assert meta == {"title": "Foo", "type": "entity"}
    assert body.strip() == "Body."


def test_parse_frontmatter_missing():
    meta, body = _parse_frontmatter("no frontmatter")
    assert meta == {}
    assert body == "no frontmatter"


def test_age_days_none_returns_zero():
    assert _age_days(None) == 0


def test_age_days_invalid_returns_zero():
    assert _age_days("not-a-date") == 0


def test_age_days_computes_correctly():
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    assert _age_days("2026-04-01", now=now) == 16


def test_rewrite_status_replaces_existing():
    text = (
        '---\ntitle: X\nstatus: candidate\n---\n\nbody\n'
    )
    result = _rewrite_status(text, old="candidate", new="reviewed")
    assert "status: reviewed" in result
    assert "status: candidate" not in result


def test_rewrite_status_adds_when_missing():
    text = '---\ntitle: X\n---\n\nbody\n'
    result = _rewrite_status(text, old="candidate", new="reviewed")
    assert "status: reviewed" in result


# ─── Lint rule integration ───────────────────────────────────────────


def test_stale_candidates_lint_rule_registered():
    from llmwiki.lint import REGISTRY
    from llmwiki.lint import rules  # noqa: F401
    assert "stale_candidates" in REGISTRY


# ─── Slash command ───────────────────────────────────────────────────


def test_wiki_review_slash_command_exists():
    from llmwiki import REPO_ROOT
    cmd = REPO_ROOT / ".claude" / "commands" / "wiki-review.md"
    assert cmd.is_file()
    text = cmd.read_text(encoding="utf-8")
    assert "promote" in text
    assert "merge" in text
    assert "discard" in text


# ─── CLI integration ────────────────────────────────────────────────


def test_cli_candidates_subcommand_registered():
    from llmwiki.cli import build_parser
    parser = build_parser()
    sub_action = None
    for a in parser._actions:
        if hasattr(a, "choices") and a.choices:
            sub_action = a
            break
    assert sub_action is not None
    assert "candidates" in sub_action.choices
