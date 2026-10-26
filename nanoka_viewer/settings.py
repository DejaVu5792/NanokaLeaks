"""Persistent user settings stored under the XDG config directory."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS = {
    "cache_character_details": True,
    "cache_character_artwork": True,
    "cache_character_builds": True,
}

_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME")
CONFIG_DIR = Path(_CONFIG_HOME) if _CONFIG_HOME else Path.home() / ".config"
SETTINGS_DIR = CONFIG_DIR / "nanoka_leaks"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


def _normalize(settings: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(DEFAULT_SETTINGS)
    if isinstance(settings, dict):
        for key in DEFAULT_SETTINGS:
            if key in settings:
                result[key] = bool(settings[key])
    return result


def load_settings() -> dict[str, Any]:
    """Load settings from disk, falling back to defaults."""
    try:
        if SETTINGS_FILE.exists():
            with SETTINGS_FILE.open("r", encoding="utf-8") as handle:
                return _normalize(json.load(handle))
    except (OSError, ValueError, TypeError) as exc:
        import logging

        logging.getLogger(__name__).warning("Could not read settings: %s", exc)
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Normalize, persist, and return the settings."""
    normalized = _normalize(settings)
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        temporary = SETTINGS_FILE.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.replace(SETTINGS_FILE)
    except OSError as exc:
        import logging

        logging.getLogger(__name__).warning("Could not save settings: %s", exc)
    return normalized


def get_setting(key: str) -> bool:
    """Return one boolean setting, defaulting to enabled."""
    return bool(load_settings().get(key, DEFAULT_SETTINGS.get(key, True)))