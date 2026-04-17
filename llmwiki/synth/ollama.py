"""Ollama backend for local LLM synthesis (v1.1.0 · #35).

Provides ``OllamaSynthesizer``, a stdlib-only HTTP client for Ollama's
``/api/generate`` endpoint. The dependency is **optional**: the default
llmwiki install stays on stdlib + ``markdown``, and this module only
touches ``urllib`` (also stdlib), so there is nothing extra to install.

Ollama must be running locally — by default at ``http://127.0.0.1:11434``.
This keeps synthesis private by default (no data ever leaves the box).

Design notes
------------
- **Privacy by default**: ``base_url`` defaults to 127.0.0.1. If the user
  points the backend at a remote host we log a warning once so they
  know they've left the local-only path.
- **Graceful fallback**: ``is_available()`` probes ``/api/tags`` with a
  short timeout. If the server is down ``synthesize_source_page()`` raises
  ``OllamaUnavailableError``; the caller (``pipeline.synthesize_new_sessions``)
  catches that, logs a warning, and skips the file without crashing the
  sync.
- **Retries**: transient 5xx or ``socket.timeout`` errors retry with
  exponential backoff (default 3 attempts, 0.5/1.0/2.0s). Connection
  refused errors short-circuit — the server is simply not running.
- **No streaming**: we send ``stream: false`` because callers want the
  complete synthesised page back, not a token stream. Streaming can land
  later if a use case for it appears.

Configuration (``sessions_config.json`` / ``config.json``)::

    "synthesis": {
      "backend": "ollama",
      "model":  "llama3.1:8b",
      "base_url": "http://127.0.0.1:11434",
      "timeout": 60,
      "max_retries": 3
    }

Config parsing is done in :func:`load_ollama_config` so the CLI can
surface readable errors instead of stack traces.
"""

from __future__ import annotations

import json
import logging
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from llmwiki.synth.base import BaseSynthesizer

# ─── Constants ─────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_TIMEOUT = 60           # seconds, per HTTP call
DEFAULT_MAX_RETRIES = 3        # includes the first attempt
DEFAULT_BACKOFF_BASE = 0.5     # seconds; doubles each retry

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

logger = logging.getLogger(__name__)


# ─── Exceptions ────────────────────────────────────────────────────────


class OllamaError(RuntimeError):
    """Base class for Ollama backend failures."""


class OllamaUnavailableError(OllamaError):
    """Raised when the Ollama server is unreachable (connection refused,
    DNS failure, or health check fails)."""


