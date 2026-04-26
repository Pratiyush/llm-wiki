"""Adapter configuration validation (v1.0 · #177).

Consolidates the adapter enable/configure surface so users have a single
place to check what opt-in adapters can be configured and which are active.

Supported adapters:
  - meeting      (file-based, source_dirs + extensions)
  - jira         (network, server/email/api_token/jql)
  - web_clipper  (file-based intake, watch_dir + auto_queue)

The PDF adapter that used to live here was removed in the simplification
sweep — its dispatch path in ``convert.py`` was a phantom (no concrete
implementation; every adapter raised ``AttributeError`` on ``convert_pdf``).

All disabled by default — users must set ``<adapter>.enabled: true`` in
``sessions_config.json`` to activate.
"""

from __future__ import annotations

from typing import Any, Optional


# ─── Schemas ───────────────────────────────────────────────────────────

ADAPTER_SCHEMAS: dict[str, dict[str, Any]] = {
    "web_clipper": {
        "required_if_enabled": ["watch_dir"],
        "defaults": {"extensions": [".md"], "auto_queue": True},
        "types": {
            "watch_dir": str,
            "extensions": list,
            "auto_queue": bool,
        },
    },
}


def validate_adapter_config(
    config: dict[str, Any],
    adapter_name: str,
) -> list[str]:
    """Validate a single adapter's config section. Returns list of errors.

    Empty list = valid. Disabled adapters (or missing sections) are
    always valid — the check is about the *shape* of the config when
    enabled.
    """
    schema = ADAPTER_SCHEMAS.get(adapter_name)
    if schema is None:
        return [f"unknown adapter {adapter_name!r}"]

    section = config.get(adapter_name, {})
    if not isinstance(section, dict):
        return [f"{adapter_name!r} config must be a JSON object"]

    # If not enabled, skip further checks
    if not section.get("enabled"):
        return []

    errors: list[str] = []

    # Required fields
    for field in schema["required_if_enabled"]:
        if field not in section:
            errors.append(
                f"{adapter_name!r} is enabled but missing required field: {field!r}"
            )
        elif not section[field]:
            errors.append(
                f"{adapter_name!r} is enabled but {field!r} is empty"
            )

    # Type checks
    for field, expected_type in schema["types"].items():
        if field in section:
            value = section[field]
            if not isinstance(value, expected_type):
                errors.append(
                    f"{adapter_name!r} field {field!r} must be "
                    f"{expected_type.__name__} (got {type(value).__name__})"
                )

    return errors


def validate_all_adapters(config: dict[str, Any]) -> dict[str, list[str]]:
    """Validate every known adapter's config section. Returns ``{name: errors}``.

    Adapters with no errors map to an empty list. Use to display a full
    status report.
    """
    return {
        name: validate_adapter_config(config, name)
        for name in ADAPTER_SCHEMAS
    }


def is_adapter_enabled(config: dict[str, Any], adapter_name: str) -> bool:
    """Return True if the adapter is explicitly enabled in config."""
    section = config.get(adapter_name, {})
    if not isinstance(section, dict):
        return False
    return bool(section.get("enabled", False))


def enabled_adapters(config: dict[str, Any]) -> list[str]:
    """List adapter names that are enabled in config."""
    return [name for name in ADAPTER_SCHEMAS if is_adapter_enabled(config, name)]


def apply_defaults(
    config: dict[str, Any],
    adapter_name: str,
) -> dict[str, Any]:
    """Return the config section merged with schema defaults."""
    schema = ADAPTER_SCHEMAS.get(adapter_name)
    if schema is None:
        return config.get(adapter_name, {})
    section = dict(config.get(adapter_name, {}))
    for key, default in schema["defaults"].items():
        if key not in section:
            section[key] = default
    return section
