"""Tests for #484 — default redaction covers Anthropic/OpenAI/Google/
Stripe/JWT/PEM keys.

The original #416 contract: GitHub PATs + AWS keys + Slack tokens
unconditionally redacted. Extended in #484 to cover the keys
developers most commonly paste into Claude sessions:

- Anthropic: sk-ant-api03-...
- OpenAI: sk-..., sk-proj-..., sk-svcacct-...
- Google: AIza[35-char]
- Stripe: sk_live_..., pk_live_..., rk_live_...
- npm: npm_[36-char]
- JWT: eyJ.eyJ.sig 3-segment shape
- PEM: full BEGIN/END PRIVATE KEY envelope
"""

from __future__ import annotations

import pytest

from llmwiki.convert import Redactor, DEFAULT_CONFIG


@pytest.fixture
def redactor():
    """Default redactor with no extra patterns — exercises only the
    built-in _DEFAULT_TOKEN_PATTERNS."""
    cfg = {"redaction": {"real_username": "", "extra_patterns": []}}
    return Redactor(cfg)


# ─── positive matches: each new pattern catches its target ──────────────


def test_anthropic_key_redacted(redactor):
    text = "ANTHROPIC_API_KEY=sk-ant-api03-abcdefghij1234567890XXX-_"
    out = redactor(text)
    assert "sk-ant-api03" not in out
    assert "abcdefghij1234567890" not in out


def test_openai_classic_key_redacted(redactor):
    text = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwx"
    out = redactor(text)
    assert "abcdefghij" not in out


def test_openai_project_key_redacted(redactor):
    text = "OPENAI_PROJECT=sk-proj-abc123def456ghi789jkl012mno345"
    out = redactor(text)
    assert "abc123" not in out


def test_openai_service_account_key_redacted(redactor):
    text = "OPENAI_SVCACCT=sk-svcacct-XYZ123def456ghi789jkl012mno345"
    out = redactor(text)
    assert "XYZ123" not in out


def test_google_api_key_redacted(redactor):
    # AIza + exactly 35 chars. Built via concatenation so GitHub's
    # secret-scanner doesn't flag this test file as containing a
    # real Google API key.
    fake_key = "AI" + "za" + "SyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY"
    text = f"GOOGLE_API_KEY={fake_key}"
    out = redactor(text)
    assert fake_key[:8] not in out


def test_stripe_live_secret_key_redacted(redactor):
    # Concatenated so GitHub's secret-scanner doesn't flag the
    # contiguous `sk_live_*` literal in this test file.
    fake_key = "sk" + "_live_" + "51HabcDEFghiJKLmnoPQRstuVWXyz"
    text = f"STRIPE={fake_key}"
    out = redactor(text)
    assert "_live_" not in out  # the prefix part of the fake key gone


def test_stripe_publishable_live_key_redacted(redactor):
    fake_key = "pk" + "_live_" + "51HabcDEFghiJKLmnoPQRstuVWXyz"
    text = f"STRIPE_PUB={fake_key}"
    out = redactor(text)
    assert "_live_" not in out


def test_stripe_restricted_live_key_redacted(redactor):
    fake_key = "rk" + "_live_" + "51HabcDEFghiJKLmnoPQRstuVWXyz"
    text = f"STRIPE_RK={fake_key}"
    out = redactor(text)
    assert "_live_" not in out


def test_npm_token_redacted(redactor):
    text = "NPM_TOKEN=npm_abcdefghijklmnopqrstuvwxyz0123456789"
    out = redactor(text)
    assert "npm_abc" not in out


def test_jwt_redacted(redactor):
    # eyJ header + eyJ payload + signature, all base64url-shaped
    text = (
        "Authorization: Bearer "
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    out = redactor(text)
    assert "eyJhbGciOi" not in out


def _pem(kind: str = "", body: str = "MIIE-fake-body") -> str:
    """Build a PEM envelope at runtime so gitleaks doesn't flag the
    test file itself as containing a private key. The literal string
    `-----BEGIN ... PRIVATE KEY-----` never appears in source."""
    label = (kind + " ").lstrip()
    dashes = "-" * 5
    return (
        f"{dashes}BEGIN {label}PRIVATE KEY{dashes}\n"
        f"{body}\n"
        f"{dashes}END {label}PRIVATE KEY{dashes}"
    )


def test_pem_private_key_redacted(redactor):
    text = _pem(body="MIIEvQ-secret-content-line-1\nsecret-content-line-2")
    out = redactor(text)
    assert "secret-content-line" not in out
    assert "MIIEvQ" not in out


def test_pem_rsa_private_key_redacted(redactor):
    """Variants like RSA, EC, OPENSSH, etc. should also be caught."""
    for kind in ("RSA", "EC", "DSA", "OPENSSH", "ENCRYPTED"):
        text = _pem(kind=kind, body=f"VERY-SECRET-{kind}-MATERIAL")
        out = redactor(text)
        assert f"VERY-SECRET-{kind}" not in out, f"failed on {kind}"


# ─── negative cases: don't over-match ───────────────────────────────────


def test_stripe_test_key_NOT_redacted(redactor):
    """Test keys are meant to ship in code — leaving them visible is
    a feature. Built via concat so GitHub doesn't flag `sk_test_`."""
    fake_test = "sk" + "_test_" + "51HabcDEFghiJKLmnoPQRstuVWX"
    text = f"STRIPE_TEST={fake_test}"
    out = redactor(text)
    assert "_test_" in out


def test_lowercase_aiza_not_matched(redactor):
    """Google keys are case-sensitive — `aiza...` is not a key."""
    text = "var name = aizabcdefghijklmnopqrstuvwxyz0123456789"
    out = redactor(text)
    assert "aizabcdefghijk" in out


def test_dotted_string_not_classified_as_jwt(redactor):
    """A generic three-segment dotted string (not starting with eyJ)
    must not be JWT-classified."""
    text = "module.submodule.function"
    out = redactor(text)
    assert "module.submodule.function" in out


def test_short_sk_substring_not_redacted(redactor):
    """`sk-` followed by <20 chars is too short to be an API key."""
    text = "git checkout sk-feature-branch"
    out = redactor(text)
    # `sk-feature-branch` is 17 chars after `sk-`, below the 20-char threshold
    assert "sk-feature-branch" in out
