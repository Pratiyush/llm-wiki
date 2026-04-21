"""Docs-site compiler (v1.2.0 · #265).

Walks ``docs/**/*.md`` and emits matching HTML under ``site/docs/``,
wrapping every body with ``<main class="docs-shell">`` (+ the ``docs-hub``
modifier on ``docs/index.md``) so the page picks up the minimalism +
trust-authority editorial CSS in ``llmwiki/render/docs_css.py``.

Gate: only pages carrying ``docs_shell: true`` in frontmatter are
compiled. Pages without the flag stay GitHub-rendered only, which is
what existing reference docs (e.g. ``docs/adapters/*.md``) expect.

Public API
----------
- :func:`iter_docs_pages` — discover every opt-in markdown source
- :func:`compile_docs_site` — build all pages into ``site_dir / "docs"``
- :func:`render_meta_strip` — convert the ``**Time / You'll need / Result**``
  tutorial header into the editorial hairline strip

Design notes
------------
- **Stdlib + the existing markdown pipeline.** We reuse ``md_to_html``
  from ``llmwiki/build.py`` so code-fence highlighting + table rendering
  + heading anchors stay identical to the rest of the site.
- **Never rewrites non-opt-in files.** The gate on ``docs_shell: true``
  keeps ``docs/adapters/*.md`` + ``docs/deploy/*.md`` etc. untouched —
  they're linked from the hub but render on GitHub only.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# ─── Frontmatter parsing ─────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw, body = match.group(1), match.group(2)
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    return meta, body


def _is_docs_shell(meta: dict[str, str]) -> bool:
    raw = str(meta.get("docs_shell", "")).strip().lower()
    return raw in {"true", "yes", "on", "1"}


# ─── Discovery ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DocsPage:
    """One compiled docs page."""

    source: Path              # absolute path under docs/
    rel: str                  # e.g. "index.md" or "tutorials/01-installation.md"
    title: str
    meta: dict[str, str]
    body: str                 # markdown body without frontmatter
    is_shell: bool = True     # False = passthrough (minimal wrapper, no editorial CSS)

    @property
    def out_rel(self) -> str:
        """Relative HTML path under site/docs/."""
        stem = self.rel[:-len(".md")] if self.rel.endswith(".md") else self.rel
        if stem == "index":
            return "index.html"
        return f"{stem}.html"

    @property
    def is_hub(self) -> bool:
        return self.rel == "index.md"

    @property
    def depth(self) -> int:
        """Directory depth below ``docs/`` — drives CSS href prefixing."""
        return self.rel.count("/")


def iter_docs_pages(
    docs_dir: Path, *, include_passthrough: bool = True
) -> Iterable[DocsPage]:
    """Yield every ``docs/**/*.md`` under ``docs_dir``.

    ``include_passthrough=True`` (default) emits pages WITHOUT
    ``docs_shell: true`` too — they render with a minimal wrapper so
    cross-links from opt-in pages still resolve. The ``is_shell``
    attribute tells the caller which mode to use.
    """
    if not docs_dir.is_dir():
        return
    for path in sorted(docs_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _parse_frontmatter(text)
        is_shell = _is_docs_shell(meta)
        if not is_shell and not include_passthrough:
            continue
        title = meta.get("title") or _first_h1(body) or path.stem
        rel = str(path.relative_to(docs_dir)).replace("\\", "/")
        yield DocsPage(
            source=path,
            rel=rel,
            title=title,
            meta=meta,
            body=body,
            is_shell=is_shell,
        )


def _first_h1(body: str) -> Optional[str]:
    match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return match.group(1).strip() if match else None


# ─── Meta-strip rendering ─────────────────────────────────────────────


_META_FIELDS = ("Time", "You'll need", "Result")


def _inline_markdown(text: str) -> str:
    """Minimal inline-markdown pass used for meta-strip values: backtick
    inline-code + ``[text](url)`` links. Anything richer belongs in the
    body, not the strip.
    """
    # 1) escape HTML first so user prose can't inject tags
    safe = html.escape(text)
    # 2) unescape only the backticks + brackets we care about
    safe = safe.replace("&#x27;", "'")  # apostrophe looks weird escaped
    # 3) inline code: `foo` -> <code>foo</code>
    safe = re.sub(
        r"`([^`\n]+?)`",
        lambda m: f"<code>{m.group(1)}</code>",
        safe,
    )
    # 4) inline links: [label](url) -> <a href="url">label</a>
    #    Keep this after code so backticks inside labels still render.
    safe = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        safe,
    )
    return safe


def render_meta_strip(body: str) -> Optional[str]:
    """Turn the tutorial's opening ``**Time: …**`` / ``**You'll need: …**``
    / ``**Result: …**`` lines into a ``<dl class="docs-meta">`` strip.

    Inline markdown (backticks + links) in the value is rendered;
    everything else is HTML-escaped.

    Returns the HTML block or ``None`` if no fields were found. Callers
    splice the strip between the h1 and the first section.
    """
    found: list[tuple[str, str]] = []
    for field in _META_FIELDS:
        # match `**Field:** value` — stop at next `**` or newline
        pattern = re.compile(
            rf"\*\*{re.escape(field)}:\*\*\s+(.+?)(?=\n|$)", re.IGNORECASE
        )
        m = pattern.search(body)
        if m:
            found.append((field, m.group(1).strip()))

    if not found:
        return None

    items = "".join(
        f'<dt>{html.escape(label)}</dt>'
        f'<dd>{_inline_markdown(value)}</dd>'
        for label, value in found
    )
    return f'<dl class="docs-meta">{items}</dl>'


def _strip_meta_lines(body: str) -> str:
    """Remove the raw ``**Time:** …`` etc. lines from the body — we
    render them separately as the hairline strip."""
    for field in _META_FIELDS:
        body = re.sub(
            rf"^\*\*{re.escape(field)}:\*\*\s+.+?$\n?",
            "",
            body,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    return body


# ─── Compilation ─────────────────────────────────────────────────────


def _css_prefix(depth: int) -> str:
    """Return the relative href prefix to reach ``site/style.css``
    from a page nested ``depth`` levels below ``site/docs/``.

    - ``docs/index.html``             depth 0 → ``../``
    - ``docs/tutorials/01.html``      depth 1 → ``../../``
    """
    return "../" * (depth + 1)


def _breadcrumb(page: DocsPage) -> str:
    """One-line crumb trail: ``← Docs hub`` for non-hub pages."""
    if page.is_hub:
        return ""
    if page.depth == 0:
        href = "index.html"
    else:
        href = ("../" * page.depth) + "index.html"
    return (
        f'<p style="margin: 0 0 24px; font-size: 0.85rem;">'
        f'<a href="{html.escape(href)}">← Docs hub</a></p>'
    )


_GITHUB_EDIT_BASE = (
    "https://github.com/Pratiyush/llm-wiki/edit/master/docs"
)


def _tutorial_seq(pages: list["DocsPage"]) -> list["DocsPage"]:
    """Return numbered tutorial pages (``docs/tutorials/NN-*.md``) sorted
    by their leading two-digit prefix.  Used for prev/next wiring (#282)."""
    tuts = []
    for p in pages:
        if not p.rel.startswith("tutorials/"):
            continue
        name = p.rel.rsplit("/", 1)[-1]
        m = re.match(r"^(\d{2})-", name)
        if not m:
            continue
        tuts.append((int(m.group(1)), p))
    tuts.sort(key=lambda t: t[0])
    return [p for _, p in tuts]


def _tutorial_toc_html(body: str) -> str:
    """Build an in-page table of contents from ``## `` and ``### `` headings.

    Returns empty string when fewer than 2 headings exist — TOC is
    only useful on longer pages.
    """
    entries: list[tuple[int, str, str]] = []
    for m in re.finditer(r"^(#{2,3})\s+(.+?)\s*$", body, re.MULTILINE):
        level = len(m.group(1))
        title = re.sub(r"[`*_]", "", m.group(2))  # strip markdown emphasis
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        entries.append((level, title, slug))
    if len(entries) < 2:
        return ""
    items = []
    for level, title, slug in entries:
        indent = "  " * (level - 2)
        items.append(
            f'{indent}<li><a href="#{html.escape(slug)}">{html.escape(title)}</a></li>'
        )
    return (
        '<nav class="tutorial-toc" aria-label="Table of contents">'
        '<details open>'
        '<summary>On this page</summary>'
        '<ul>'
        + "\n".join(items)
        + "</ul>"
        "</details>"
        "</nav>"
    )


def _tutorial_footer_html(
    current: "DocsPage",
    all_pages: list["DocsPage"],
    docs_rel_from_page: str,
) -> str:
    """Build the prev/next footer + edit-on-GitHub link shown at the
    bottom of every numbered tutorial (#282).

    ``docs_rel_from_page`` — e.g. ``"../"`` when the current page is
    ``docs/tutorials/01-installation.md`` and we want the prev/next
    hrefs rooted at ``docs/``.
    """
    tuts = _tutorial_seq(all_pages)
    try:
        idx = tuts.index(current)
    except ValueError:
        return ""

    prev_tut = tuts[idx - 1] if idx > 0 else None
    next_tut = tuts[idx + 1] if idx < len(tuts) - 1 else None

    bits: list[str] = []
    if prev_tut:
        href = docs_rel_from_page + prev_tut.out_rel.replace(".md", ".html")
        bits.append(
            f'<a class="prev-tut" href="{html.escape(href)}" rel="prev">'
            f'<span class="tut-nav-dir">← Previous</span>'
            f'<span class="tut-nav-title">{html.escape(prev_tut.title)}</span>'
            f'</a>'
        )
    else:
        bits.append('<span class="prev-tut placeholder"></span>')
    if next_tut:
        href = docs_rel_from_page + next_tut.out_rel.replace(".md", ".html")
        bits.append(
            f'<a class="next-tut" href="{html.escape(href)}" rel="next">'
            f'<span class="tut-nav-dir">Next →</span>'
            f'<span class="tut-nav-title">{html.escape(next_tut.title)}</span>'
            f'</a>'
        )
    else:
        bits.append('<span class="next-tut placeholder"></span>')

    edit_href = f"{_GITHUB_EDIT_BASE}/{current.rel}"
    edit_html = (
        f'<a class="edit-on-github" href="{html.escape(edit_href)}" '
        f'target="_blank" rel="noopener">Edit on GitHub ↗</a>'
    )

    return (
        '<hr class="tutorial-footer-rule">'
        '<nav class="tutorial-footer" aria-label="Tutorial navigation">'
        + "".join(bits)
        + "</nav>"
        + f'<div class="tutorial-edit">{edit_html}</div>'
    )


def compile_docs_site(
    docs_dir: Path,
    site_dir: Path,
    *,
    md_to_html=None,
    page_head=None,
    nav_builder=None,
) -> list[Path]:
    """Compile every opt-in page under ``docs_dir`` into ``site_dir/docs/``.

    ``md_to_html`` + ``page_head`` are injected so ``llmwiki/build.py``
    can pass its existing renderers without import cycles. ``nav_builder``
    is a callable ``(link_prefix: str) -> str`` that produces the site-
    wide navigation with the right href prefix for the current page's
    directory depth. If ``None`` we omit the nav (useful for tests).

    Returns the list of files written (absolute paths).
    """
    if md_to_html is None:
        md_to_html = _fallback_md_to_html
    if page_head is None:
        page_head = _fallback_page_head

    out_root = site_dir / "docs"
    written: list[Path] = []
    all_pages = list(iter_docs_pages(docs_dir))

    for page in all_pages:
        meta_strip = render_meta_strip(page.body) if page.is_shell else ""
        body_without_meta = (
            _strip_meta_lines(page.body) if page.is_shell else page.body
        )
        body_html = md_to_html(body_without_meta)

        # #282: insert an in-page table of contents on tutorials that
        # have ≥2 section headings. Slots in right after the <h1>.
        toc_html = ""
        if page.rel.startswith("tutorials/"):
            toc_html = _tutorial_toc_html(body_without_meta)

        # Splice the meta strip (then TOC) right after the <h1>…</h1> line.
        if meta_strip or toc_html:
            replacement = f"</h1>\n{meta_strip}\n{toc_html}"
            body_html = body_html.replace("</h1>", replacement, 1)

        # #270: route source-code + repo-root-only links to GitHub
        # before the generic .md→.html pass, so e.g. `../../llmwiki/convert.py`
        # becomes an absolute GitHub URL instead of a dangling relative path.
        body_html = rewrite_source_code_links_to_github(body_html)
        # P0 fix: rewrite every internal .md link to .html so the
        # compiled pages actually link to each other.
        body_html = rewrite_md_links_to_html(body_html)

        if page.is_shell:
            shell_class = "docs-shell docs-hub" if page.is_hub else "docs-shell"
        else:
            # Passthrough: minimal wrapper, no editorial CSS — these
            # are legacy docs (adapters, deploy guides) that still need
            # to resolve as .html from the hub + tutorials.
            shell_class = "docs-shell docs-passthrough"
        description = _first_paragraph(body_without_meta)[:200]

        css_prefix = _css_prefix(page.depth)
        nav = nav_builder(css_prefix) if nav_builder else ""

        # #282: prev/next + edit-on-GitHub footer for numbered tutorials.
        footer_html = ""
        if page.rel.startswith("tutorials/") and re.match(
            r"^\d{2}-", page.rel.rsplit("/", 1)[-1]
        ):
            # docs_rel_from_page: we need a path that resolves from the
            # current page back to the docs root. Tutorials live at
            # site/docs/tutorials/NN-x.html so "../" gets us to docs/.
            footer_html = _tutorial_footer_html(page, all_pages, "../")

        html_doc = (
            page_head(page.title, description, css_prefix=css_prefix)
            + nav
            + f'<main id="main-content" class="{shell_class}">'
            + _breadcrumb(page)
            + body_html
            + footer_html
            + "</main>\n</body>\n</html>\n"
        )

        out_path = out_root / page.out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_doc, encoding="utf-8")
        written.append(out_path)

    return written


