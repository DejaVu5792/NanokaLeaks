"""Persistent user settings stored under the XDG config directory."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS = {
    "cache_character_details": True,
    # Build tables are versioned per live game release and change much more
    # often than detail text, so they remain a separate cache category.
    "cache_character_builds": True,
    "cache_character_artwork": True,
    # Experimental: shift the details artwork toward its detail-weighted
    # centroid instead of the geometric centre.  The key predates the
    # Pillow-only centroid and is kept so saved settings keep working.
    "sr_centroid_centering": True,
}

_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME")
CONFIG_DIR = Path(_CONFIG_HOME) if _CONFIG_HOME else Path.home() / ".config"
SETTINGS_DIR = CONFIG_DIR / "nanoka_leaks"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# The game list lives in the API package, which itself imports this module.
# Resolve it lazily so importing ``nanoka_viewer.settings`` on its own never
# triggers a partially initialized circular import.
_GAME_IDS: tuple[str, ...] | None = None

# ``get_setting`` is called on most detail, artwork and preload paths, so
# re-reading and re-parsing the JSON file on every call adds up.  The parsed
# result is kept until the file's mtime/size changes or ``save_settings``
# replaces it.
_SETTINGS_CACHE: dict[str, Any] | None = None
_SETTINGS_STAMP: tuple[str, int, int] | None = None
_SETTINGS_LOCK = threading.Lock()


def _settings_stamp() -> tuple[str, int, int] | None:
    """Return an identity for the on-disk settings file, or ``None``."""
    try:
        stat = SETTINGS_FILE.stat()
    except OSError:
        return None
    return (str(SETTINGS_FILE), stat.st_mtime_ns, stat.st_size)


def _copy_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy whose lists cannot mutate the cached value."""
    return {
        key: list(value) if isinstance(value, list) else value
        for key, value in settings.items()
    }


def clear_settings_cache() -> None:
    """Drop the in-memory settings; the next read hits the file again."""
    global _SETTINGS_CACHE, _SETTINGS_STAMP
    with _SETTINGS_LOCK:
        _SETTINGS_CACHE = None
        _SETTINGS_STAMP = None


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


def normalize_game_order(raw: Any) -> list[str]:
    """Return a sanitized, complete game order."""
    return _normalize_game_order(raw)


def normalize_game_ids(raw: Any) -> list[str]:
    """Return known, unique game ids in the order they were stored."""
    return _normalize_game_ids(raw)


def _normalize(settings: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(DEFAULT_SETTINGS)
    source = settings if isinstance(settings, dict) else {}
    for key in DEFAULT_SETTINGS:
        if key in source:
            result[key] = bool(source[key])
    result["game_order"] = _normalize_game_order(source.get("game_order"))
    result["disabled_games"] = _normalize_game_ids(source.get("disabled_games"))
    return result


def load_settings(*, use_cache: bool = True) -> dict[str, Any]:
    """Load settings from disk, falling back to defaults.

    The parsed result is cached in memory keyed by the file's mtime and size.
    Pass ``use_cache=False`` when a fresh read is required regardless (for
    example after another process wrote the file with an unchanged size).
    """
    global _SETTINGS_CACHE, _SETTINGS_STAMP
    stamp = _settings_stamp()
    if use_cache:
        with _SETTINGS_LOCK:
            cached = _SETTINGS_CACHE
            cached_stamp = _SETTINGS_STAMP
        if cached is not None and stamp == cached_stamp:
            return _copy_settings(cached)

    try:
        if stamp is not None:
            with SETTINGS_FILE.open("r", encoding="utf-8") as handle:
                normalized = _normalize(json.load(handle))
        else:
            normalized = _normalize(None)
    except (OSError, ValueError, TypeError) as exc:
        import logging

        logging.getLogger(__name__).warning("Could not read settings: %s", exc)
        # Do not cache defaults for an unreadable file: retry on the next call.
        return _normalize(None)

    with _SETTINGS_LOCK:
        _SETTINGS_CACHE = normalized
        _SETTINGS_STAMP = stamp
    return _copy_settings(normalized)


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Normalize, persist, and return the settings."""
    global _SETTINGS_CACHE, _SETTINGS_STAMP
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
        clear_settings_cache()
        return _copy_settings(normalized)

    with _SETTINGS_LOCK:
        _SETTINGS_CACHE = normalized
        _SETTINGS_STAMP = _settings_stamp()
    return _copy_settings(normalized)


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
