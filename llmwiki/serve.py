"""Local HTTP server for the built llmwiki site.

Uses only Python stdlib. Binds to 127.0.0.1 by default so nothing is exposed
to the network unless the user explicitly passes --host 0.0.0.0.
"""

from __future__ import annotations

import http.server
import socketserver
import webbrowser
from pathlib import Path


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Like SimpleHTTPRequestHandler but with prettier logs and a branded
    404 response that pulls ``site/404.html`` (closes #387 U8) instead of
    falling back to the stdlib's plain-text error page."""

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Suppress per-request logs for a cleaner terminal.
        return

    def send_error(self, code: int, message: str | None = None,
                   explain: str | None = None) -> None:
        """Override the default error page so 404s pick up the branded
        ``404.html`` shipped by ``llmwiki build``. We deliberately keep the
        404 status code intact — the page is the *body* of the 404 response,
        not a redirect — so crawlers still see the right HTTP code.

        Falls back to the stdlib default for anything other than 404, or
        when ``404.html`` is missing (e.g. a partially-built site)."""
        if code == 404:
            try:
                # #py-m2 (#588): no longer relies on os.chdir(). The
                # SimpleHTTPRequestHandler's `directory` arg holds the
                # site root; we read 404.html from there explicitly.
                site_root = getattr(self, "directory", None)
                err_page = (Path(site_root) / "404.html") if site_root else Path("404.html")
                with open(err_page, "rb") as f:
                    body = f.read()
                self.send_response(404, message)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except (FileNotFoundError, OSError):
                # 404.html doesn't exist — fall through to default behavior.
                pass
        super().send_error(code, message, explain)


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def serve_site(
    directory: Path,
    port: int = 8765,
    host: str = "127.0.0.1",
    open_browser: bool = False,
) -> int:
    directory = directory.expanduser().resolve()
    if not directory.exists():
        print(f"error: {directory} does not exist. Run `llmwiki build` first.")
        return 2
    # #py-m2 (#588): use SimpleHTTPRequestHandler's `directory=` kwarg
    # (Python 3.7+) instead of mutating global cwd. The previous
    # `os.chdir(directory)` call leaked process state — every test
    # using this function had to remember to chdir back, and
    # concurrent serve_site calls in tests would race.
    handler_factory = lambda *a, **kw: _QuietHandler(*a, directory=str(directory), **kw)
    url = f"http://{host}:{port}/"
    print(f"==> Serving {directory} at {url}")
    print("    Press Ctrl+C to stop.")
    try:
        with _ReusableTCPServer((host, port), handler_factory) as httpd:
            if open_browser:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n  stopped.")
    except OSError as e:
        print(f"error: could not bind {host}:{port}: {e}")
        return 1
    return 0
