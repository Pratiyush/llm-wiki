"""Adapter status computation — pulled out of cli.py (#arch-h8 / #611).

Pre-#611 the ``configured``/``will_fire`` label computation lived as a
private ``_adapter_status`` helper inside ``cli.py``. The CLI's job is
to parse argv and print things — deciding whether an adapter is on /
off / auto belongs in the adapters package next to the adapters
themselves.

The function is re-exported from ``llmwiki.cli`` so the existing
``from llmwiki.cli import _adapter_status`` import path keeps working
for any downstream caller that reached for it.
"""

from __future__ import annotations

from typing import Any


def adapter_status(
    name: str,
    adapter_cls: Any,
    config: dict,
) -> tuple[str, str]:
    """Return ``(configured, will_fire)`` labels for one adapter (G-01 · #287).

    * ``configured``: ``explicit`` (user set ``enabled: true`` in the
      config), ``off`` (user set ``enabled: false``), or ``auto``
      (default — no explicit toggle).
    * ``will_fire``: ``yes`` when the next ``sync`` will pick this
      adapter up (available **and** not explicitly off), ``no``
      otherwise.

    The old labels — ``-`` / ``enabled`` / ``disabled`` — read as
    "adapter can't see anything" even when the adapter was discovering
    471 files on the next line. The new labels say exactly what they
    mean without the user cross-referencing ``sessions_config.json``.
    """
    adapter_cfg = config.get(name, {})
    enabled_in_cfg = None
    if isinstance(adapter_cfg, dict):
        enabled_in_cfg = adapter_cfg.get("enabled", None)
    if enabled_in_cfg is True:
        configured = "explicit"
    elif enabled_in_cfg is False:
        configured = "off"
    else:
        configured = "auto"
    available = adapter_cls.is_available()
    # #326: non-AI adapters are opt-in only, so ``auto`` on an Obsidian /
    # Jira / Meeting / PDF adapter means "available but won't fire".
    is_ai = getattr(adapter_cls, "is_ai_session", True)
    if configured == "off":
        will_fire = "no"
    elif configured == "explicit":
        will_fire = "yes" if available else "no"
    else:  # auto
        will_fire = "yes" if (available and is_ai) else "no"
    return configured, will_fire
