"""GitHub webhook handler for auto-syncing llm-wiki.

A minimal HTTP server (stdlib only — no Flask) that receives GitHub push
webhooks and triggers `python3 -m llmwiki sync` + `python3 -m llmwiki build`.

Usage:
    python3 handler.py                           # default: 0.0.0.0:9876
    python3 handler.py --port 9000               # custom port
    WEBHOOK_SECRET=mysecret python3 handler.py   # verify signatures

Environment variables:
    LLMWIKI_DIR      — path to the llm-wiki project root (default: cwd)
    WEBHOOK_SECRET   — GitHub webhook secret for HMAC verification (optional)
    PYTHON_PATH      — Python executable (default: python3)
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLMWIKI_DIR = Path(os.environ.get("LLMWIKI_DIR", ".")).resolve()
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
PYTHON_PATH = os.environ.get("PYTHON_PATH", "python3")


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class WebhookHandler(BaseHTTPRequestHandler):
    """Handle POST /webhook from GitHub."""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        if self.path not in ("/webhook", "/webhook/"):
            self._respond(404, {"error": "not found"})
            return

        # Verify signature if a secret is configured
        if WEBHOOK_SECRET:
            sig_header = self.headers.get("X-Hub-Signature-256", "")
            if not self._verify_signature(body, sig_header):
                self._respond(403, {"error": "invalid signature"})
                return

        # Parse payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid JSON"})
            return

        # Only act on push events
        event = self.headers.get("X-GitHub-Event", "")
        if event != "push":
            self._respond(200, {"status": "ignored", "event": event})
            return

        ref = payload.get("ref", "")
        self.log_message("Push to %s — triggering sync + build", ref)

        # Run sync + build
        try:
            self._run_llmwiki("sync")
            self._run_llmwiki("build")
            self._respond(200, {"status": "ok", "ref": ref})
        except subprocess.CalledProcessError as exc:
            self._respond(
                500,
                {
                    "status": "error",
                    "command": exc.cmd,
                    "returncode": exc.returncode,
                    "output": (exc.output or b"").decode(errors="replace"),
                },
            )

    def do_GET(self) -> None:
        """Health check endpoint."""
        if self.path in ("/health", "/health/"):
            self._respond(200, {"status": "healthy", "project": str(LLMWIKI_DIR)})
        else:
            self._respond(200, {"status": "llmwiki webhook handler"})

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _verify_signature(self, body: bytes, sig_header: str) -> bool:
        """Verify the X-Hub-Signature-256 HMAC."""
        if not sig_header.startswith("sha256="):
            return False
        expected = hmac.new(
            WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        received = sig_header[7:]
        return hmac.compare_digest(expected, received)

    def _run_llmwiki(self, subcommand: str) -> None:
        """Run a llmwiki CLI subcommand."""
        subprocess.run(
            [PYTHON_PATH, "-m", "llmwiki", subcommand],
            cwd=str(LLMWIKI_DIR),
            check=True,
            capture_output=True,
        )

    def _respond(self, status: int, body: dict) -> None:
        """Send a JSON response."""
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        """Prefix log messages with [llmwiki-webhook]."""
        sys.stderr.write(
            f"[llmwiki-webhook] {fmt % args}\n"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GitHub webhook handler for llm-wiki auto-sync"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=9876, help="Port (default: 9876)"
    )
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), WebhookHandler)
    print(
        f"[llmwiki-webhook] Listening on {args.host}:{args.port}\n"
        f"[llmwiki-webhook] Project root: {LLMWIKI_DIR}\n"
        f"[llmwiki-webhook] Signature verification: "
        f"{'enabled' if WEBHOOK_SECRET else 'disabled'}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[llmwiki-webhook] Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