# ─── .md → .html link rewriting (P0 fix — #265) ─────────────────────


# Matches `href="something.md"` or `href="something.md#anchor"`.
# Intentionally does NOT match absolute URLs (http, mailto) or hrefs
# that already end in .html. Internal relative paths only.
_MD_HREF_RE = re.compile(
    r'href="(?!https?:|mailto:|#)([^"]+?)\.md(\#[^"]*)?"'
)

# #270: docs pages frequently reference source code or root files that
# don't compile to HTML — link rewriter used to leave them dangling.
# Match anything under ../.. that points at source code or repo-root
# files we intentionally don't render.
_SOURCE_CODE_EXTS = (
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".rb", ".java", ".kt", ".swift",
    ".sh", ".toml", ".yaml", ".yml", ".json", ".cfg", ".ini",
    ".Dockerfile", ".env",
)
_ROOT_ONLY_MD_BASENAMES = {
    # #284: README.md + CONTRIBUTING.md now compile to site HTML, so
    # they're NOT in this list — the .md→.html pass routes them to the
    # compiled page inside the site.
    "CODE_OF_CONDUCT.md",
    "CLAUDE.md", "AGENTS.md", "SECURITY.md", "RELEASE-NOTES.md",
    "LICENSE", ".gitignore", ".env", ".editorconfig",
}
_GITHUB_BLOB_URL = "https://github.com/Pratiyush/llm-wiki/blob/master"

