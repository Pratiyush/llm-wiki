"""Tests for the Ollama synthesis backend (v1.1.0 · #35).

No network calls: all HTTP is stubbed via the ``http_post`` / ``http_get``
kwargs on ``OllamaSynthesizer``, so the tests run the same on a laptop
without Ollama as they do in CI.
"""

from __future__ import annotations

import json
import socket
import urllib.error
from typing import Any
from unittest.mock import patch

import pytest

from llmwiki.synth.ollama import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    OllamaConfig,
    OllamaError,
    OllamaHTTPError,
    OllamaSynthesizer,
    OllamaUnavailableError,
    _render_prompt,
    _urlopen_get,
    _urlopen_post,
    load_ollama_config,
)


# ─── Test helpers ─────────────────────────────────────────────────────


class _FakeHTTP:
    """Scripted HTTP double. Returns queued ``(status, body)`` tuples
    (or raises queued exceptions) in order."""

    def __init__(self, script: list[Any]):
        self.script = list(script)
        self.calls: list[tuple[str, Any, float]] = []

    def __call__(self, url: str, *args, **kwargs) -> tuple[int, str]:
        payload = args[0] if args else None
        timeout = kwargs.get("timeout")
        self.calls.append((url, payload, timeout))
        if not self.script:
            raise AssertionError("no more scripted HTTP responses")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _make_synth(
    *,
    post_script: list[Any] | None = None,
    get_script: list[Any] | None = None,
    config: OllamaConfig | None = None,
) -> tuple[OllamaSynthesizer, _FakeHTTP, _FakeHTTP]:
    post = _FakeHTTP(post_script or [])
    get = _FakeHTTP(get_script or [])
    synth = OllamaSynthesizer(
        config=config or OllamaConfig(backoff_base=0.0),  # no sleep in tests
        http_post=post,
        http_get=get,
    )
    return synth, post, get


# ─── Config / defaults ────────────────────────────────────────────────


def test_defaults_match_privacy_baseline():
    assert DEFAULT_BASE_URL == "http://127.0.0.1:11434"
    assert DEFAULT_MODEL == "llama3.1:8b"
    assert DEFAULT_TIMEOUT == 60
    assert DEFAULT_MAX_RETRIES == 3
    assert DEFAULT_BACKOFF_BASE == 0.5


def test_ollama_config_urls():
    cfg = OllamaConfig(base_url="http://localhost:11434/")
    assert cfg.generate_url == "http://localhost:11434/api/generate"
    assert cfg.tags_url == "http://localhost:11434/api/tags"


def test_ollama_config_is_local_true_for_loopback():
    assert OllamaConfig(base_url="http://127.0.0.1:11434").is_local
    assert OllamaConfig(base_url="http://localhost:11434").is_local
    assert OllamaConfig(base_url="http://[::1]:11434").is_local


def test_ollama_config_is_local_false_for_public_host():
    assert not OllamaConfig(base_url="http://ollama.example.com:11434").is_local


def test_load_ollama_config_defaults_from_empty_block():
    cfg = load_ollama_config({"synthesis": {"backend": "ollama"}})
    assert cfg.model == DEFAULT_MODEL
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.timeout == DEFAULT_TIMEOUT
    assert cfg.max_retries == DEFAULT_MAX_RETRIES


def test_load_ollama_config_explicit_values():
    cfg = load_ollama_config({
        "synthesis": {
            "backend": "ollama",
            "model": "mistral:7b",
            "base_url": "http://127.0.0.1:9999",
            "timeout": 30,
            "max_retries": 5,
        }
    })
    assert cfg.model == "mistral:7b"
    assert cfg.base_url == "http://127.0.0.1:9999"
    assert cfg.timeout == 30
    assert cfg.max_retries == 5


def test_load_ollama_config_handles_none_root():
    cfg = load_ollama_config(None)
    assert cfg.model == DEFAULT_MODEL


def test_load_ollama_config_handles_missing_synthesis():
    cfg = load_ollama_config({})
    assert cfg.model == DEFAULT_MODEL


def test_load_ollama_config_rejects_zero_timeout():
    with pytest.raises(ValueError, match="timeout"):
        load_ollama_config({"synthesis": {"timeout": 0}})


def test_load_ollama_config_rejects_bad_max_retries():
    with pytest.raises(ValueError, match="max_retries"):
        load_ollama_config({"synthesis": {"max_retries": 0}})


def test_load_ollama_config_warns_on_remote_host(caplog):
    with caplog.at_level("WARNING", logger="llmwiki.synth.ollama"):
        load_ollama_config({"synthesis": {"base_url": "http://ollama.prod:11434"}})
    assert any("leave this machine" in rec.message for rec in caplog.records)


# ─── is_available() probe ────────────────────────────────────────────


def test_is_available_true_when_tags_200():
    synth, _, get = _make_synth(get_script=[(200, '{"models":[]}')])
    assert synth.is_available() is True
    assert get.calls[0][0].endswith("/api/tags")


