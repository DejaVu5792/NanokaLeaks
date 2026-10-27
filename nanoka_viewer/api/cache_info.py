"""Metadata for the recommended-build cache.

Build metadata changes more often than character detail text: each live game
version ships a new relic/weapon/item table.  This module records when the
build cache was last written and which live/latest versions were current at
that moment, so the settings dialog can explain why a build cache may be
stale.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from .cache_io import write_bytes_atomic
from .constants import CACHE_DIR, GAMES
from .manifest import fetch_manifest

logger = logging.getLogger(__name__)

BUILD_CACHE_INFO_FILE = CACHE_DIR / "build_cache_info.json"

_LOCK = threading.Lock()


def _empty_info() -> dict[str, Any]:
    return {"version": 1, "last_cached": 0.0, "games": {}}


def _normalize(data: Any) -> dict[str, Any]:
    info = _empty_info()
    if not isinstance(data, dict):
        return info
    try:
        info["last_cached"] = float(data.get("last_cached") or 0.0)
    except (TypeError, ValueError):
        pass
    games = data.get("games")
    if isinstance(games, dict):
        for game, entry in games.items():
            if not isinstance(entry, dict):
                continue
            try:
                cached_at = float(entry.get("cached_at") or 0.0)
            except (TypeError, ValueError):
                cached_at = 0.0
            info["games"][str(game)] = {
                "live": str(entry.get("live") or ""),
                "latest": str(entry.get("latest") or ""),
                "cached_at": cached_at,
            }
    return info


def read_build_cache_info() -> dict[str, Any]:
    """Read the build-cache record, returning an empty record when absent."""
    try:
        if BUILD_CACHE_INFO_FILE.exists():
            with BUILD_CACHE_INFO_FILE.open("r", encoding="utf-8") as handle:
                return _normalize(json.load(handle))
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Could not read build cache info: %s", exc)
    return _empty_info()


def build_cache_entry(game: str) -> dict[str, Any] | None:
    """Return the recorded build-cache entry for *game*, if any."""
    return read_build_cache_info()["games"].get(game)


def _write_info(info: dict[str, Any]) -> None:
    try:
        BUILD_CACHE_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(info, indent=2, sort_keys=True) + "\n"
        write_bytes_atomic(BUILD_CACHE_INFO_FILE, payload.encode("utf-8"))
    except OSError as exc:
        logger.warning("Could not write build cache info: %s", exc)


def _version_pair(game: str, manifest: Any) -> tuple[str, str]:
    if not isinstance(manifest, dict):
        return "", ""
    entry = manifest.get(game)
    if not isinstance(entry, dict):
        return "", ""
    return str(entry.get("live") or ""), str(entry.get("latest") or "")


def _current_manifest() -> Any:
    try:
        return fetch_manifest()
    except Exception as exc:  # noqa: BLE001 - version labels are optional
        logger.warning("Could not read the manifest for build cache info: %s", exc)
        return {}


def record_build_cache_for_game(game: str, timestamp: float | None = None) -> None:
    """Record that *game*'s build metadata was just written to disk."""
    now = time.time() if timestamp is None else float(timestamp)
    live, latest = _version_pair(game, _current_manifest())
    with _LOCK:
        info = read_build_cache_info()
        info["games"][game] = {
            "live": live,
            "latest": latest,
            "cached_at": now,
        }
        info["last_cached"] = max(float(info.get("last_cached") or 0.0), now)
        info["version"] = 1
        _write_info(info)


def record_build_cache_snapshot(timestamp: float | None = None) -> None:
    """Record the current live/latest version of every game.

    Called after a builds preload so the info icon covers all games, even the
    ones whose current version has no build payload (GI and NTE).
    """
    now = time.time() if timestamp is None else float(timestamp)
    manifest = _current_manifest()
    if not manifest:
        return
    with _LOCK:
        info = read_build_cache_info()
        info["games"] = {}
        for game in GAMES:
            live, latest = _version_pair(game, manifest)
            info["games"][game] = {
                "live": live,
                "latest": latest,
                "cached_at": now,
            }
        info["last_cached"] = now
        info["version"] = 1
        _write_info(info)


def clear_build_cache_info() -> None:
    """Remove the build-cache record (used by Clear cache)."""
    with _LOCK:
        try:
            BUILD_CACHE_INFO_FILE.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not clear build cache info: %s", exc)