_CODE_OR_ROOT_HREF_RE = re.compile(
    r'href="(?!https?:|mailto:|#)([^"]+?)"'
)


_ROOT_ONLY_HTML_BASENAMES = {
    b.replace(".md", ".html")
    for b in _ROOT_ONLY_MD_BASENAMES if b.endswith(".md")
}


def _rewrite_one_to_github(href: str) -> str | None:
    """Return a GitHub blob URL for ``href`` if it points at source
    code or a root file; else ``None`` (caller leaves the href alone).
    """
    # Strip any leading ../ chunks to get the path relative to repo root.
    path = re.sub(r"^(?:\.\./)+", "", href)
    path = path.lstrip("/")
    if not path:
        return None
    # Pull off any #anchor / ?query.
    path_no_fragment = path.split("#", 1)[0].split("?", 1)[0]
    base = path_no_fragment.rsplit("/", 1)[-1]
    # Source-code files — always route to GitHub.
    if path_no_fragment.endswith(_SOURCE_CODE_EXTS):
        return f"{_GITHUB_BLOB_URL}/{path_no_fragment}"
    # Repo-root files (README, CONTRIBUTING, LICENSE, CODE_OF_CONDUCT,
    # .gitignore) that aren't compiled to HTML.
    if base in _ROOT_ONLY_MD_BASENAMES:
        return f"{_GITHUB_BLOB_URL}/{path_no_fragment}"
    # Previously-rewritten .html versions of root-only files
    # (e.g. ``../CLAUDE.html`` from an earlier md→html pass that ran
    # before we knew the file is repo-root-only).  Flip back to the
    # canonical .md source on GitHub.
    if base in _ROOT_ONLY_HTML_BASENAMES:
        md_name = base.replace(".html", ".md")
        md_path = path_no_fragment.rsplit("/", 1)[0] + "/" + md_name if "/" in path_no_fragment else md_name
        return f"{_GITHUB_BLOB_URL}/{md_path}"
    return None


