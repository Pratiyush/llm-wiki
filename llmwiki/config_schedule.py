"""Schedule-config helpers extracted from cli.py (#691 / #arch-h8).

The "should this step run automatically after sync?" decision is a
config-policy concern, not a CLI concern. Moved out of ``cli.py``
into this module; ``cli.py`` re-exports under the original
underscored names for back-compat.
"""

from __future__ import annotations

import json as _json

from llmwiki import REPO_ROOT


def load_schedule_config() -> dict[str, str]:
    """Load build/lint schedule config from sessions_config.json.

    Returns a dict with at minimum ``build`` and ``lint`` keys, each
    one of ``on-sync``, ``daily``, ``weekly``, ``manual``, or ``never``.
    Defaults are ``build: on-sync, lint: manual`` when the config file
    is missing or malformed.
    """
    config_path = REPO_ROOT / "examples" / "sessions_config.json"
    if not config_path.is_file():
        return {"build": "on-sync", "lint": "manual"}
    try:
        data = _json.loads(config_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"build": "on-sync", "lint": "manual"}
    schedule = data.get("schedule", {})
    return {
        "build": schedule.get("build", "on-sync"),
        "lint": schedule.get("lint", "manual"),
    }


def should_run_after_sync(schedule: str) -> bool:
    """Return True if the schedule value indicates running after sync.

    Accepted values: ``on-sync``, ``daily``, ``weekly``, ``manual``,
    ``never``. Only ``on-sync`` triggers from cmd_sync. ``daily`` /
    ``weekly`` run from a scheduled task; ``manual`` and ``never``
    never auto-run.
    """
    return schedule.lower() == "on-sync"
