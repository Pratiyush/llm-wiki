"""Guardrails for the production docs overhaul (v1.2.0 · #265).

The tutorials under ``docs/tutorials/`` follow a strict skeleton so the
editorial voice stays consistent. These tests keep them from rotting:

- Every tutorial has the mandatory sections (Time / You'll need / Result /
  Why / Steps / Verify / Troubleshooting / Next).
- Every link from ``docs/index.md`` resolves to a real file.
- Every tutorial has ``docs_shell: true`` in frontmatter so it picks up
  the `.docs-shell` CSS.
- The docs-shell CSS is appended to the main stylesheet (namespace only).
- The style guide exists and covers its own structural requirements.
- No raw ``<script>`` in tutorial bodies (docs survive without JS).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT


DOCS = REPO_ROOT / "docs"
TUTORIALS = DOCS / "tutorials"
INDEX = DOCS / "index.md"
STYLE_GUIDE = DOCS / "style-guide.md"


# ─── Existence ─────────────────────────────────────────────────────────


def test_docs_index_exists():
    assert INDEX.is_file()


def test_style_guide_exists():
    assert STYLE_GUIDE.is_file()


def test_tutorials_dir_exists():
    assert TUTORIALS.is_dir()


@pytest.mark.parametrize(
    "filename",
    [
        "01-installation.md",
        "02-first-sync.md",
        "03-use-with-claude-code.md",
        "04-use-with-codex-cli.md",
        "05-querying-your-wiki.md",
        "06-bring-your-obsidian-vault.md",
        "07-example-workflows.md",
    ],
)
def test_every_numbered_tutorial_exists(filename: str):
    path = TUTORIALS / filename
    assert path.is_file(), f"tutorial missing: {filename}"


# ─── Frontmatter ───────────────────────────────────────────────────────


def _collect_tutorials() -> list[Path]:
    return sorted(p for p in TUTORIALS.glob("*.md") if p.name != "setup-guide.md")


def test_every_tutorial_has_docs_shell_frontmatter():
    """Without `docs_shell: true`, pages don't pick up the editorial
    CSS — a silent regression."""
    for path in _collect_tutorials():
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{path.name}: missing frontmatter block"
        fm = text.split("---\n", 2)[1]
        assert "docs_shell: true" in fm, (
            f"{path.name}: frontmatter missing `docs_shell: true`"
        )
        assert "type: tutorial" in fm, (
            f"{path.name}: frontmatter missing `type: tutorial`"
        )


def test_index_page_has_docs_shell_frontmatter():
    fm = INDEX.read_text(encoding="utf-8").split("---\n", 2)[1]
    assert "docs_shell: true" in fm


def test_style_guide_has_docs_shell_frontmatter():
    fm = STYLE_GUIDE.read_text(encoding="utf-8").split("---\n", 2)[1]
    assert "docs_shell: true" in fm


# ─── Mandatory tutorial sections ───────────────────────────────────────


MANDATORY_SECTIONS = (
    "**Time:**",
    "**You'll need:**",
    "**Result:**",
    "## Why this matters",
    "## Verify",
    "## Troubleshooting",
    "## Next",
)


def test_every_tutorial_has_all_mandatory_sections():
    missing: dict[str, list[str]] = {}
    for path in _collect_tutorials():
        # Old setup-guide.md predates this convention — exempt
        if path.name == "setup-guide.md":
            continue
        text = path.read_text(encoding="utf-8")
        lacking = [s for s in MANDATORY_SECTIONS if s not in text]
        if lacking:
            missing[path.name] = lacking
    assert not missing, (
        "Tutorials missing mandatory sections (see docs/style-guide.md):\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in missing.items())
    )


def test_every_tutorial_has_numbered_h1():
    """Title pattern is `NN · <phrase>` — the number gives readers an
    instant sense of where they are in the sequence."""
    for path in _collect_tutorials():
        if path.name == "setup-guide.md":
            continue
        text = path.read_text(encoding="utf-8")
        # First `# ` heading
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        assert m, f"{path.name}: no h1"
        assert re.match(r"^\d{2}\s*·", m.group(1)), (
            f"{path.name}: h1 {m.group(1)!r} doesn't start with `NN · `"
        )


def test_tutorial_filename_number_matches_h1_number():
    """`03-use-with-claude-code.md` → `# 03 · Use with Claude Code`."""
    for path in _collect_tutorials():
        if path.name == "setup-guide.md":
            continue
        m = re.match(r"^(\d{2})-", path.name)
        if not m:
            continue
        file_num = m.group(1)
        text = path.read_text(encoding="utf-8")
        h1 = re.search(r"^#\s+(\d{2})\s*·", text, re.MULTILINE)
        assert h1, f"{path.name}: no numbered h1"
        assert h1.group(1) == file_num, (
            f"{path.name}: filename has {file_num}, h1 has {h1.group(1)}"
        )


# ─── Internal links ────────────────────────────────────────────────────


LINK_RE = re.compile(r"\]\(([^)]+)\)")


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks + inline code so illustrative link
    examples inside code don't trip the link checker."""
    # Fenced blocks ``` … ```
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Inline code — but leave the closing backtick for the link target
    # detection. Easiest: drop any `…` span too.
    text = re.sub(r"`[^`\n]+`", "", text)
    return text