def test_is_available_false_on_connection_refused():
    synth, _, _ = _make_synth(
        get_script=[OllamaUnavailableError("connection refused")]
    )
    assert synth.is_available() is False


def test_is_available_false_on_500():
    synth, _, _ = _make_synth(get_script=[(500, "oops")])
    assert synth.is_available() is False


def test_is_available_false_on_timeout():
    synth, _, _ = _make_synth(get_script=[socket.timeout("slow")])
    assert synth.is_available() is False


# ─── synthesize_source_page() ────────────────────────────────────────


def test_synthesize_happy_path_returns_response_text():
    body = json.dumps({"response": "## Summary\n\nA synthesized page."})
    synth, post, _ = _make_synth(post_script=[(200, body)])

    out = synth.synthesize_source_page(
        raw_body="Raw session.",
        meta={"slug": "s"},
        prompt_template="Body: {body}\nMeta: {meta}",
    )
    assert out == "## Summary\n\nA synthesized page."
    url, payload, _ = post.calls[0]
    assert url.endswith("/api/generate")
    assert payload["stream"] is False
    assert payload["model"] == DEFAULT_MODEL
    assert "Raw session." in payload["prompt"]


def test_synthesize_passes_configured_model():
    body = json.dumps({"response": "ok"})
    cfg = OllamaConfig(model="mistral:7b", backoff_base=0.0)
    synth, post, _ = _make_synth(post_script=[(200, body)], config=cfg)

    synth.synthesize_source_page(
        raw_body="", meta={}, prompt_template="{body}{meta}"
    )
    assert post.calls[0][1]["model"] == "mistral:7b"


def test_synthesize_raises_when_server_unavailable():
    synth, _, _ = _make_synth(
        post_script=[OllamaUnavailableError("refused")]
    )
    with pytest.raises(OllamaUnavailableError):
        synth.synthesize_source_page(
            raw_body="x", meta={}, prompt_template="{body}"
        )


def test_synthesize_retries_on_5xx_and_succeeds():
    body_ok = json.dumps({"response": "ok"})
    synth, post, _ = _make_synth(
        post_script=[(503, "busy"), (500, "busy"), (200, body_ok)]
    )
    out = synth.synthesize_source_page(
        raw_body="x", meta={}, prompt_template="{body}"
    )
    assert out == "ok"
    assert len(post.calls) == 3


def test_synthesize_gives_up_after_max_retries_on_5xx():
    cfg = OllamaConfig(max_retries=2, backoff_base=0.0)
    synth, post, _ = _make_synth(
        post_script=[(500, "down"), (500, "down")], config=cfg
    )
    with pytest.raises(OllamaHTTPError) as excinfo:
        synth.synthesize_source_page(
            raw_body="x", meta={}, prompt_template="{body}"
        )
    assert excinfo.value.status == 500
    assert len(post.calls) == 2


def test_synthesize_retries_on_socket_timeout():
    body_ok = json.dumps({"response": "ok"})
    synth, post, _ = _make_synth(
        post_script=[socket.timeout("slow"), (200, body_ok)]
    )
    out = synth.synthesize_source_page(
        raw_body="x", meta={}, prompt_template="{body}"
    )
    assert out == "ok"
    assert len(post.calls) == 2


def test_synthesize_wraps_urllib_error_after_retries():
    cfg = OllamaConfig(max_retries=2, backoff_base=0.0)
    err = urllib.error.URLError("wat")
    synth, post, _ = _make_synth(post_script=[err, err], config=cfg)
    with pytest.raises(OllamaError):
        synth.synthesize_source_page(
            raw_body="x", meta={}, prompt_template="{body}"
        )
    assert len(post.calls) == 2


def test_synthesize_raises_on_non_json_body():
    synth, _, _ = _make_synth(post_script=[(200, "not json")])
    with pytest.raises(OllamaError, match="non-JSON"):
        synth.synthesize_source_page(
            raw_body="x", meta={}, prompt_template="{body}"
        )


def test_synthesize_raises_on_non_string_response_field():
    body = json.dumps({"response": {"not": "a string"}})
    synth, _, _ = _make_synth(post_script=[(200, body)])
    with pytest.raises(OllamaError, match="non-string"):
        synth.synthesize_source_page(
            raw_body="x", meta={}, prompt_template="{body}"
        )


def test_synthesize_does_not_retry_on_4xx():
    # 4xx is a user error (bad model, bad request) — retrying is pointless.
    synth, post, _ = _make_synth(post_script=[(400, "no such model")])
    with pytest.raises(OllamaHTTPError) as excinfo:
        synth.synthesize_source_page(
            raw_body="x", meta={}, prompt_template="{body}"
        )
    assert excinfo.value.status == 400
    assert len(post.calls) == 1


# ─── Prompt rendering ─────────────────────────────────────────────────


def test_render_prompt_replaces_body_placeholder():
    out = _render_prompt("BODY: {body}", raw_body="hi", meta={})
    assert out == "BODY: hi"


def test_render_prompt_renders_meta_as_json():
    out = _render_prompt("META: {meta}", raw_body="", meta={"a": 1})
    assert '"a": 1' in out


