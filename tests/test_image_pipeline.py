"""Tests for llmwiki.image_pipeline (v0.7 · #96).

Covers:
- find_remote_images: https URLs found, local paths skipped, edge cases
- download_image: hash-based filenames, graceful failure, caching
- rewrite_image_refs: URL replacement, local refs untouched
- process_markdown_images: dry_run counts, full rewrite, dedup, edge cases
"""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki.image_pipeline import (
    _DEFAULT_EXT,
    _ext_from_url,
    _hash_url,
    download_image,
    find_remote_images,
    process_markdown_images,
    rewrite_image_refs,
)


# ─── helpers ──────────────────────────────────────────────────────────────

def _sha(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


# ─── find_remote_images ──────────────────────────────────────────────────

class TestFindRemoteImages:
    def test_finds_https_url(self):
        md = "![diagram](https://example.com/pic.png)"
        result = find_remote_images(md)
        assert len(result) == 1
        url, alt, line = result[0]
        assert url == "https://example.com/pic.png"
        assert alt == "diagram"
        assert line == 1

    def test_finds_http_url(self):
        md = "![](http://example.com/image.jpg)"
        result = find_remote_images(md)
        assert len(result) == 1
        assert result[0][0] == "http://example.com/image.jpg"
        assert result[0][1] == ""

    def test_skips_local_path(self):
        md = "![logo](./images/logo.png)"
        assert find_remote_images(md) == []

    def test_skips_relative_path(self):
        md = "![logo](assets/logo.png)"
        assert find_remote_images(md) == []

    def test_empty_markdown(self):
        assert find_remote_images("") == []

    def test_no_images(self):
        md = "Just some text with [a link](https://example.com) but no images."
        assert find_remote_images(md) == []

    def test_multiple_images(self):
        md = textwrap.dedent("""\
            # Heading

            ![one](https://a.com/1.png)

            Some text.

            ![two](https://b.com/2.jpg)
        """)
        result = find_remote_images(md)
        assert len(result) == 2
        assert result[0][0] == "https://a.com/1.png"
        assert result[0][2] == 3
        assert result[1][0] == "https://b.com/2.jpg"
        assert result[1][2] == 7

    def test_multiple_images_on_same_line(self):
        md = "![a](https://x.com/a.png) and ![b](https://x.com/b.png)"
        result = find_remote_images(md)
        assert len(result) == 2

    def test_deduplicates_same_url(self):
        md = "![a](https://x.com/dup.png)\n![b](https://x.com/dup.png)"
        result = find_remote_images(md)
        assert len(result) == 1

    def test_image_with_title(self):
        md = '![alt](https://example.com/pic.png "A title")'
        result = find_remote_images(md)
        assert len(result) == 1
        assert result[0][0] == "https://example.com/pic.png"

    def test_url_with_query_params(self):
        md = "![](https://example.com/img.png?w=100&h=200)"
        result = find_remote_images(md)
        assert len(result) == 1
        assert "w=100" in result[0][0]


# ─── _ext_from_url ───────────────────────────────────────────────────────

class TestExtFromUrl:
    def test_png(self):
        assert _ext_from_url("https://example.com/pic.png") == ".png"

    def test_jpg(self):
        assert _ext_from_url("https://example.com/pic.jpg") == ".jpg"

    def test_jpeg(self):
        assert _ext_from_url("https://example.com/pic.JPEG") == ".jpeg"

    def test_svg(self):
        assert _ext_from_url("https://example.com/diagram.svg") == ".svg"

    def test_no_extension(self):
        assert _ext_from_url("https://example.com/image") == _DEFAULT_EXT

    def test_unknown_extension(self):
        assert _ext_from_url("https://example.com/file.xyz") == _DEFAULT_EXT

    def test_url_with_query(self):
        assert _ext_from_url("https://example.com/pic.jpg?size=lg") == ".jpg"

    def test_url_with_fragment(self):
        assert _ext_from_url("https://example.com/pic.webp#section") == ".webp"

    def test_trailing_slash(self):
        assert _ext_from_url("https://example.com/images/") == _DEFAULT_EXT


# ─── _hash_url ───────────────────────────────────────────────────────────

class TestHashUrl:
    def test_returns_16_hex_chars(self):
        h = _hash_url("https://example.com/img.png")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        url = "https://example.com/img.png"
        assert _hash_url(url) == _hash_url(url)

    def test_different_urls_different_hashes(self):
        assert _hash_url("https://a.com/1.png") != _hash_url("https://a.com/2.png")


# ─── download_image ──────────────────────────────────────────────────────

class TestDownloadImage:
    def test_successful_download(self, tmp_path):
        """Mock urllib to simulate a successful download."""
        url = "https://example.com/photo.jpg"
        assets = tmp_path / "assets"
        fake_data = b"\xff\xd8\xff\xe0fake-jpeg-bytes"

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_data
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("llmwiki.image_pipeline.urllib.request.urlopen", return_value=mock_resp):
            result = download_image(url, assets)

        assert result is not None
        assert result.exists()
        assert result.name == f"{_sha(url)}.jpg"
        assert result.read_bytes() == fake_data

    def test_hash_based_filename(self, tmp_path):
        url = "https://cdn.example.com/deep/path/image.png"
        assets = tmp_path / "assets"
        expected_name = f"{_sha(url)}.png"

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"fake-png"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("llmwiki.image_pipeline.urllib.request.urlopen", return_value=mock_resp):
            result = download_image(url, assets)

        assert result is not None
        assert result.name == expected_name

    def test_graceful_failure_on_network_error(self, tmp_path):
        """Network errors return None, never raise."""
        url = "https://does-not-exist.example.com/broken.png"
        assets = tmp_path / "assets"

        import urllib.error

        with patch(
            "llmwiki.image_pipeline.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            result = download_image(url, assets)

        assert result is None

    def test_graceful_failure_on_http_error(self, tmp_path):
        url = "https://example.com/404.png"
        assets = tmp_path / "assets"

        import urllib.error

        with patch(
            "llmwiki.image_pipeline.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(url, 404, "Not Found", {}, None),
        ):
            result = download_image(url, assets)

        assert result is None

    def test_creates_assets_dir(self, tmp_path):
        url = "https://example.com/pic.png"
        assets = tmp_path / "deep" / "nested" / "assets"
        assert not assets.exists()

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"data"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("llmwiki.image_pipeline.urllib.request.urlopen", return_value=mock_resp):
            result = download_image(url, assets)

        assert assets.exists()
        assert result is not None

    def test_skips_if_already_cached(self, tmp_path):
        url = "https://example.com/cached.png"
        assets = tmp_path / "assets"
        assets.mkdir()
        # Pre-create the cached file.
        cached = assets / f"{_sha(url)}.png"
        cached.write_bytes(b"already-here")

        with patch("llmwiki.image_pipeline.urllib.request.urlopen") as mock_open:
            result = download_image(url, assets)

        # Should NOT have called urlopen — served from cache.
        mock_open.assert_not_called()
        assert result == cached

    def test_url_with_no_extension_gets_default(self, tmp_path):
        url = "https://example.com/image-no-ext"
        assets = tmp_path / "assets"

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"data"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("llmwiki.image_pipeline.urllib.request.urlopen", return_value=mock_resp):
            result = download_image(url, assets)

        assert result is not None
        assert result.suffix == _DEFAULT_EXT


# ─── rewrite_image_refs ──────────────────────────────────────────────────

class TestRewriteImageRefs:
    def test_replaces_remote_url(self):
        md = "![pic](https://example.com/img.png)"
        mapping = {"https://example.com/img.png": "assets/abc123.png"}
        result = rewrite_image_refs(md, mapping)
        assert result == "![pic](assets/abc123.png)"

    def test_leaves_local_refs_untouched(self):
        md = "![pic](./local/image.png)"
        result = rewrite_image_refs(md, {})
        assert result == md

    def test_leaves_unmapped_urls_untouched(self):
        md = "![pic](https://example.com/not-mapped.png)"
        result = rewrite_image_refs(md, {})
        assert result == md

    def test_handles_multiple_replacements(self):
        md = "![a](https://a.com/1.png)\n![b](https://b.com/2.jpg)"
        mapping = {
            "https://a.com/1.png": "assets/aaa.png",
            "https://b.com/2.jpg": "assets/bbb.jpg",
        }
        result = rewrite_image_refs(md, mapping)
        assert "assets/aaa.png" in result
        assert "assets/bbb.jpg" in result
        assert "https://a.com" not in result
        assert "https://b.com" not in result

    def test_preserves_alt_text(self):
        md = "![complex alt text here](https://example.com/img.png)"
        mapping = {"https://example.com/img.png": "assets/x.png"}
        result = rewrite_image_refs(md, mapping)
        assert "![complex alt text here](assets/x.png)" == result

    def test_mixed_local_and_remote(self):
        md = "![local](./a.png)\n![remote](https://r.com/b.png)\n![local2](img/c.jpg)"
        mapping = {"https://r.com/b.png": "assets/b.png"}
        result = rewrite_image_refs(md, mapping)
        assert "![local](./a.png)" in result
        assert "![remote](assets/b.png)" in result
        assert "![local2](img/c.jpg)" in result


# ─── process_markdown_images ─────────────────────────────────────────────

class TestProcessMarkdownImages:
    def test_dry_run_counts_but_does_not_modify(self, tmp_path):
        md_content = "![a](https://example.com/a.png)\n![b](https://example.com/b.jpg)"
        md_file = tmp_path / "test.md"
        md_file.write_text(md_content, encoding="utf-8")
        assets = tmp_path / "assets"

        dl, fail, skip = process_markdown_images(md_file, assets, dry_run=True)

        # Should count 2 as "would download" (assets dir doesn't exist).
        assert dl == 2
        assert fail == 0
        assert skip == 0
        # File content unchanged.
        assert md_file.read_text(encoding="utf-8") == md_content

    def test_dry_run_detects_cached(self, tmp_path):
        url = "https://example.com/cached.png"
        md_content = f"![x]({url})"
        md_file = tmp_path / "test.md"
        md_file.write_text(md_content, encoding="utf-8")
        assets = tmp_path / "assets"
        assets.mkdir()
        # Pre-create cached file.
        cached = assets / f"{_sha(url)}.png"
        cached.write_bytes(b"cached-data")

        dl, fail, skip = process_markdown_images(md_file, assets, dry_run=True)
        assert dl == 0
        assert skip == 1

    def test_empty_markdown(self, tmp_path):
        md_file = tmp_path / "empty.md"
        md_file.write_text("", encoding="utf-8")
        assets = tmp_path / "assets"

        dl, fail, skip = process_markdown_images(md_file, assets)
        assert (dl, fail, skip) == (0, 0, 0)

    def test_markdown_with_only_local_images(self, tmp_path):
        md_file = tmp_path / "local.md"
        md_file.write_text("![a](./local.png)\n![b](img/other.jpg)", encoding="utf-8")
        assets = tmp_path / "assets"

        dl, fail, skip = process_markdown_images(md_file, assets)
        assert (dl, fail, skip) == (0, 0, 0)

    def test_full_pipeline_rewrites_file(self, tmp_path):
        """End-to-end: download succeeds, file is rewritten."""
        url = "https://example.com/photo.png"
        md_content = f"# Title\n\n![photo]({url})\n\nEnd."
        md_file = tmp_path / "session.md"
        md_file.write_text(md_content, encoding="utf-8")
        assets = tmp_path / "assets"

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"fake-img-data"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("llmwiki.image_pipeline.urllib.request.urlopen", return_value=mock_resp), \
             patch("llmwiki.image_pipeline.time.sleep"):
            dl, fail, skip = process_markdown_images(md_file, assets)

        assert dl == 1
        assert fail == 0
        new_text = md_file.read_text(encoding="utf-8")
        assert url not in new_text
        assert f"{_sha(url)}.png" in new_text

    def test_failed_download_keeps_original_url(self, tmp_path):
        url = "https://example.com/broken.png"
        md_content = f"![x]({url})"
        md_file = tmp_path / "test.md"
        md_file.write_text(md_content, encoding="utf-8")
        assets = tmp_path / "assets"

        import urllib.error

        with patch(
            "llmwiki.image_pipeline.urllib.request.urlopen",
            side_effect=urllib.error.URLError("fail"),
        ), patch("llmwiki.image_pipeline.time.sleep"):
            dl, fail, skip = process_markdown_images(md_file, assets)

        assert dl == 0
        assert fail == 1
        # Original URL preserved in the file.
        assert md_file.read_text(encoding="utf-8") == md_content

    def test_duplicate_urls_deduped_via_hash(self, tmp_path):
        """Same URL appearing twice: only one download, file has both rewritten."""
        url = "https://example.com/dup.png"
        md_content = f"![a]({url})\n![b]({url})"
        md_file = tmp_path / "test.md"
        md_file.write_text(md_content, encoding="utf-8")
        assets = tmp_path / "assets"

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"img"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("llmwiki.image_pipeline.urllib.request.urlopen", return_value=mock_resp), \
             patch("llmwiki.image_pipeline.time.sleep"):
            dl, fail, skip = process_markdown_images(md_file, assets)

        # find_remote_images deduplicates, so only 1 unique URL found.
        assert dl == 1
        assert fail == 0
        new_text = md_file.read_text(encoding="utf-8")
        # Both occurrences should be rewritten.
        assert url not in new_text

    def test_rate_limit_sleep_called(self, tmp_path):
        """Verify time.sleep(1) is called between downloads."""
        md_content = (
            "![a](https://example.com/a.png)\n"
            "![b](https://example.com/b.png)\n"
            "![c](https://example.com/c.png)"
        )
        md_file = tmp_path / "test.md"
        md_file.write_text(md_content, encoding="utf-8")
        assets = tmp_path / "assets"

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"data"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("llmwiki.image_pipeline.urllib.request.urlopen", return_value=mock_resp), \
             patch("llmwiki.image_pipeline.time.sleep") as mock_sleep:
            process_markdown_images(md_file, assets)

        # Sleep called between downloads (not before the first one).
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1)
