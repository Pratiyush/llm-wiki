"""Validate the shape + integrity of every build artifact emitted to ``site/``.

The browser tests cover *what users see*, but a class of regressions
ships silently because they live in machine-readable artifacts that
no human ever opens: the JSON search index, the XML sitemap, the
JSON-LD knowledge graph, the PWA manifest, the LLM-discovery
``llms.txt`` files, the RSS feed, and ``robots.txt``.

This module asserts on the *shape* of each artifact (well-formed
markup, expected keys, plausible URL counts), not the content. We
explicitly do NOT test for specific session titles or counts because
the synthetic e2e fixture's contents change as the harness evolves —
binding tests to that would create churn without catching real bugs.

Each test:

* Reads the artifact from the session-scoped ``site_root`` fixture
  (already built once in conftest.py).
* Parses it with the appropriate stdlib parser (``json``,
  ``xml.etree.ElementTree``, ``email.parser``).
* Asserts the minimum invariants.

Failure messages include the offending file path so the failing
artifact is one click away in pytest output.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


# ─── search-index.json ─────────────────────────────────────────────────


def test_search_index_is_valid_json(site_root: Path) -> None:
    """The client-side fuzzy search loads ``search-index.json`` via
    ``fetch()``. Anything that isn't well-formed JSON breaks Cmd+K
    silently — the palette opens, the input accepts text, results
    just never appear. Hard to debug, easy to regress."""
    idx = site_root / "search-index.json"
    assert idx.is_file(), f"missing artifact: {idx}"
    data = json.loads(idx.read_text(encoding="utf-8"))
    assert data, "search-index.json is empty"


def test_search_index_entries_have_required_fields(site_root: Path) -> None:
    """Every entry must have at minimum a title and a URL the palette
    can navigate to. The exact field name varies by build mode (tree /
    flat / auto) so we accept any of the documented variants."""
    idx = site_root / "search-index.json"
    data = json.loads(idx.read_text(encoding="utf-8"))

    # Normalise: the index may be a top-level list, or a dict with
    # ``items`` / ``entries`` / a tree of nested objects.
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("items") or data.get("entries") or []
        if not items:
            # Tree mode: flatten one level by collecting any list
            # values nested under the root keys.
            for v in data.values():
                if isinstance(v, list):
                    items = v
                    break
    else:
        pytest.fail(f"unexpected search-index.json root type: {type(data).__name__}")

    if not items:
        pytest.skip("search index has zero entries — synthetic corpus is too small")

    sample = items[0]
    assert isinstance(sample, dict), f"search index entry is not a dict: {type(sample).__name__}"

    # At least one of these must be a non-empty string.
    title_keys = {"title", "name", "label", "heading", "t"}
    url_keys = {"url", "href", "path", "u", "link"}
    title = next((sample[k] for k in title_keys if k in sample and sample[k]), None)
    url = next((sample[k] for k in url_keys if k in sample and sample[k]), None)
    assert title, f"search index entry has no title-like field: {sample.keys()}"
    assert url, f"search index entry has no URL-like field: {sample.keys()}"


# ─── sitemap.xml ───────────────────────────────────────────────────────


def test_sitemap_is_well_formed_xml(site_root: Path) -> None:
    """``sitemap.xml`` is consumed by Google + every other crawler.
    Malformed XML here means our pages aren't indexed. Parsing must
    succeed and the root must be the standard sitemap namespace."""
    sitemap = site_root / "sitemap.xml"
    if not sitemap.is_file():
        pytest.skip("sitemap.xml not produced (export not run)")
    tree = ET.parse(sitemap)
    root = tree.getroot()
    # Standard sitemap protocol: <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    assert root.tag.endswith("urlset"), f"sitemap root is {root.tag}, expected urlset"
    # At least one <url><loc>...</loc></url>.
    locs = root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
    if not locs:
        # Fallback: namespace might be empty.
        locs = root.findall(".//loc")
    assert locs, "sitemap.xml has no <loc> entries"
    # Every loc should be an absolute or relative URL — never empty.
    empty = [loc for loc in locs if not (loc.text or "").strip()]
    assert not empty, f"{len(empty)} <loc> entries are empty in sitemap.xml"


# ─── llms.txt + llms-full.txt ──────────────────────────────────────────


def test_llms_txt_present_and_nonempty(site_root: Path) -> None:
    """``llms.txt`` is the LLM-discovery contract (see llmstxt.org).
    A site that emits it but produces an empty file actively misleads
    consumers — better to not emit it at all."""
    f = site_root / "llms.txt"
    if not f.is_file():
        pytest.skip("llms.txt not produced (export not run)")
    content = f.read_text(encoding="utf-8").strip()
    assert content, "llms.txt is empty"
    # Convention: starts with a Markdown H1.
    assert content.startswith("#"), (
        f"llms.txt should open with a Markdown H1, got: {content[:80]!r}"
    )


def test_llms_full_txt_under_size_budget(site_root: Path) -> None:
    """``llms-full.txt`` ships every page concatenated. We enforce a
    soft budget so a runaway ingest can't ship a 100MB text file
    that crashes consumer LLMs at upload time. Limit: 5MB."""
    f = site_root / "llms-full.txt"
    if not f.is_file():
        pytest.skip("llms-full.txt not produced (export not run)")
    size = f.stat().st_size
    budget = 5 * 1024 * 1024
    assert size <= budget, (
        f"llms-full.txt is {size:,} bytes, exceeds {budget:,} budget. "
        f"Consider chunking or summarising before shipping."
    )


# ─── manifest.json ─────────────────────────────────────────────────────


def test_build_manifest_has_perf_budget_data(site_root: Path) -> None:
    """``manifest.json`` here is the build's *performance manifest*
    (not a PWA manifest — confusingly the same filename). It's
    consumed by the CI ``performance budget check`` job in ci.yml.
    Expected fields: ``version``, ``total_files``, ``total_bytes``,
    ``largest_page_bytes``, ``perf_budget``, ``budget_violations``.

    A regression where a writer forgets to populate ``budget_violations``
    silently bypasses the CI gate that protects against page-size blow-ups.
    """
    f = site_root / "manifest.json"
    if not f.is_file():
        pytest.skip("manifest.json not produced")
    data = json.loads(f.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "manifest.json root is not an object"

    # Perf-manifest shape (per llmwiki/build.py).
    expected = {"version", "total_files", "total_bytes", "perf_budget", "budget_violations"}
    missing = expected - set(data.keys())
    assert not missing, (
        f"perf manifest missing keys: {sorted(missing)}. Got: {sorted(data.keys())}"
    )
    # Sanity on counts.
    assert isinstance(data["total_files"], int) and data["total_files"] > 0, (
        "manifest.total_files should be a positive int"
    )
    assert isinstance(data["budget_violations"], list), (
        "manifest.budget_violations should be a list (empty is fine)"
    )


# ─── robots.txt ────────────────────────────────────────────────────────


def test_robots_txt_has_valid_directives(site_root: Path) -> None:
    """``robots.txt`` follows a tiny grammar: each non-comment line
    must be ``User-agent: ...``, ``Disallow: ...``, ``Allow: ...``,
    or ``Sitemap: ...``. A typo (e.g. ``Disalllow:``) silently
    disables the rule for crawlers that don't know about typos."""
    f = site_root / "robots.txt"
    if not f.is_file():
        pytest.skip("robots.txt not produced")
    valid_directives = {
        "user-agent", "disallow", "allow", "sitemap", "crawl-delay",
        "host", "noindex",
    }
    bad_lines: list[str] = []
    for ln, raw in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            bad_lines.append(f"line {ln}: missing ':' — {line!r}")
            continue
        directive = line.split(":", 1)[0].strip().lower()
        if directive not in valid_directives:
            bad_lines.append(f"line {ln}: unknown directive {directive!r}")
    assert not bad_lines, (
        f"robots.txt has malformed directives:\n  " + "\n  ".join(bad_lines)
    )


