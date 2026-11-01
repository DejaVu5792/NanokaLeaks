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


def _read_manifest_cache():
    """Return the on-disk manifest, or ``None`` when it cannot be used."""
    try:
        with open(MANIFEST_CACHE_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Error reading disk cache: {e}")
        return None
    return data if isinstance(data, dict) else None


def fetch_manifest():
    """Fetch the manifest with caching (memory and disk).

    A stale on-disk manifest is still used when the network is unavailable.
    The freshness window only decides when to *revalidate*, not whether cached
    data may be served at all: without the fallback, being offline for more
    than a day made every cached character and detail unreachable.
    """
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

    # Read the disk cache once: it is either fresh enough to skip the network
    # or the fallback when the network request fails.
    disk_data = _read_manifest_cache()
    if disk_data is not None:
        try:
            cache_age = current_time - MANIFEST_CACHE_FILE.stat().st_mtime
        except OSError:
            cache_age = 0.0
        if cache_age < DISK_CACHE_TIMEOUT:
            logger.info(f"Using cached manifest from disk (age: {cache_age:.1f}s)")
            # Update memory cache
            _manifest_cache = disk_data
            _manifest_cache_time = current_time
            return disk_data

    # Fetch new manifest
    logger.info("Fetching new manifest from network")
    try:
        response = requests.get(f"{BASE_URL}/manifest.json", timeout=30)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        if disk_data is None:
            raise
        logger.warning(
            "Could not refresh the manifest (%s); using the cached copy from disk",
            exc,
        )
        # Cache the fallback in memory too, so each game load does not wait for
        # another connection timeout while we stay offline.
        _manifest_cache = disk_data
        _manifest_cache_time = current_time
        return disk_data

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