class OllamaHTTPError(OllamaError):
    """Raised when the server returns a non-2xx after exhausting retries."""

    def __init__(self, status: int, body: str):
        super().__init__(f"Ollama returned HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body


# ─── Config ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OllamaConfig:
    """Resolved configuration for :class:`OllamaSynthesizer`."""

    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_base: float = DEFAULT_BACKOFF_BASE

    @property
    def generate_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/generate"

    @property
    def tags_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/tags"

    @property
    def is_local(self) -> bool:
        """True if base_url resolves to localhost (privacy check)."""
        try:
            host = urllib.parse.urlparse(self.base_url).hostname or ""
        except ValueError:
            return False
        return host in LOCAL_HOSTS


def load_ollama_config(cfg: Optional[dict[str, Any]]) -> OllamaConfig:
    """Build an :class:`OllamaConfig` from the ``synthesis`` block of
    ``sessions_config.json``.

    Missing keys fall back to the module-level defaults so first-time
    users don't have to configure anything to try it out::

        { "synthesis": { "backend": "ollama" } }

    is enough to reach a working local default.
    """
    synth = (cfg or {}).get("synthesis", {}) or {}
    # Use `in` checks (not `or`) so an explicit 0 fails validation instead
    # of being silently swapped for the default.
    model = synth.get("model") or DEFAULT_MODEL
    base_url = synth.get("base_url") or DEFAULT_BASE_URL
    timeout = int(synth["timeout"]) if "timeout" in synth else DEFAULT_TIMEOUT
    max_retries = (
        int(synth["max_retries"]) if "max_retries" in synth else DEFAULT_MAX_RETRIES
    )
    backoff_base = (
        float(synth["backoff_base"])
        if "backoff_base" in synth
        else DEFAULT_BACKOFF_BASE
    )

    if timeout <= 0:
        raise ValueError(f"synthesis.timeout must be positive, got {timeout}")
    if max_retries < 1:
        raise ValueError(
            f"synthesis.max_retries must be >= 1, got {max_retries}"
        )

    resolved = OllamaConfig(
        model=model,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        backoff_base=backoff_base,
    )

    if not resolved.is_local:
        logger.warning(
            "Ollama backend pointed at non-local host %s — transcript data "
            "will leave this machine. Set synthesis.base_url to http://127.0.0.1:11434 "
            "to restore privacy-by-default.",
            resolved.base_url,
        )

    return resolved


# ─── Synthesizer ───────────────────────────────────────────────────────


class OllamaSynthesizer(BaseSynthesizer):
    """Synthesize wiki source pages via a local Ollama HTTP server.

    The implementation uses only ``urllib`` so no third-party HTTP client
    is required. Test injection uses the ``http_post`` / ``http_get``
    kwargs so ``unittest.mock`` or a hand-rolled fake can substitute the
    transport layer without a real socket.
    """

    def __init__(
        self,
        config: Optional[OllamaConfig] = None,
        *,
        http_post: Optional[Any] = None,
        http_get: Optional[Any] = None,
    ):
        self.config = config or OllamaConfig()
        self._http_post = http_post or _urlopen_post
        self._http_get = http_get or _urlopen_get

    # ---- BaseSynthesizer interface --------------------------------

    def is_available(self) -> bool:
        """Probe ``/api/tags`` with a 2-second timeout.

        Returns True iff the server responds 2xx. Any exception
        (connection refused, DNS failure, HTTP 5xx, etc.) is swallowed
        and returns False — callers should branch on this before calling
        :meth:`synthesize_source_page`.
        """
        try:
            status, _ = self._http_get(
                self.config.tags_url, timeout=min(self.config.timeout, 2)
            )
            return 200 <= status < 300
        except Exception as exc:  # noqa: BLE001 — probe must never raise
            logger.debug("Ollama availability probe failed: %s", exc)
            return False

    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        """Render ``prompt_template`` with the session body + metadata
        and send it to Ollama. Returns the model's raw completion text.

        Raises
        ------
        OllamaUnavailableError
            The server could not be reached at all (connection refused,
            DNS failure, etc.). Callers should skip synthesis and move on.
        OllamaHTTPError
            The server returned a non-2xx response after all retries.
        """
        prompt = _render_prompt(prompt_template, raw_body=raw_body, meta=meta)
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
        }

        data = self._call_generate(payload)
        response = data.get("response", "")
        if not isinstance(response, str):
            raise OllamaError(
                f"Ollama returned non-string response: {type(response).__name__}"
            )
        return response.strip()

    # ---- internals -----------------------------------------------

    def _call_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to /api/generate with retry + backoff."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                status, body = self._http_post(
                    self.config.generate_url,
                    payload,
                    timeout=self.config.timeout,
                )
            except OllamaUnavailableError:
                # Connection refused / DNS failure — don't retry. The
                # server simply isn't listening; retrying wastes time.
                raise
            except (socket.timeout, urllib.error.URLError) as exc:
                last_exc = exc
                logger.warning(
                    "Ollama request attempt %d/%d failed: %s",
                    attempt,
                    self.config.max_retries,
                    exc,
                )
                if attempt == self.config.max_retries:
                    raise OllamaError(f"Ollama call failed: {exc}") from exc
                time.sleep(self.config.backoff_base * (2 ** (attempt - 1)))
                continue

            if 200 <= status < 300:
                try:
                    return json.loads(body)
                except (ValueError, json.JSONDecodeError) as exc:
                    raise OllamaError(
                        f"Ollama returned non-JSON body: {exc}"
                    ) from exc

            if 500 <= status < 600 and attempt < self.config.max_retries:
                logger.warning(
                    "Ollama %s returned %d; retrying (%d/%d)",
                    self.config.generate_url,
                    status,
                    attempt,
                    self.config.max_retries,
                )
                time.sleep(self.config.backoff_base * (2 ** (attempt - 1)))
                continue

            raise OllamaHTTPError(status, body)

        # Unreachable if max_retries >= 1, but keep the type checker honest
        raise OllamaError(f"Ollama call failed after retries: {last_exc}")


# ─── HTTP transport (stdlib) ──────────────────────────────────────────


def _urlopen_post(
    url: str, payload: dict[str, Any], *, timeout: float
) -> tuple[int, str]:
    """POST JSON and return (status, body) as text. Raises
    :class:`OllamaUnavailableError` on connection refused / DNS failure."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        # Server responded, but with an error code — treat as protocol
        # failure and return the status/body so retry logic can decide.
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ConnectionRefusedError):
            raise OllamaUnavailableError(
                f"Ollama server refused connection at {url}. "
                "Is `ollama serve` running?"
            ) from exc
        if isinstance(reason, socket.gaierror):
            raise OllamaUnavailableError(
                f"Ollama host DNS lookup failed for {url}: {reason}"
            ) from exc
        raise


def _urlopen_get(url: str, *, timeout: float) -> tuple[int, str]:
    """GET and return (status, body). Same error-mapping rules as POST."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ConnectionRefusedError):
            raise OllamaUnavailableError(
                f"Ollama server refused connection at {url}."
            ) from exc
        if isinstance(reason, socket.gaierror):
            raise OllamaUnavailableError(
                f"Ollama host DNS lookup failed for {url}: {reason}"
            ) from exc
        raise


# ─── Prompt rendering ─────────────────────────────────────────────────


def _render_prompt(
    template: str, *, raw_body: str, meta: dict[str, Any]
) -> str:
    """Substitute ``{body}`` and ``{meta}`` placeholders in the template.

    We deliberately use ``str.replace`` (not ``.format``) because session
    bodies contain ``{}`` in code blocks — calling ``.format`` there would
    raise ``KeyError``.
    """
    meta_dump = json.dumps(meta, indent=2, default=str, sort_keys=True)
    return template.replace("{body}", raw_body).replace("{meta}", meta_dump)
