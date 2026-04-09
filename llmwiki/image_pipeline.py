"""Image pipeline — download remote images and rewrite markdown refs to local paths.

Stdlib-only. Uses ``urllib.request`` for downloads and ``hashlib`` for
content-addressable filenames (``sha256(url)[:16].<ext>``).

Usage from CLI:
    llmwiki sync --download-images

Functions:
    find_remote_images   — scan markdown for ``![alt](https://...)`` patterns
    download_image       — fetch one URL to *assets_dir*, return local Path
    rewrite_image_refs   — replace URLs in markdown with local paths
    process_markdown_images — orchestrate find → download → rewrite for one file
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Matches ![alt text](https://...) — only remote (http/https) URLs.
# Allows optional title: ![alt](url "title")
_IMAGE_RE = re.compile(
    r"!\[([^\]]*)\]"           # ![alt text]
    r"\("                       # (
    r"(https?://[^\s\)\"]+)"   # URL (http or https, no spaces/parens/quotes)
    r'(?:\s+"[^"]*")?'         # optional "title"
    r"\)",                      # )
)

# Known image extensions (used to infer extension from URL path).
_IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".bmp", ".ico", ".tiff", ".tif", ".avif",
}

# Default extension when URL path has none or an unrecognised one.
_DEFAULT_EXT = ".png"

# Rate-limit: minimum seconds between consecutive downloads.
_RATE_LIMIT_SECONDS = 1


def _ext_from_url(url: str) -> str:
    """Derive a file extension from a URL, falling back to .png."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if "." in path.split("/")[-1]:
        ext = "." + path.rsplit(".", 1)[-1].lower()
        # Strip query-string fragments that may have leaked in.
        ext = ext.split("?")[0].split("#")[0]
        if ext in _IMAGE_EXTS:
            return ext
    return _DEFAULT_EXT


def _hash_url(url: str) -> str:
    """Return the first 16 hex chars of the SHA-256 of *url*."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def find_remote_images(markdown_text: str) -> list[tuple[str, str, int]]:
    """Find all remote image references in *markdown_text*.

    Returns a list of ``(original_url, alt_text, line_number)`` tuples.
    Line numbers are 1-based.
    """
    results: list[tuple[str, str, int]] = []
    seen_urls: set[str] = set()
    for line_no, line in enumerate(markdown_text.splitlines(), start=1):
        for match in _IMAGE_RE.finditer(line):
            alt = match.group(1)
            url = match.group(2)
            if url not in seen_urls:
                results.append((url, alt, line_no))
                seen_urls.add(url)
    return results


def download_image(
    url: str,
    assets_dir: Path,
    timeout: int = 10,
) -> Optional[Path]:
    """Download a single remote image to *assets_dir*.

    Filename is ``sha256(url)[:16].<ext>``.  Returns the ``Path`` on
    success, or ``None`` on any failure (network, timeout, HTTP error).
    Never raises — failures are logged as warnings.
    """
    assets_dir.mkdir(parents=True, exist_ok=True)
    ext = _ext_from_url(url)
    filename = f"{_hash_url(url)}{ext}"
    dest = assets_dir / filename

    # Skip if already downloaded (content-addressable dedup).
    if dest.exists() and dest.stat().st_size > 0:
        logger.debug("already cached: %s -> %s", url, dest)
        return dest

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "llmwiki/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        dest.write_bytes(data)
        logger.info("downloaded: %s -> %s (%d bytes)", url, dest.name, len(data))
        return dest
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        logger.warning("failed to download %s: %s", url, exc)
        return None


def rewrite_image_refs(
    markdown_text: str,
    url_to_local_map: dict[str, str],
) -> str:
    """Replace remote image URLs in *markdown_text* with local paths.

    *url_to_local_map* maps original URLs to the local relative path that
    should replace them.  URLs not in the map are left untouched.
    """
    def _replacer(m: re.Match) -> str:
        alt = m.group(1)
        url = m.group(2)
        local = url_to_local_map.get(url)
        if local is not None:
            return f"![{alt}]({local})"
        return m.group(0)

    return _IMAGE_RE.sub(_replacer, markdown_text)


def process_markdown_images(
    md_path: Path,
    assets_dir: Path,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Process one markdown file: find remote images, download, rewrite.

    Returns ``(downloaded_count, failed_count, skipped_count)``.

    *skipped_count* includes images that were already cached locally.

    When *dry_run* is ``True``, images are counted but NOT downloaded
    and the markdown file is NOT rewritten.
    """
    text = md_path.read_text(encoding="utf-8")
    images = find_remote_images(text)

    if not images:
        return (0, 0, 0)

    downloaded = 0
    failed = 0
    skipped = 0
    url_to_local: dict[str, str] = {}

    for i, (url, _alt, _line) in enumerate(images):
        if dry_run:
            # In dry-run mode, just count them as "would download".
            ext = _ext_from_url(url)
            filename = f"{_hash_url(url)}{ext}"
            dest = assets_dir / filename
            if dest.exists() and dest.stat().st_size > 0:
                skipped += 1
            else:
                downloaded += 1
            continue

        # Rate limit: sleep before every download except the first.
        if i > 0:
            time.sleep(_RATE_LIMIT_SECONDS)

        dest = download_image(url, assets_dir)
        if dest is not None:
            # Build a relative path from the markdown file to the asset.
            try:
                rel = dest.relative_to(md_path.parent)
            except ValueError:
                # Assets dir is not under the markdown's parent — use an
                # absolute-ish path relative to the repo raw/ root.
                rel = Path("assets") / dest.name
            url_to_local[url] = str(rel)
            # Distinguish fresh download vs cache hit.
            downloaded += 1
        else:
            failed += 1

    # Rewrite only when we actually downloaded something (not dry-run).
    if not dry_run and url_to_local:
        new_text = rewrite_image_refs(text, url_to_local)
        md_path.write_text(new_text, encoding="utf-8")

    return (downloaded, failed, skipped)