_SESSION_LOCAL_BASENAMES = {
    "tasks.md", "CHANGELOG.md", "_progress.md",
    "user_profile.md", "user_pratiyush.md",
    "RELEASE-NOTES.md", "notes.md", "TODO.md",
    "plan.md", "roadmap.md",
}


def _is_session_local_ref(href: str, source_path_prefix: str = "sessions/") -> bool:
    """Heuristic: href is a project-local reference that won't resolve
    anywhere in the compiled site (#336).

    Applied to session transcripts, which routinely inline references
    to files that exist in the user's project but not in the compiled
    wiki: ``tasks.md``, ``settings.gradle.kts``, ``../../sources/foo.md``,
    absolute ``/Users/…/…``, IDE config like ``.kiro/steering/*``.  We'd
    rather keep the filename visible as plain text and drop the (broken)
    anchor than ship a 404.
    """
    # Strip trailing #anchor / ?query.  Keep leading ./ and ../
    # prefixes — the classifier uses them to recognise wiki-layer paths.
    path = href.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return False
    if path.startswith(("http:", "https:", "mailto:")):
        return False
    # Absolute host paths (e.g. /Users/USER/.claude/...) — always dead.
    if path.startswith(("/Users/", "/home/", "/root/", "/tmp/")):
        return True
    # Regular site-absolute paths shouldn't be stripped.
    if path.startswith("/"):
        return False
    # Drop ONLY the ``./`` prefix (strip explicit "./" once, keep "../").
    if path.startswith("./"):
        path = path[2:]
    # For the basename check we want the last path segment.
    base = path.rsplit("/", 1)[-1]
    if base in _SESSION_LOCAL_BASENAMES:
        return True
    # ../../sources/ and ../../wiki/ — wiki-layer targets that don't
    # compile as standalone site pages.
    if path.startswith((
        "../../sources/", "../sources/", "sources/",
        "../../wiki/", "../../entities/", "../../concepts/",
        "../../syntheses/",
    )):
        return True
    # IDE / project config dirs that live in the user's repo but not ours.
    if path.startswith((
        ".kiro/", ".cursor/", ".vscode/", ".idea/",
        ".claude/", ".codex/",
        "infra/", "gradle/", "scripts/",
        "examples/demo-", "docs/images",
    )):
        return True
    # Bare gradle / kts / source-build files typed without ../../.
    if "/" not in path and path.endswith((
        ".kts", ".gradle", ".sbt", ".mill", ".properties",
        ".sh", ".bat", ".ps1",
        ".conf", ".ini", ".cfg",
        ".env",
    )):
        return True
    if path.endswith((
        "gradlew", "gradlew.bat", "CODEOWNERS",
    )):
        return True
    # Bare .txt / .json / .yaml / .md / .html siblings seen in session
    # transcripts (e.g. "01 Summary.txt") — the session body inlined
    # filenames.  Only strip bare filenames without any directory;
    # path-prefixed refs might still be legit.
    if "/" not in path and base.endswith((
        ".txt", ".json", ".csv", ".yaml", ".yml", ".md", ".html",
    )):
        return True
    return False