# Paths that exist only as build output (`llmwiki build` writes them
# into site/). The test can't find them in the source tree, so allow-list.
_GENERATED_HTML_ALLOWLIST = frozenset({
    "changelog.html",   # compiled from CHANGELOG.md at the repo root
    "index.html",       # site/index.html (home)
})


def _check_links(doc: Path) -> list[str]:
    """Return the list of unresolved relative links in ``doc``."""
    text = _strip_code_blocks(doc.read_text(encoding="utf-8"))
    missing: list[str] = []
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        # Strip anchor
        base = target.split("#", 1)[0]
        if not base:
            continue
        # Whitelist known build-output paths — they only exist after
        # `llmwiki build`, not in the source tree.
        if Path(base).name in _GENERATED_HTML_ALLOWLIST:
            continue
        resolved = (doc.parent / base).resolve()
        # Allow directory links (they'll be rendered by build.py)
        if resolved.is_dir():
            continue
        if not resolved.is_file():
            missing.append(target)
    return missing


def test_index_links_all_resolve():
    missing = _check_links(INDEX)
    assert not missing, f"docs/index.md links to missing paths: {missing}"


def test_style_guide_links_all_resolve():
    missing = _check_links(STYLE_GUIDE)
    assert not missing, f"docs/style-guide.md links to missing paths: {missing}"


def test_every_tutorial_links_resolve():
    bad: dict[str, list[str]] = {}
    for path in _collect_tutorials():
        missing = _check_links(path)
        if missing:
            bad[path.name] = missing
    assert not bad, f"tutorials link to missing paths: {bad}"


# ─── Sequencing: every tutorial's "Next" link points at the next one ─


def test_tutorials_next_links_chain_correctly():
    """01 → 02 → 03 → 04 → 05 → 06 → 07. Tutorial 07 is the last;
    its Next section points back at the hub."""
    chain = [
        ("01-installation.md", "02-first-sync.md"),
        ("02-first-sync.md", "03-use-with-claude-code.md"),
        ("03-use-with-claude-code.md", "04-use-with-codex-cli.md"),
        ("04-use-with-codex-cli.md", "05-querying-your-wiki.md"),
        ("05-querying-your-wiki.md", "06-bring-your-obsidian-vault.md"),
        ("06-bring-your-obsidian-vault.md", "07-example-workflows.md"),
    ]
    for source, expected in chain:
        path = TUTORIALS / source
        text = path.read_text(encoding="utf-8")
        # Next-section must contain a link to `expected`
        next_section = text.split("## Next", 1)[-1]
        assert expected in next_section, (
            f"{source}: 'Next' section doesn't link to {expected}"
        )


def test_final_tutorial_links_back_to_hub():
    path = TUTORIALS / "07-example-workflows.md"
    text = path.read_text(encoding="utf-8")
    assert "../index.md" in text, (
        "07-example-workflows.md should link back to docs/index.md"
    )


