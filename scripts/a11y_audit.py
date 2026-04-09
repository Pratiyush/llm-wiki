#!/usr/bin/env python3
"""Run axe-core against a built llmwiki site via Playwright.

Usage:
    python3 scripts/a11y_audit.py [--site-dir site/]

Builds a demo site (using conftest helpers), starts a local server,
runs axe-core on 4 key page types, and prints a JSON report.
"""
import json
import socket
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ── build a demo site ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_demo_site() -> Path:
    """Seed raw/ with two demo sessions and run the builder."""
    import importlib
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="a11y_audit_"))
    raw_dir = tmp / "raw" / "sessions" / "demo-project"
    raw_dir.mkdir(parents=True)

    # Minimal session markdown
    for i, (slug, lang) in enumerate(
        [("2026-01-15-fastapi-auth", "python"), ("2026-02-10-chrono-parser", "rust")],
        1,
    ):
        (raw_dir / f"{slug}.md").write_text(
            f"""---
slug: {slug}
project: demo-project
date: {'2026-01-15' if i == 1 else '2026-02-10'}
started: {'2026-01-15T10:00:00Z' if i == 1 else '2026-02-10T14:00:00Z'}
ended: {'2026-01-15T11:30:00Z' if i == 1 else '2026-02-10T15:45:00Z'}
model: claude-sonnet-4-20250514
gitBranch: main
cwd: /Users/USER/projects/demo
user_messages: {10 + i}
tool_calls: {20 + i}
tools_used: [Bash, Read, Write, Grep, Glob]
is_subagent: false
---

# Session: {slug}

**Project:** demo-project · **Branch:** main

## Summary

Demo session {i} for accessibility audit testing.

## Conversation

### Turn 1 — User

Set up the {'FastAPI auth' if i == 1 else 'chrono date parser'} module.

### Turn 1 — Assistant

I'll create the {'authentication middleware' if i == 1 else 'date parsing library'}.

```{lang}
{'def authenticate(token: str) -> bool: return True' if lang == 'python' else 'fn parse_date(s: &str) -> Option<NaiveDate> { None }'}
```

**Tools used:**
- `Bash`: `mkdir -p src` — exit 0
- `Write`: `src/{'auth' if lang == 'python' else 'parser'}.{'py' if lang == 'python' else 'rs'}`
""",
            encoding="utf-8",
        )

    # Build into tmp/site/
    site_dir = tmp / "site"
    site_dir.mkdir()

    build_mod = importlib.import_module("llmwiki.build")

    # Monkeypatch RAW_DIR/RAW_SESSIONS like conftest does
    orig_raw = build_mod.RAW_DIR
    orig_sessions = getattr(build_mod, "RAW_SESSIONS", None)

    build_mod.RAW_DIR = tmp / "raw"
    if hasattr(build_mod, "RAW_SESSIONS"):
        build_mod.RAW_SESSIONS = raw_dir

    try:
        build_mod.build_site(out_dir=site_dir)
    finally:
        build_mod.RAW_DIR = orig_raw
        if orig_sessions is not None:
            build_mod.RAW_SESSIONS = orig_sessions

    return site_dir


def _serve(site_dir: Path, port: int) -> ThreadingHTTPServer:
    handler = type(
        "H",
        (SimpleHTTPRequestHandler,),
        {"__init__": lambda self, *a, **kw: SimpleHTTPRequestHandler.__init__(self, *a, directory=str(site_dir), **kw)},
    )
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def run_audit(site_dir=None):
    from axe_playwright_python.sync_playwright import Axe
    from playwright.sync_api import sync_playwright

    if site_dir is None:
        print("Building demo site …", file=sys.stderr)
        site_dir = _build_demo_site()
        print(f"  Built to {site_dir}", file=sys.stderr)

    port = _free_port()
    srv = _serve(site_dir, port)
    base = f"http://127.0.0.1:{port}"

    # Discover pages to test
    pages_to_test = {
        "home": f"{base}/index.html",
        "projects_index": f"{base}/projects/index.html",
        "sessions_index": f"{base}/sessions/index.html",
    }
    # Find a session detail page
    session_htmls = list((site_dir / "sessions").rglob("*.html"))
    session_htmls = [p for p in session_htmls if p.name != "index.html"]
    if session_htmls:
        rel = session_htmls[0].relative_to(site_dir)
        pages_to_test["session_detail"] = f"{base}/{rel}"

    all_violations = {}
    total_violations = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        for label, url in pages_to_test.items():
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")

            axe = Axe()
            results = axe.run(page)

            violations = results.response.get("violations", [])
            all_violations[label] = []

            for v in violations:
                nodes = []
                for n in v.get("nodes", []):
                    nodes.append({
                        "html": n.get("html", "")[:200],
                        "target": n.get("target", []),
                        "failureSummary": n.get("failureSummary", ""),
                    })
                all_violations[label].append({
                    "id": v["id"],
                    "impact": v.get("impact", ""),
                    "description": v.get("description", ""),
                    "helpUrl": v.get("helpUrl", ""),
                    "nodes_count": len(v.get("nodes", [])),
                    "nodes": nodes[:5],  # limit
                })
                total_violations += 1

            page.close()

        browser.close()

    srv.shutdown()

    # Print report
    print(json.dumps(all_violations, indent=2))
    print(f"\n=== Total: {total_violations} violation types across {len(pages_to_test)} pages ===", file=sys.stderr)

    return all_violations


if __name__ == "__main__":
    site_dir = None
    if len(sys.argv) > 1 and sys.argv[1] == "--site-dir":
        site_dir = Path(sys.argv[2])
    run_audit(site_dir)
