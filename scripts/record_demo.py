"""#638 + #248: scripted demo recording for the README demo GIF.

Records a polished walkthrough of the live llmwiki site using
Playwright's `page.video()` API, then optionally converts the WebM
to an animated GIF via ffmpeg. The output lives at:

  - ``docs/videos/llmwiki-demo.webm``  (raw recording)
  - ``docs/demo.gif``                  (README-embeddable GIF)

The walkthrough mirrors the manual flow from #248:

  1. Home — hero, activity heatmap, token stats, project grid
  2. Projects index — freshness badges
  3. Largest project page (llm-wiki) — sessions list
  4. Sessions index — filter bar (project, slug)
  5. Session detail — breadcrumbs + Copy as markdown
  6. Cmd+K palette — type a query, navigate via results
  7. Knowledge graph — cluster toggle
  8. Theme toggle — dark → light

Run locally (assumes a serving site at $QA_BASE_URL or 127.0.0.1:8765):

    python3 scripts/record_demo.py
    python3 scripts/record_demo.py --base-url http://127.0.0.1:8765

Run with --no-gif to skip the ffmpeg conversion (useful when ffmpeg
is unavailable in the environment).

Resolution defaults to 1280×800 to match the rest of the e2e harness.
The cursor + subtitle overlays are inlined here rather than imported
from a shared helper because this is a one-shot recording script,
not part of the test suite.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = REPO_ROOT / "docs" / "videos"
GIF_PATH = REPO_ROOT / "docs" / "demo.gif"


# JS overlays: SVG cursor follows mouse + subtitle bar above the bottom.
CURSOR_JS = r"""
() => {
  if (document.getElementById('demo-cursor')) return;
  const c = document.createElement('div');
  c.id = 'demo-cursor';
  c.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg">
    <path d="M5 3L19 12L12 13L9 20L5 3Z"
          fill="white" stroke="black" stroke-width="1.5"
          stroke-linejoin="round"/></svg>`;
  c.style.cssText = `
    position: fixed; z-index: 999999; pointer-events: none;
    width: 22px; height: 22px;
    transition: left 0.08s linear, top 0.08s linear;
    filter: drop-shadow(1px 1px 2px rgba(0,0,0,0.4));
  `;
  c.style.left = '20px'; c.style.top = '20px';
  document.body.appendChild(c);
  document.addEventListener('mousemove', (e) => {
    c.style.left = e.clientX + 'px';
    c.style.top = e.clientY + 'px';
  });
}
"""

SUBTITLE_JS = r"""
() => {
  if (document.getElementById('demo-subtitle')) return;
  const b = document.createElement('div');
  b.id = 'demo-subtitle';
  b.style.cssText = `
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 999998;
    text-align: center; padding: 14px 24px;
    background: linear-gradient(to top, rgba(0,0,0,0.85), rgba(0,0,0,0.7));
    color: white; font-family: -apple-system, system-ui, sans-serif;
    font-size: 17px; font-weight: 500; transition: opacity 0.25s;
    pointer-events: none;
  `;
  b.textContent = ''; b.style.opacity = '0';
  document.body.appendChild(b);
}
"""


def inject_overlays(page) -> None:  # type: ignore[no-untyped-def]
    page.evaluate(CURSOR_JS)
    page.evaluate(SUBTITLE_JS)


def subtitle(page, text: str, hold_ms: int = 600) -> None:  # type: ignore[no-untyped-def]
    page.evaluate(
        """(t) => { const b = document.getElementById('demo-subtitle');
                    if (!b) return;
                    if (t) { b.textContent = t; b.style.opacity = '1'; }
                    else { b.style.opacity = '0'; } }""",
        text,
    )
    if text:
        page.wait_for_timeout(hold_ms)


def smooth_scroll(page, top: int, ms: int = 1100) -> None:  # type: ignore[no-untyped-def]
    page.evaluate(f"window.scrollTo({{top: {top}, behavior: 'smooth'}})")
    page.wait_for_timeout(ms)


def move_to(page, sel: str) -> None:  # type: ignore[no-untyped-def]
    try:
        el = page.locator(sel).first
        el.scroll_into_view_if_needed(timeout=1500)
        box = el.bounding_box()
        if box:
            page.mouse.move(box["x"] + box["width"] / 2,
                            box["y"] + box["height"] / 2, steps=10)
            page.wait_for_timeout(250)
    except Exception:
        pass


def move_and_click(page, sel: str, post_ms: int = 700) -> bool:  # type: ignore[no-untyped-def]
    try:
        el = page.locator(sel).first
        el.scroll_into_view_if_needed(timeout=2000)
        box = el.bounding_box()
        if box:
            page.mouse.move(box["x"] + box["width"] / 2,
                            box["y"] + box["height"] / 2, steps=12)
            page.wait_for_timeout(300)
        el.click()
    except Exception as exc:
        print(f"  warn: click on {sel!r} failed: {exc}", file=sys.stderr)
        return False
    page.wait_for_timeout(post_ms)
    return True


def record(base_url: str) -> Path:
    """Run the walkthrough; return the path of the captured webm."""
    from playwright.sync_api import sync_playwright

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        try:
            # 1. Home
            page.goto(f"{base_url}/index.html"); page.wait_for_load_state("networkidle")
            inject_overlays(page)
            subtitle(page, "llmwiki — your sessions, browsable", 1400)
            smooth_scroll(page, 250); subtitle(page, "Activity heatmap")
            smooth_scroll(page, 480); subtitle(page, "Token stats")
            smooth_scroll(page, 700); subtitle(page, "Project grid"); page.wait_for_timeout(800)

            # 2. Projects index
            page.goto(f"{base_url}/projects/index.html"); page.wait_for_load_state("networkidle")
            inject_overlays(page); subtitle(page, "Projects index — freshness badges", 1400)

            # 3. Largest project (best-effort match — fallback to sessions index)
            for sel in ('a.card[href="llm-wiki.html"]',
                        'a.card[href="research.html"]',
                        'a.card'):
                if move_and_click(page, sel, post_ms=1100):
                    break
            page.wait_for_load_state("networkidle"); inject_overlays(page)
            subtitle(page, "Per-project sessions list", 900)
            smooth_scroll(page, 350)

            # 4. Sessions index — filter
            page.goto(f"{base_url}/sessions/index.html"); page.wait_for_load_state("networkidle")
            inject_overlays(page); subtitle(page, "Filter by slug", 800)
            page.locator("#filter-text").fill("subagent"); page.wait_for_timeout(900)
            page.locator("#filter-clear").click(); page.wait_for_timeout(400)

            # 5. Cmd+K palette
            page.goto(f"{base_url}/index.html"); page.wait_for_load_state("networkidle")
            inject_overlays(page); subtitle(page, "Cmd+K palette", 700)
            move_and_click(page, "#open-palette", post_ms=400)
            try:
                page.locator("#palette-input").press_sequentially("graph", delay=70)
                page.wait_for_timeout(900)
            except Exception:
                pass
            page.keyboard.press("Escape"); page.wait_for_timeout(500)

            # 6. Graph
            page.goto(f"{base_url}/graph.html"); page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000); inject_overlays(page)
            subtitle(page, "Knowledge graph", 1200)
            move_and_click(page, "#cluster-toggle", post_ms=1200)

            # 7. Theme toggle
            page.goto(f"{base_url}/index.html"); page.wait_for_load_state("networkidle")
            inject_overlays(page); subtitle(page, "Theme: dark → light", 800)
            move_and_click(page, "#theme-toggle", post_ms=1200)
            subtitle(page, "")
        finally:
            ctx.close()
            video_src = page.video.path() if page.video else None
            browser.close()

    if not video_src:
        raise RuntimeError("playwright reported no video path")
    final = VIDEO_DIR / "llmwiki-demo.webm"
    Path(video_src).rename(final)
    return final


def to_gif(webm: Path, out: Path, *, fps: int = 12, width: int = 960) -> bool:
    """Convert webm → optimized gif via ffmpeg's palettegen filter.

    Returns True on success, False if ffmpeg is unavailable. We intentionally
    do not raise so a maintainer without ffmpeg can still produce the webm.
    """
    if shutil.which("ffmpeg") is None:
        print("ffmpeg not on PATH — skipping GIF conversion", file=sys.stderr)
        return False
    palette = webm.with_suffix(".palette.png")
    # Two-pass: build palette, then encode.
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(webm),
         "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,palettegen",
         str(palette)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(webm), "-i", str(palette),
         "-lavfi", f"fps={fps},scale={width}:-1:flags=lanczos[x];[x][1:v]paletteuse",
         str(out)],
        check=True,
    )
    palette.unlink(missing_ok=True)
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="Record llmwiki demo walkthrough")
    p.add_argument("--base-url",
                   default=os.environ.get("QA_BASE_URL", "http://127.0.0.1:8765"))
    p.add_argument("--no-gif", action="store_true",
                   help="Skip the GIF conversion step")
    p.add_argument("--width", type=int, default=960,
                   help="GIF width in pixels (default 960)")
    p.add_argument("--fps", type=int, default=12, help="GIF frames per second")
    args = p.parse_args()

    print(f"Recording walkthrough against {args.base_url} …")
    try:
        webm = record(args.base_url)
    except Exception as e:
        print(f"recording failed: {e}", file=sys.stderr)
        return 1
    print(f"video saved: {webm}")
    if args.no_gif:
        return 0
    print(f"converting to GIF at {GIF_PATH} …")
    ok = to_gif(webm, GIF_PATH, fps=args.fps, width=args.width)
    if ok:
        print(f"GIF saved: {GIF_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
