"""Metadata for the recommended-build cache.

Build metadata changes with every live game release, so the settings dialog
shows when the build cache was last written.  That timestamp is the only
metadata we need to keep.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from .cache_io import write_bytes_atomic
from .constants import CACHE_DIR

logger = logging.getLogger(__name__)

BUILD_CACHE_INFO_FILE = CACHE_DIR / "build_cache_info.json"

_LOCK = threading.Lock()


def _empty_info() -> dict[str, Any]:
    return {"version": 1, "last_cached": 0.0}


def _normalize(data: Any) -> dict[str, Any]:
    info = _empty_info()
    if not isinstance(data, dict):
        return info
    try:
        info["last_cached"] = float(data.get("last_cached") or 0.0)
    except (TypeError, ValueError):
        pass
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


def build_cache_last_cached() -> float:
    """Return the last build-cache write time, or ``0.0`` when unknown."""
    return float(read_build_cache_info().get("last_cached") or 0.0)


def _write_info(info: dict[str, Any]) -> None:
    try:
        BUILD_CACHE_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(info, indent=2, sort_keys=True) + "\n"
        write_bytes_atomic(BUILD_CACHE_INFO_FILE, payload.encode("utf-8"))
    except OSError as exc:
        logger.warning("Could not write build cache info: %s", exc)


def record_build_cache_write(timestamp: float | None = None) -> None:
    """Record that build metadata was written to disk."""
    now = time.time() if timestamp is None else float(timestamp)
    with _LOCK:
        info = read_build_cache_info()
        info["last_cached"] = max(float(info.get("last_cached") or 0.0), now)
        info["version"] = 1
        _write_info(info)


def clear_build_cache_info() -> None:
    """Remove the build-cache record (used by Clear cache)."""
    with _LOCK:
        try:
            BUILD_CACHE_INFO_FILE.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not clear build cache info: %s", exc)