def test_render_prompt_survives_curly_braces_in_body():
    # A session body containing {} would crash str.format — make sure we
    # use replace() instead.
    body = "code: def f(): return {'x': 1}"
    out = _render_prompt("{body}", raw_body=body, meta={})
    assert "'x': 1" in out


# ─── BaseSynthesizer conformance ──────────────────────────────────────


def test_synthesizer_is_base_synthesizer():
    from llmwiki.synth.base import BaseSynthesizer
    assert isinstance(OllamaSynthesizer(), BaseSynthesizer)


def test_name_property():
    assert OllamaSynthesizer().name == "OllamaSynthesizer"


# ─── Transport error mapping (real urllib stubs) ──────────────────────


def test_urlopen_post_maps_connection_refused_to_unavailable():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.URLError(
            ConnectionRefusedError("refused")
        )
        with pytest.raises(OllamaUnavailableError):
            _urlopen_post("http://127.0.0.1:11434/api/generate", {}, timeout=1)


def test_urlopen_post_maps_dns_failure_to_unavailable():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.URLError(
            socket.gaierror("no such host")
        )
        with pytest.raises(OllamaUnavailableError):
            _urlopen_post("http://nope.invalid/api/generate", {}, timeout=1)


def test_urlopen_get_maps_connection_refused_to_unavailable():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.URLError(
            ConnectionRefusedError("refused")
        )
        with pytest.raises(OllamaUnavailableError):
            _urlopen_get("http://127.0.0.1:11434/api/tags", timeout=1)


def test_urlopen_post_returns_status_and_body_on_http_error():
    class _FakeHTTPError(urllib.error.HTTPError):
        def __init__(self):
            self.code = 500
            self.fp = None
            self.msg = "boom"

        def read(self) -> bytes:
            return b""

    with patch("urllib.request.urlopen") as mock_open:
        err = _FakeHTTPError()
        mock_open.side_effect = err
        status, body = _urlopen_post(
            "http://127.0.0.1:11434/api/generate", {}, timeout=1
        )
        assert status == 500
        assert body == ""


# ─── Edge cases ───────────────────────────────────────────────────────


def test_empty_raw_body_still_calls_server():
    body = json.dumps({"response": "stub"})
    synth, post, _ = _make_synth(post_script=[(200, body)])
    out = synth.synthesize_source_page(
        raw_body="", meta={}, prompt_template="{body}"
    )
    assert out == "stub"
    assert post.calls, "server should still be called with empty body"


def test_response_trimmed():
    body = json.dumps({"response": "   padded  \n\n"})
    synth, _, _ = _make_synth(post_script=[(200, body)])
    out = synth.synthesize_source_page(
        raw_body="x", meta={}, prompt_template="{body}"
    )
    assert out == "padded"


def test_unicode_body_round_trips():
    raw = "日本語テスト — 🚀 — \u00e9lan"
    body = json.dumps({"response": raw})
    synth, post, _ = _make_synth(post_script=[(200, body)])
    out = synth.synthesize_source_page(
        raw_body=raw, meta={}, prompt_template="{body}"
    )
    assert out == raw
    assert raw in post.calls[0][1]["prompt"]


def test_ollama_http_error_message_truncates_long_body():
    err = OllamaHTTPError(500, "x" * 1000)
    assert len(str(err)) < 300  # the 200-char cap plus prefix


# ─── Pipeline resolver ────────────────────────────────────────────────


def test_resolve_backend_defaults_to_dummy_when_no_config():
    from llmwiki.synth.base import DummySynthesizer
    from llmwiki.synth.pipeline import resolve_backend

    assert isinstance(resolve_backend(None), DummySynthesizer)
    assert isinstance(resolve_backend({}), DummySynthesizer)


def test_resolve_backend_picks_ollama_when_configured():
    from llmwiki.synth.pipeline import resolve_backend

    backend = resolve_backend({"synthesis": {"backend": "ollama"}})
    assert isinstance(backend, OllamaSynthesizer)


def test_resolve_backend_falls_back_on_unknown_name(caplog):
    from llmwiki.synth.base import DummySynthesizer
    from llmwiki.synth.pipeline import resolve_backend

    with caplog.at_level("WARNING"):
        backend = resolve_backend({"synthesis": {"backend": "magic"}})
    assert isinstance(backend, DummySynthesizer)
    assert any("Unknown synthesis.backend" in r.message for r in caplog.records)


def test_resolve_backend_case_insensitive():
    from llmwiki.synth.pipeline import resolve_backend
    assert isinstance(
        resolve_backend({"synthesis": {"backend": "OLLAMA"}}),
        OllamaSynthesizer,
    )


# ─── CLI integration ──────────────────────────────────────────────────


def test_synthesize_subcommand_registered():
    from llmwiki.cli import build_parser

    parser = build_parser()
    sub_action = None
    for a in parser._actions:
        if hasattr(a, "choices") and a.choices:
            sub_action = a
            break
    assert sub_action is not None
    assert "synthesize" in sub_action.choices