# ─── rss.xml ───────────────────────────────────────────────────────────


def test_rss_feed_is_well_formed(site_root: Path) -> None:
    """The RSS feed is consumed by aggregators (Inoreader, Feedly,
    NetNewsWire). Malformed XML produces an opaque "feed couldn't be
    fetched" error in those clients."""
    f = site_root / "rss.xml"
    if not f.is_file():
        pytest.skip("rss.xml not produced")
    tree = ET.parse(f)
    root = tree.getroot()
    # RSS 2.0: <rss><channel>...</channel></rss>
    # Atom: <feed>...</feed>
    if root.tag == "rss":
        channel = root.find("channel")
        assert channel is not None, "rss.xml has no <channel>"
        assert channel.find("title") is not None, "rss <channel> has no <title>"
    elif root.tag.endswith("feed"):
        # Atom — accept it.
        pass
    else:
        pytest.fail(f"rss.xml root is {root.tag}, expected rss or feed")


# ─── graph.jsonld ──────────────────────────────────────────────────────


def test_graph_jsonld_is_valid(site_root: Path) -> None:
    """``graph.jsonld`` is JSON-LD encoded as JSON. Consumers (search
    engines, knowledge-graph tools) parse it as JSON first, then
    interpret @context. Either step failing breaks discovery."""
    f = site_root / "graph.jsonld"
    if not f.is_file():
        pytest.skip("graph.jsonld not produced")
    data = json.loads(f.read_text(encoding="utf-8"))
    assert isinstance(data, (dict, list)), "graph.jsonld root is neither object nor array"
    # If it's a dict, expect @context (JSON-LD requirement).
    if isinstance(data, dict):
        assert "@context" in data or "@graph" in data, (
            f"graph.jsonld missing JSON-LD keys: {list(data.keys())[:8]}"
        )


