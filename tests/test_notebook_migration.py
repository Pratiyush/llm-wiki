from __future__ import annotations

import json
import os
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_migrate_default_notebook_dry_run_does_not_write(tmp_path):
    from llmwiki.notebooks import migrate_default_notebook

    _write(tmp_path / "wiki" / "index.md", "# Index\n")
    _write(tmp_path / "raw" / "company-docs" / "doc.md", "# Doc\n")

    result = migrate_default_notebook(repo_root=tmp_path, dry_run=True)

    assert result["dry_run"] is True
    assert result["would_copy"]
    assert result["copied"] == []
    assert result["blocked"] == []
    assert not (tmp_path / "notebooks" / "enterprise-management").exists()


def test_migrate_default_notebook_copies_existing_wiki_and_raw(tmp_path):
    from llmwiki.notebooks import migrate_default_notebook

    _write(tmp_path / "wiki" / "index.md", "# Index\n")
    _write(tmp_path / "graph" / "graph.json", '{"nodes":[]}\n')
    _write(tmp_path / "raw" / "company-docs" / "policy.md", "# Policy\n")

    result = migrate_default_notebook(repo_root=tmp_path)

    notebook_root = tmp_path / "notebooks" / "enterprise-management"
    assert result["dry_run"] is False
    assert result["blocked"] == []
    assert (notebook_root / "wiki" / "index.md").read_text(encoding="utf-8") == "# Index\n"
    assert (notebook_root / "graph" / "graph.json").read_text(encoding="utf-8") == '{"nodes":[]}\n'
    assert (notebook_root / "raw" / "company-docs" / "policy.md").read_text(encoding="utf-8") == "# Policy\n"

    metadata = json.loads((notebook_root / "notebook.json").read_text(encoding="utf-8"))
    assert metadata["slug"] == "enterprise-management"
    assert metadata["title"] == "\u4f01\u4e1a\u7ba1\u7406\u5236\u5ea6"
    assert metadata["is_default"] is True


def test_migrate_default_notebook_refuses_overwrite(tmp_path):
    from llmwiki.notebooks import migrate_default_notebook

    _write(tmp_path / "wiki" / "index.md", "# Source\n")
    _write(tmp_path / "graph" / "graph.json", '{"nodes":[]}\n')
    target_index = tmp_path / "notebooks" / "enterprise-management" / "wiki" / "index.md"
    _write(target_index, "existing")

    result = migrate_default_notebook(repo_root=tmp_path)

    assert result["blocked"]
    assert result["copied"] == []
    assert target_index.read_text(encoding="utf-8") == "existing"
    assert not (tmp_path / "notebooks" / "enterprise-management" / "graph" / "graph.json").exists()


def test_notebooks_migrate_default_dry_run_cli(monkeypatch, capsys):
    from llmwiki import cli

    monkeypatch.setattr(
        "llmwiki.notebooks.migrate_default_notebook",
        lambda dry_run=False: {
            "dry_run": dry_run,
            "would_copy": ["wiki -> notebooks/enterprise-management/wiki"],
            "copied": [],
            "blocked": [],
        },
    )

    rc = cli.main(["notebooks", "migrate-default", "--dry-run"])

    output = capsys.readouterr().out
    assert rc == 0
    assert "Would copy:" in output
    assert "wiki -> notebooks/enterprise-management/wiki" in output


def test_migrate_default_notebook_rejects_notebooks_symlink_escape(tmp_path):
    import pytest

    from llmwiki.notebooks import migrate_default_notebook

    outside = tmp_path / "outside"
    outside.mkdir()
    _write(tmp_path / "wiki" / "index.md", "# Source\n")
    try:
        os.symlink(outside, tmp_path / "notebooks", target_is_directory=True)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("creating symlinks requires elevated privileges on this Windows host")
        raise

    with pytest.raises(ValueError):
        migrate_default_notebook(repo_root=tmp_path)

    assert not (outside / "enterprise-management").exists()
