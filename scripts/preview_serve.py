#!/usr/bin/env python3
"""Tiny localhost-only static server for llmwiki preview.

This exists because the default `python3 -m http.server` can fail when the
parent shell is launched from a cwd that has been deleted — Python 3.9's
`http.server` evaluates `os.getcwd()` at argparse definition time in its
`__main__` block and raises PermissionError. This script chdir's first,
then imports the handler, so there is no implicit `getcwd()` at import.

Usage (from anywhere):
    /usr/bin/python3 /path/to/scripts/preview_serve.py

Port, host, and directory are resolved from the repo root relative to this
file, so there are no CLI args and nothing to configure.
"""
from __future__ import annotations

import os
from pathlib import Path

# Resolve site dir BEFORE importing http.server. No getcwd() calls allowed.
_HERE = Path(__file__).resolve().parent
_SITE = (_HERE.parent / "site").resolve()
if not _SITE.is_dir():
    raise SystemExit(f"site directory not found: {_SITE}")
os.chdir(_SITE)

import http.server  # noqa: E402 — must come after chdir
import socketserver  # noqa: E402

_HOST = "127.0.0.1"
_PORT = 8765


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A002
        return


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main() -> int:
    url = f"http://{_HOST}:{_PORT}/"
    print(f"==> Serving {_SITE} at {url}")
    print("    Press Ctrl+C to stop.")
    with _ReusableTCPServer((_HOST, _PORT), _QuietHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
