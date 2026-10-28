"""Persistent user settings stored under the XDG config directory."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS = {
    "cache_character_details": True,
    # Build tables are versioned per live game release and change much more
    # often than detail text, so they remain a separate cache category.
    "cache_character_builds": True,
    "cache_character_artwork": True,
}

_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME")
CONFIG_DIR = Path(_CONFIG_HOME) if _CONFIG_HOME else Path.home() / ".config"
SETTINGS_DIR = CONFIG_DIR / "nanoka_leaks"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# The game list lives in the API package, which itself imports this module.
# Resolve it lazily so importing ``nanoka_viewer.settings`` on its own never
# triggers a partially initialized circular import.
_GAME_IDS: tuple[str, ...] | None = None


def all_game_ids() -> tuple[str, ...]:
    """Return every known game id in the default display order."""
    global _GAME_IDS
    if _GAME_IDS is None:
        from .api.constants import GAMES

        _GAME_IDS = tuple(GAMES)
    return _GAME_IDS


def _normalize_game_ids(raw: Any) -> list[str]:
    """Return known, unique game ids in the order they were stored."""
    known = all_game_ids()
    if not isinstance(raw, (list, tuple)):
        return []
    result: list[str] = []
    for value in raw:
        game = str(value)
        if game in known and game not in result:
            result.append(game)
    return result


def _normalize_game_order(raw: Any) -> list[str]:
    """Normalize the full order, appending games added in a newer release."""
    order = _normalize_game_ids(raw)
    for game in all_game_ids():
        if game not in order:
            order.append(game)
    return order


def _normalize(settings: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(DEFAULT_SETTINGS)
    source = settings if isinstance(settings, dict) else {}
    for key in DEFAULT_SETTINGS:
        if key in source:
            result[key] = bool(source[key])
    result["game_order"] = _normalize_game_order(source.get("game_order"))
    result["disabled_games"] = _normalize_game_ids(source.get("disabled_games"))
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
    return _normalize(None)


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


def get_game_order() -> list[str]:
    """Return the full display order, including disabled games."""
    return list(load_settings()["game_order"])


def get_disabled_games() -> list[str]:
    """Return the games hidden from the viewer."""
    return list(load_settings()["disabled_games"])


def get_enabled_games() -> list[str]:
    """Return enabled game ids in display order."""
    settings = load_settings()
    disabled = set(settings["disabled_games"])
    return [game for game in settings["game_order"] if game not in disabled]


def is_game_enabled(game: str) -> bool:
    """Return whether *game* should be loaded and displayed."""
    return game not in get_disabled_games()