def strip_dead_session_refs(html_body: str) -> str:
    """Unwrap anchors that point at session-local dead refs (#336).

    Replaces ``<a href="tasks.md" ...>TASKS</a>`` with
    ``<span class="session-ref dead-link">TASKS</span>``.  The text
    stays visible (users still see the filename that was referenced)
    but the link is gone, so the compiled site stops reporting a 404.
    """
    # Lazy import to avoid a hard markdown dep at module import time.
    import re as _re

    # Match anchors we'd otherwise route.  Skip anchors already rewritten
    # to absolute URLs (github.com / external).
    anchor_re = _re.compile(
        r'<a\s+([^>]*?)href="([^"]+)"([^>]*)>(.*?)</a>',
        _re.IGNORECASE | _re.DOTALL,
    )

    def _sub(m: _re.Match) -> str:
        pre, href, post, inner = m.group(1), m.group(2), m.group(3), m.group(4)
        # Respect absolute + mailto + in-page anchors — they're never dead.
        if href.startswith(("http:", "https:", "mailto:", "#")):
            return m.group(0)
        if not _is_session_local_ref(href):
            return m.group(0)
        # Preserve the inner text; drop the anchor.  Add title attribute
        # so hover reveals what the original href was.
        import html as _html
        title = _html.escape(href)
        return (
            f'<span class="session-ref dead-link" title="session-local ref: {title}">'
            f'{inner}</span>'
        )

    return anchor_re.sub(_sub, html_body)


