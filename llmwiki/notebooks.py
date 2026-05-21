"""Notebook migration helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from llmwiki import REPO_ROOT
from llmwiki.web.services import notebooks as notebook_services
from llmwiki.web.services.notebooks import (
    DEFAULT_NOTEBOOK_SLUG,
    DEFAULT_NOTEBOOK_TITLE,
    SLUG_RE,
)


NOTEBOOK_DESCRIPTION = "\u4f01\u4e1a\u7ba1\u7406\u5236\u5ea6\u9ed8\u8ba4\u77e5\u8bc6\u5e93"
MIGRATION_PATHS = (
    ("wiki", "wiki"),
    ("graph", "graph"),
    ("raw/company-docs", "raw/company-docs"),
)


def is_valid_slug(slug: str) -> bool:
    """Return True when slug is safe for notebook directory lookup."""
    return bool(SLUG_RE.fullmatch(slug))


def current_notebook_slug(raw: str | None) -> str:
    """Return the requested notebook slug, falling back to the default."""
    if raw and is_valid_slug(raw):
        return raw
    return DEFAULT_NOTEBOOK_SLUG


def notebook_wiki_dir(slug: str, *, repo_root: Path = REPO_ROOT) -> Path:
    """Return repo_root/notebooks/<slug>/wiki after path boundary checks."""
    slug = current_notebook_slug(slug)
    repo_root = repo_root.resolve(strict=False)
    notebooks_root = (repo_root / "notebooks").resolve(strict=False)
    root = (notebooks_root / slug).resolve(strict=False)
    if root != notebooks_root and notebooks_root not in root.parents:
        raise ValueError("notebook slug resolves outside notebooks directory")
    if root != repo_root and repo_root not in root.parents:
        raise ValueError("notebook path resolves outside repository")
    return root / "wiki"


def _relative(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _notebook_root(repo_root: Path) -> Path:
    repo_root = repo_root.resolve(strict=False)
    lexical_base = repo_root / "notebooks"
    lexical_root = lexical_base / DEFAULT_NOTEBOOK_SLUG
    if lexical_root != lexical_base and lexical_base not in lexical_root.parents:
        raise ValueError("default notebook path resolves outside notebooks directory")
    resolved_root = lexical_root.resolve(strict=False)
    if resolved_root != repo_root and repo_root not in resolved_root.parents:
        raise ValueError("default notebook path resolves outside repository")
    return lexical_root


def _target_has_user_content(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_file():
        return True
    return any(child.name != ".gitkeep" for child in path.rglob("*") if child.is_file())


def _write_notebook_metadata(notebook_root: Path) -> None:
    notebook_root.mkdir(parents=True, exist_ok=True)
    metadata_path = notebook_root / "notebook.json"
    if metadata_path.exists():
        return

    metadata = {
        "slug": DEFAULT_NOTEBOOK_SLUG,
        "title": DEFAULT_NOTEBOOK_TITLE,
        "description": NOTEBOOK_DESCRIPTION,
        "visibility": "public",
        "is_default": True,
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _ensure_default_notebook_files(repo_root: Path) -> None:
    original_repo_root = notebook_services.REPO_ROOT
    try:
        notebook_services.REPO_ROOT = repo_root
        notebook_services.ensure_notebook_dirs(DEFAULT_NOTEBOOK_SLUG)
    finally:
        notebook_services.REPO_ROOT = original_repo_root
    _write_notebook_metadata(_notebook_root(repo_root))


def migrate_default_notebook(
    *,
    repo_root: Path = REPO_ROOT,
    dry_run: bool = False,
) -> dict[str, object]:
    """Copy existing root wiki data into the default notebook without overwrites."""
    repo_root = repo_root.resolve()
    notebook_root = _notebook_root(repo_root)

    would_copy: list[str] = []
    copied: list[str] = []
    blocked: list[str] = []
    copy_pairs: list[tuple[Path, Path]] = []

    for source_rel, target_rel in MIGRATION_PATHS:
        source = repo_root / source_rel
        target = notebook_root / target_rel
        if not source.exists():
            continue

        target_label = _relative(target, repo_root)
        if _target_has_user_content(target):
            blocked.append(target_label)
            continue

        would_copy.append(f"{source_rel} -> {target_label}")
        copy_pairs.append((source, target))

    if dry_run:
        return {
            "dry_run": True,
            "would_copy": would_copy,
            "copied": copied,
            "blocked": blocked,
        }
    if blocked:
        return {
            "dry_run": False,
            "would_copy": would_copy,
            "copied": copied,
            "blocked": blocked,
        }

    _ensure_default_notebook_files(repo_root)

    for source, target in copy_pairs:
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        copied.append(f"{_relative(source, repo_root)} -> {_relative(target, repo_root)}")

    return {
        "dry_run": False,
        "would_copy": would_copy,
        "copied": copied,
        "blocked": blocked,
    }
