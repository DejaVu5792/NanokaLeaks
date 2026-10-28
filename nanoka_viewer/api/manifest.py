"""Manifest fetching and caching."""

import json
import time
import logging

import requests

from .constants import (
    BASE_URL,
    MANIFEST_CACHE_FILE,
    MEMORY_CACHE_TIMEOUT,
    DISK_CACHE_TIMEOUT,
)

logger = logging.getLogger(__name__)

# Memory cache for manifest
_manifest_cache = None
_manifest_cache_time = 0


def fetch_manifest():
    """Fetch the manifest with caching (memory and disk)."""
    global _manifest_cache, _manifest_cache_time
    current_time = time.time()

    # Check memory cache first
    if (
        _manifest_cache is not None
        and (current_time - _manifest_cache_time) < MEMORY_CACHE_TIMEOUT
    ):
        logger.debug(
            f"Using cached manifest from memory (age: {current_time - _manifest_cache_time:.1f}s)"
        )
        return _manifest_cache

    # Check disk cache
    try:
        if MANIFEST_CACHE_FILE.exists():
            # Check if disk cache is still valid
            cache_age = current_time - MANIFEST_CACHE_FILE.stat().st_mtime
            if cache_age < DISK_CACHE_TIMEOUT:
                with open(MANIFEST_CACHE_FILE, "r") as f:
                    data = json.load(f)
                logger.info(f"Using cached manifest from disk (age: {cache_age:.1f}s)")
                # Update memory cache
                _manifest_cache = data
                _manifest_cache_time = current_time
                return data
    except Exception as e:
        logger.error(f"Error reading disk cache: {e}")

    # Fetch new manifest
    logger.info("Fetching new manifest from network")
    response = requests.get(f"{BASE_URL}/manifest.json", timeout=30)
    response.raise_for_status()
    data = response.json()

    # Update caches
    _manifest_cache = data
    _manifest_cache_time = current_time
    try:
        with open(MANIFEST_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error writing disk cache: {e}")

    return data


def get_latest_version(game):
    """Get the latest version for a game from the manifest."""
    manifest = fetch_manifest()
    return manifest[game]["latest"]


def cached_latest_version(game):
    """Return the latest known version without ever touching the network.

    ``get_latest_version`` may block on an HTTP request when both caches are
    cold or stale.  Callers that only want a cheap "is this cached?" probe can
    use this instead: it checks the memory cache and then the on-disk manifest,
    regardless of the disk cache's age, and returns ``None`` when neither is
    available.  It deliberately does not refresh ``_manifest_cache`` so a stale
    on-disk manifest cannot postpone the normal revalidation.
    """
    if _manifest_cache is not None:
        try:
            return str(_manifest_cache[game]["latest"])
        except (KeyError, TypeError):
            return None

    try:
        if MANIFEST_CACHE_FILE.exists():
            with open(MANIFEST_CACHE_FILE, "r") as f:
                data = json.load(f)
            return str(data[game]["latest"])
    except Exception as exc:  # noqa: BLE001 - a missing cache is not an error
        logger.debug("Could not read cached manifest: %s", exc)
    return None


def clear_manifest_cache():
    """Clear manifest cache (memory and disk)."""
    global _manifest_cache, _manifest_cache_time
    _manifest_cache = None
    _manifest_cache_time = 0
    try:
        if MANIFEST_CACHE_FILE.exists():
            MANIFEST_CACHE_FILE.unlink()
            logger.info("Manifest disk cache cleared")
    except Exception as e:
        logger.error(f"Error clearing manifest disk cache: {e}")