def rewrite_source_code_links_to_github(html_body: str) -> str:
    """Rewrite ``href`` values pointing at source code or repo-root
    files to absolute GitHub URLs (#270).

    Runs BEFORE ``rewrite_md_links_to_html`` because we want
    ``README.md`` to become a GitHub link, not ``README.html``.
    """
    def _sub(m: re.Match) -> str:
        href = m.group(1)
        new = _rewrite_one_to_github(href)
        return m.group(0) if new is None else f'href="{new}"'

    return _CODE_OR_ROOT_HREF_RE.sub(_sub, html_body)


def rewrite_md_links_to_html(html_body: str) -> str:
    """Rewrite every internal ``href="foo.md"`` (and ``foo.md#anchor``)
    to ``foo.html``. Leaves external URLs untouched.

    The docs compiler writes ``.html`` files, but Markdown source
    authors use ``.md`` so the links work on GitHub too. This one
    pass reconciles the two.

    #270: callers should now run
    :func:`rewrite_source_code_links_to_github` BEFORE this function
    so repo-root ``.md`` files (README, CONTRIBUTING, etc.) get routed
    to GitHub instead of becoming dangling ``.html`` links.
    """
    return _MD_HREF_RE.sub(
        lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"',
        html_body,
    )


def _first_paragraph(body: str) -> str:
    """First non-heading paragraph; used as the ``<meta description>``."""
    for block in body.split("\n\n"):
        stripped = block.strip()
        if stripped and not stripped.startswith(("#", "---")):
            return re.sub(r"\s+", " ", stripped)
    return ""


# ─── Fallbacks (used when this module is imported without build.py) ──


def _fallback_md_to_html(body: str) -> str:
    """Cheap stdlib-only markdown when the real converter isn't wired."""
    # Escape everything, then turn the most common constructs into tags.
    escaped = html.escape(body)
    # fenced code blocks
    escaped = re.sub(
        r"```(\w*)\n(.*?)```",
        lambda m: f'<pre><code class="language-{m.group(1) or "text"}">{m.group(2)}</code></pre>',
        escaped,
        flags=re.DOTALL,
    )
    # headings
    for level in range(6, 0, -1):
        escaped = re.sub(
            rf"^{'#' * level}\s+(.+)$",
            rf"<h{level}>\1</h{level}>",
            escaped,
            flags=re.MULTILINE,
        )
    # inline code
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    # Preserve paragraphs
    blocks = [
        b.strip() for b in escaped.split("\n\n") if b.strip()
    ]
    wrapped = []
    for block in blocks:
        if block.startswith(("<h", "<pre", "<ul", "<ol", "<table")):
            wrapped.append(block)
        else:
            wrapped.append(f"<p>{block}</p>")
    return "\n".join(wrapped)


def _fallback_page_head(title: str, description: str, css_prefix: str = "") -> str:
    return (
        "<!DOCTYPE html><html><head>"
        f"<title>{html.escape(title)}</title>"
        f'<meta name="description" content="{html.escape(description)}">'
        f'<link rel="stylesheet" href="{css_prefix}style.css">'
        "</head><body>"
    )
