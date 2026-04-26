"""Integration test for the collision-retry branch in ``convert_all`` (#339).

When two distinct source jsonls would write to the same output path
(subagent sharing its parent's start-time + slug, or two top-level
sessions that happen to start in the same minute), the retry appends
a source-path hash so both files land side-by-side rather than one
getting quarantined.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from llmwiki import convert as c


def _write_jsonl(path: Path, session_id: str, iso_ts: str,
                 slug: str = "shared-slug") -> None:
    """Seed a minimal claude_code-shaped jsonl.

    ``slug`` on the first record pins derive_session_slug so two
    sources can deliberately collide on the canonical filename.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "user",
            "sessionId": session_id,
            "slug": slug,
            "timestamp": iso_ts,
            "cwd": "/tmp",
            "gitBranch": "main",
            "message": {"role": "user", "content": "hi"},
        }) + "\n"
        + json.dumps({
            "type": "assistant",
            "sessionId": session_id,
            "timestamp": iso_ts,
            "message": {"role": "assistant", "content": "hello"},
        }) + "\n",
        encoding="utf-8",
    )


def _seed_env(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Seed a tmp_path repo + fake ~/.claude/projects/ source tree.

    Returns ``(home, project_dir, out_dir, state)``.  ``project_dir`` is
    already one level inside the store root so the adapter derives a
    stable project slug for every file under it.
    """
    home = tmp_path / "home"
    home.mkdir()
    # Store root (what the adapter scans) AND the project-dir within it.
    store_root = home / ".claude" / "projects"
    project_dir = store_root / "my-proj"
    out_dir = tmp_path / "repo" / "raw" / "sessions"
    state = tmp_path / "state.json"
    return home, project_dir, out_dir, state


def _patch(monkeypatch, home, out_dir, state):
    # ClaudeCodeAdapter.session_store_path is a class-level attribute
    # evaluated at class-definition time, so we have to patch the class
    # itself instead of relying on Path.home monkeypatching.  Point it
    # at the `projects/` directory so `derive_project_slug()` resolves
    # every file under it against that prefix.
    from llmwiki.adapters.claude_code import ClaudeCodeAdapter
    store = home / ".claude" / "projects"
    monkeypatch.setattr(
        ClaudeCodeAdapter, "session_store_path", store, raising=False,
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(c, "DEFAULT_STATE_FILE", state)
    monkeypatch.setattr(c, "REPO_ROOT", home.parent / "repo")


def test_subagent_collision_is_resolved_with_hash_suffix(tmp_path, monkeypatch):
    """Parent + subagent that share start-time + slug both land on disk.

    With the #406 fix, the subagent file gets a ``-subagent-<id>`` suffix
    on its slug at render time, so parent + subagent no longer COLLIDE
    on the canonical name — they land at distinct filenames without
    needing the disambiguator. The original intent of this test (both
    files survive) still holds; just the mechanism changed.
    """
    home, proj, out_dir, state = _seed_env(tmp_path)

    ts = "2026-04-16T10:00:00Z"
    parent = proj / "parent.jsonl"
    sub = proj / "subagents" / "agent-aprompt-abc.jsonl"
    _write_jsonl(parent, "sess-uuid-1111", ts, slug="shared-slug")
    _write_jsonl(sub, "sess-uuid-1111", ts, slug="shared-slug")

    _patch(monkeypatch, home, out_dir, state)

    c.discover_adapters()
    rc = c.convert_all(
        adapters=["claude_code"],
        out_dir=out_dir,
        state_file=state,
        include_current=True,  # include even very-recent test files
        force=False,
    )
    assert rc in (0, 1)

    outs = sorted(out_dir.rglob("*.md"))
    # Both files must land — parent at canonical name, subagent at
    # <slug>-subagent-<agent_id>.md.
    assert len(outs) == 2, f"expected 2 files, got {[p.name for p in outs]}"
    names = [p.name for p in outs]
    parent_files = [n for n in names if "subagent" not in n]
    subagent_files = [n for n in names if "subagent" in n]
    assert parent_files, f"parent file missing; got {names}"
    assert subagent_files, f"subagent file missing; got {names}"


def test_second_source_with_identical_canonical_name_gets_hash(tmp_path, monkeypatch):
    """Two sources produce the same canonical name; second gets a hash."""
    home, proj, out_dir, state = _seed_env(tmp_path)
    ts = "2026-04-16T10:00:00Z"

    # Both directly in the project dir so derive_project_slug gives the
    # same value for both, AND both carry the same pinned slug so
    # flat_output_name produces identical canonical filenames.
    s1 = proj / "session-a.jsonl"
    s2 = proj / "session-b.jsonl"
    _write_jsonl(s1, "same-session-id", ts, slug="shared-slug")
    _write_jsonl(s2, "same-session-id", ts, slug="shared-slug")

    _patch(monkeypatch, home, out_dir, state)

    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir,
                  state_file=state, include_current=True)

    outs = sorted(out_dir.rglob("*.md"))
    canonical = [p for p in outs if "--" not in p.name]
    disambig = [p for p in outs if "--" in p.name]
    assert len(outs) >= 2
    assert canonical, f"no canonical file: {outs}"
    assert disambig, f"no disambiguated file: {outs}"


def test_resync_same_source_is_idempotent(tmp_path, monkeypatch):
    """Re-running sync on the same jsonl doesn't explode into
    <canonical> + <hash1> + <hash2> — the state key protects us."""
    home, proj, out_dir, state = _seed_env(tmp_path)
    _write_jsonl(proj / "s.jsonl", "x", "2026-04-16T10:00:00Z")
    _patch(monkeypatch, home, out_dir, state)

    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir,
                  state_file=state, include_current=True)
    first = sorted(out_dir.rglob("*.md"))
    c.convert_all(adapters=["claude_code"], out_dir=out_dir,
                  state_file=state, include_current=True)
    second = sorted(out_dir.rglob("*.md"))
    assert first == second, f"re-sync grew the tree: {first} → {second}"


def test_force_sync_does_not_drop_colliding_sources(tmp_path, monkeypatch):
    """Regression: sync --force used to gate the collision disambiguator
    on ``not force``, so two sources producing the same canonical name
    silently overwrote each other. On real corpora this cost ~200
    sessions out of 495. Fix: disambiguation now keys off the set of
    names written in THIS run, independent of --force.
    """
    home, proj, out_dir, state = _seed_env(tmp_path)
    ts = "2026-04-16T10:00:00Z"

    # Three sources, all collide on (date, project, slug) → same canonical.
    _write_jsonl(proj / "a.jsonl", "sess-a", ts, slug="dup")
    _write_jsonl(proj / "b.jsonl", "sess-b", ts, slug="dup")
    _write_jsonl(proj / "c.jsonl", "sess-c", ts, slug="dup")

    _patch(monkeypatch, home, out_dir, state)
    c.discover_adapters()

    # --force wipes state, which used to also wipe the collision guard.
    c.convert_all(
        adapters=["claude_code"], out_dir=out_dir, state_file=state,
        include_current=True, force=True,
    )

    outs = sorted(out_dir.rglob("*.md"))
    canonical = [p for p in outs if "--" not in p.name]
    disambig = [p for p in outs if "--" in p.name]

    # All 3 sources must land on disk — one at canonical, two with hashes.
    assert len(outs) == 3, (
        f"expected 3 files on disk, got {len(outs)}: {[p.name for p in outs]}"
    )
    assert len(canonical) == 1 and len(disambig) == 2, (
        f"expected 1 canonical + 2 disambiguated, got "
        f"canonical={[p.name for p in canonical]}, "
        f"disambig={[p.name for p in disambig]}"
    )


def test_three_way_collision_no_force_all_land(tmp_path, monkeypatch):
    """Without --force, three colliding sources still all land (1 canonical +
    2 disambiguated). This is the baseline the --force path must match."""
    home, proj, out_dir, state = _seed_env(tmp_path)
    ts = "2026-04-16T10:00:00Z"

    _write_jsonl(proj / "a.jsonl", "sess-a", ts, slug="triple")
    _write_jsonl(proj / "b.jsonl", "sess-b", ts, slug="triple")
    _write_jsonl(proj / "c.jsonl", "sess-c", ts, slug="triple")

    _patch(monkeypatch, home, out_dir, state)
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code"], out_dir=out_dir, state_file=state,
        include_current=True, force=False,
    )

    outs = sorted(out_dir.rglob("*.md"))
    canonical = [p for p in outs if "--" not in p.name]
    disambig = [p for p in outs if "--" in p.name]
    assert len(outs) == 3, [p.name for p in outs]
    assert len(canonical) == 1 and len(disambig) == 2


def test_resync_preserves_disambiguated_filenames(tmp_path, monkeypatch):
    """After an initial sync creates one canonical + one disambiguated
    file, a second sync (no --force) must leave the tree exactly as it
    was. The state file remembers which source owned the hashed name,
    so neither source regenerates or clobbers."""
    home, proj, out_dir, state = _seed_env(tmp_path)
    ts = "2026-04-16T10:00:00Z"

    _write_jsonl(proj / "a.jsonl", "sess-a", ts, slug="same")
    _write_jsonl(proj / "b.jsonl", "sess-b", ts, slug="same")

    _patch(monkeypatch, home, out_dir, state)
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir,
                  state_file=state, include_current=True)

    first = sorted(p.name for p in out_dir.rglob("*.md"))
    assert len(first) == 2, first

    # Second sync, same inputs, no --force. State says these sources
    # are already converted (mtime unchanged), so sync should short-
    # circuit at the "unchanged" branch and touch nothing on disk.
    c.convert_all(adapters=["claude_code"], out_dir=out_dir,
                  state_file=state, include_current=True)

    second = sorted(p.name for p in out_dir.rglob("*.md"))
    assert first == second, (
        f"re-sync grew or renamed the tree: {first} → {second}"
    )


def test_disambiguated_names_stable_across_incremental_sync(tmp_path, monkeypatch):
    """A new colliding source added in a later sync must NOT retroactively
    rename already-written siblings. The original canonical + original
    hash survive; only the newcomer gets its own hash.

    Regression guard: a naive implementation of the "rewrite on collision"
    path could re-assign hashes based on sort order, which would make
    every existing disambiguated file orphan on the next sync — a silent
    corruption that's much worse than the data-loss bug this module
    already guards against.
    """
    home, proj, out_dir, state = _seed_env(tmp_path)
    ts = "2026-04-16T10:00:00Z"

    # Sync 1: two colliding sources → one canonical, one hashed.
    _write_jsonl(proj / "first.jsonl", "sess-1", ts, slug="stable")
    _write_jsonl(proj / "second.jsonl", "sess-2", ts, slug="stable")
    _patch(monkeypatch, home, out_dir, state)
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir,
                  state_file=state, include_current=True)
    after_first = sorted(p.name for p in out_dir.rglob("*.md"))
    assert len(after_first) == 2

    # Sync 2: add a third colliding source. The two from sync 1 must
    # remain byte-identical; only a new file lands for sync-3's source.
    _write_jsonl(proj / "third.jsonl", "sess-3", ts, slug="stable")
    c.convert_all(adapters=["claude_code"], out_dir=out_dir,
                  state_file=state, include_current=True)
    after_second = sorted(p.name for p in out_dir.rglob("*.md"))

    assert len(after_second) == 3, after_second
    # Every filename from sync 1 must still exist verbatim in sync 2.
    for name in after_first:
        assert name in after_second, (
            f"sync-2 renamed or removed {name!r}: {after_second}"
        )


def test_disambiguated_source_file_matches_disk(tmp_path, monkeypatch):
    """#404 + #427: the ``source_file:`` frontmatter field must point at
    the actual on-disk filename — including the ``--<hash>`` suffix on
    disambiguated files. Before the fix, ``render_session_markdown``
    hard-coded the canonical filename in the frontmatter, so disambiguated
    files all carried a ``source_file:`` that resolved to a sibling file
    (or a 404 in the graph viewer).
    """
    home, proj, out_dir, state = _seed_env(tmp_path)
    ts = "2026-04-16T10:00:00Z"

    # Two colliding sources → one canonical, one hashed.
    _write_jsonl(proj / "alpha.jsonl", "sess-a", ts, slug="dup-check")
    _write_jsonl(proj / "beta.jsonl", "sess-b", ts, slug="dup-check")

    _patch(monkeypatch, home, out_dir, state)
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir,
                  state_file=state, include_current=True)

    outs = sorted(out_dir.rglob("*.md"))
    assert len(outs) == 2, [p.name for p in outs]

    # For every output file, the source_file: frontmatter line must name
    # that exact file (matching disambiguated suffix where present).
    for p in outs:
        body = p.read_text(encoding="utf-8")
        # Pull out the source_file: line from the frontmatter
        sf_line = next(
            (line for line in body.splitlines() if line.startswith("source_file:")),
            None,
        )
        assert sf_line is not None, f"no source_file: line in {p.name}"
        # Frontmatter says raw/sessions/<filename>; check the trailing path matches
        recorded_filename = sf_line.split("/")[-1]
        assert recorded_filename == p.name, (
            f"frontmatter source_file mismatch in {p.name}: "
            f"frontmatter says {recorded_filename!r}, file is {p.name!r}"
        )

    # Stronger check: at least one of the two files must be disambiguated
    # (carry --<hash>) — otherwise the test isn't exercising the fix.
    disambig_files = [p for p in outs if "--" in p.name]
    assert disambig_files, (
        f"test setup failed to produce disambiguation: {[p.name for p in outs]}"
    )