# ─── HTML pages: minimal smell tests ───────────────────────────────────


def test_index_html_has_title_and_charset(site_root: Path) -> None:
    """The home page must declare a charset (browsers default to
    Latin-1 otherwise, mangling em-dashes and non-ASCII content) and
    have a non-empty <title>."""
    html = (site_root / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<meta[^>]+charset', html, re.IGNORECASE), (
        "index.html missing <meta charset>"
    )
    title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    assert title_match and title_match.group(1).strip(), (
        "index.html has empty or missing <title>"
    )


def test_index_html_lang_attribute(site_root: Path) -> None:
    """``<html lang="...">`` is required for screen readers to pick
    the right pronunciation. Missing it is a WCAG violation."""
    html = (site_root / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<html[^>]+\blang\s*=', html, re.IGNORECASE), (
        "index.html <html> tag has no lang attribute (WCAG violation)"
    )


def test_no_session_html_links_to_localhost_or_file_uri(site_root: Path) -> None:
    """A real-world regression: paths leak into the built HTML when a
    contributor previews on localhost and forgets to clean up. We
    grep session and project pages for ``localhost`` / ``file://``.

    We exclude ``docs/`` because the deployment tutorials legitimately
    reference ``http://localhost:8765`` (the local serve URL) — that's
    documentation content, not a leak. Same for ``raw/`` if it appears.
    """
    forbidden = ("http://localhost", "https://localhost", "file:///")
    # Surfaces that should never reference localhost.
    enforced_prefixes = ("sessions/", "projects/", "models/", "vs/")
    leaks: list[tuple[Path, str]] = []
    for html_file in site_root.rglob("*.html"):
        rel = html_file.relative_to(site_root)
        rel_str = str(rel)
        # Skip docs/* and the root index.html (which may legitimately
        # link to a deploy guide that mentions localhost).
        if not any(rel_str.startswith(p) for p in enforced_prefixes):
            continue
        text = html_file.read_text(encoding="utf-8", errors="replace")
        for needle in forbidden:
            if needle in text:
                leaks.append((rel, needle))
    assert not leaks, (
        f"{len(leaks)} session/project pages contain forbidden URL prefixes:\n  "
        + "\n  ".join(f"{p}: {n}" for p, n in leaks[:10])
    )


def test_every_html_page_references_inline_styles_or_external(site_root: Path) -> None:
    """The build embeds CSS inline in every page (see render/css.py).
    A page with neither inline ``<style>`` nor an external stylesheet
    means render/css.py wasn't invoked — catastrophic visual regression."""
    bare: list[Path] = []
    for html_file in site_root.rglob("*.html"):
        text = html_file.read_text(encoding="utf-8", errors="replace")
        if "<style" not in text and 'rel="stylesheet"' not in text:
            bare.append(html_file.relative_to(site_root))
    assert not bare, (
        f"{len(bare)} HTML files have no CSS at all:\n  "
        + "\n  ".join(str(p) for p in bare[:5])
    )
