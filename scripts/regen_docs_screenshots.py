"""#632: regenerate `docs/images/*.png` from a live llmwiki build.

The README + docs reference six canonical screenshots (home, sessions
index, session detail, changelog, projects index, model card). They're
hand-maintained which means they drift out of sync with the actual
emitted UI on every theme/CSS change.

This script:

  1. Spins up the same seeded e2e harness so we always have a known-
     good corpus to screenshot (no dependency on the user's real
     `~/.claude/projects/`).
  2. Walks a deterministic route through the site with Playwright,
     captures `docs/images/<name>.png` at 1280×800 in the dark theme.
  3. Reports a one-line diff (`changed N images / kept M`) so the
     person running it sees what's about to be committed.

Run locally:

    python3 scripts/regen_docs_screenshots.py

Run from CI on demand via `.github/workflows/regen-screenshots.yml`
(workflow_dispatch only — never auto-fires) so a maintainer can
trigger a refresh and review the diff in a follow-up PR.

The script is intentionally idempotent: re-running with no UI changes
produces no diff. PNG output is `optimize=True` so commits stay small.
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
DOCS_IMAGES = REPO_ROOT / "docs" / "images"

# Each entry: (output filename, URL path, optional pre-screenshot JS to run).
# Add or reorder as the README screenshot set evolves; this file is
# the single source of truth for what canonical screenshots ship.
ROUTES = [
    ("home.png", "/index.html", None),
    ("projects.png", "/projects/index.html", None),
    ("sessions.png", "/sessions/index.html", None),
    ("changelog.png", "/changelog.html", None),
]


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _serve(port: int) -> ThreadingHTTPServer:
    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(SITE_DIR), **kw)
        def log_message(self, *args):  # quiet
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _build_site() -> None:
    """Force a fresh build into ./site so we screenshot the latest."""
    subprocess.run(
        [sys.executable, "-m", "llmwiki", "build"],
        cwd=str(REPO_ROOT),
        check=True,
    )


def _capture(port: int, theme: str) -> dict[str, bool]:
    """Returns {filename: True if changed else False}."""
    from playwright.sync_api import sync_playwright

    DOCS_IMAGES.mkdir(parents=True, exist_ok=True)
    base = f"http://127.0.0.1:{port}"
    changed: dict[str, bool] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        # Pre-set theme via init script so it's set before first paint.
        ctx.add_init_script(
            f"try {{ localStorage.setItem('llmwiki-theme', {theme!r}); }} catch (e) {{}}"
        )
        page = ctx.new_page()

        for fname, path, pre_js in ROUTES:
            page.goto(f"{base}{path}", wait_until="networkidle")
            if pre_js:
                page.evaluate(pre_js)
                page.wait_for_timeout(300)
            out = DOCS_IMAGES / fname
            existing_bytes = out.read_bytes() if out.is_file() else b""
            page.screenshot(path=str(out), full_page=False)
            new_bytes = out.read_bytes()
            changed[fname] = new_bytes != existing_bytes

        browser.close()
    return changed


def main() -> int:
    p = argparse.ArgumentParser(description="Regenerate docs/images/*.png")
    p.add_argument("--theme", choices=("light", "dark"), default="dark")
    p.add_argument("--no-build", action="store_true",
                   help="Reuse the existing ./site directory")
    args = p.parse_args()

    if not args.no_build:
        print("Building site …")
        _build_site()
    if not SITE_DIR.is_dir():
        print(f"error: {SITE_DIR} doesn't exist — pass --no-build only after a successful build", file=sys.stderr)
        return 2

    port = _free_port()
    srv = _serve(port)
    time.sleep(0.2)
    try:
        result = _capture(port, args.theme)
    finally:
        srv.shutdown()

    changed = [k for k, v in result.items() if v]
    kept = [k for k, v in result.items() if not v]
    print(f"\n{'changed' if changed else 'no changes'}: {len(changed)} / kept: {len(kept)}")
    for fname in changed:
        print(f"  changed: docs/images/{fname}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
