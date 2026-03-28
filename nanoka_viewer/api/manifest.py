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