# ─── Raw HTML / JS safety ─────────────────────────────────────────────


def test_no_raw_script_tags_in_tutorials():
    """Docs must survive without JS — and are a top target for copy-paste
    into other sites where `<script>` would be dangerous."""
    for path in _collect_tutorials():
        text = path.read_text(encoding="utf-8")
        # Allow `<script>` inside fenced code blocks. Strip those first.
        stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        stripped = re.sub(r"`[^`]+`", "", stripped)
        # The style-guide mentions `<script>` in prose describing what
        # never to do — we allow that single mention by scoping to
        # tutorials only, which this function does.
        assert "<script" not in stripped, (
            f"{path.name}: raw <script> tag in tutorial body"
        )


# ─── CSS integration ───────────────────────────────────────────────────


def test_docs_shell_css_appended_to_main_stylesheet():
    from llmwiki.render.css import CSS

    assert ".docs-shell" in CSS, (
        "docs-shell CSS not appended to llmwiki/render/css.py — "
        "pages with `docs_shell: true` won't pick up editorial styles"
    )


def test_docs_shell_css_selectors_namespaced():
    """No leakage onto non-docs pages."""
    from llmwiki.render.docs_css import DOCS_SHELL_CSS

    # Every top-level selector under `.docs-shell` must be prefixed. We
    # accept media queries / keyframes / root-theme blocks as exceptions.
    selectors = re.findall(
        r"^(\.[A-Za-z0-9_-]+)", DOCS_SHELL_CSS, re.MULTILINE
    )
    leaked = [s for s in selectors if not s.startswith(".docs-shell")]
    assert not leaked, (
        f"docs-shell CSS has non-namespaced selectors: {leaked}"
    )


def test_docs_shell_css_inherits_brand_tokens_only():
    """No hard-coded hex colors — everything goes through the brand-system
    CSS variables (#115)."""
    from llmwiki.render.docs_css import DOCS_SHELL_CSS
    # Allow pixel values + rgba inside color-mix; flag only naked #hex.
    # A naked hex is anything that starts with `#` followed by 3 or 6
    # hex digits outside of var() / color-mix / comment context.
    # Simple heuristic: count hex tokens not inside var() or comment.
    # We accept zero naked hex codes — the brand tokens cover us.
    hex_occurrences = re.findall(r"#[0-9A-Fa-f]{3,8}", DOCS_SHELL_CSS)
    # Strip hex values that live inside comments
    comment_stripped = re.sub(r"/\*.*?\*/", "", DOCS_SHELL_CSS, flags=re.DOTALL)
    real_hex = re.findall(r"#[0-9A-Fa-f]{3,8}", comment_stripped)
    assert not real_hex, (
        f"docs-shell CSS hard-codes hex color(s) {real_hex!r}; use "
        "`var(--…)` tokens from llmwiki/render/css.py instead"
    )


# ─── Style guide requirements ──────────────────────────────────────────


def test_style_guide_covers_core_topics():
    text = STYLE_GUIDE.read_text(encoding="utf-8")
    for keyword in (
        "Voice",
        "Tutorial structure",
        "Callouts",
        "Code blocks",
        "Linking",
        "Adding a new tutorial",
        "Tests that protect the docs",
    ):
        assert keyword in text, (
            f"style-guide.md missing required section '{keyword}'"
        )


def test_style_guide_mentions_guardrail_test_file():
    """If this file is renamed, the style guide must be updated too."""
    text = STYLE_GUIDE.read_text(encoding="utf-8")
    assert "tests/test_docs_structure.py" in text


# ─── README cross-reference ──────────────────────────────────────────


def test_readme_points_at_tutorial_hub():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/index.md" in readme, (
        "README.md must surface docs/index.md as the documentation hub"
    )
    # Spot-check a couple of tutorial links
    assert "docs/tutorials/01-installation.md" in readme
    assert "docs/tutorials/03-use-with-claude-code.md" in readme
