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

    for page in iter_docs_pages(docs_dir):
        meta_strip = render_meta_strip(page.body) if page.is_shell else ""
        body_without_meta = (
            _strip_meta_lines(page.body) if page.is_shell else page.body
        )
        body_html = md_to_html(body_without_meta)

        # Splice the meta strip right after the <h1>…</h1> line.
        if meta_strip:
            body_html = body_html.replace("</h1>", "</h1>\n" + meta_strip, 1)

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

        html_doc = (
            page_head(page.title, description, css_prefix=css_prefix)
            + nav
            + f'<main id="main-content" class="{shell_class}">'
            + _breadcrumb(page)
            + body_html
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


def rewrite_md_links_to_html(html_body: str) -> str:
    """Rewrite every internal ``href="foo.md"`` (and ``foo.md#anchor``)
    to ``foo.html``. Leaves external URLs untouched.

    The docs compiler writes ``.html`` files, but Markdown source
    authors use ``.md`` so the links work on GitHub too. This one
    pass reconciles the two.
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
