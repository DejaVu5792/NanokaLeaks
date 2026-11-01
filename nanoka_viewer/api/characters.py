"""Character data fetching and caching."""

import json
import logging
import re

import requests

from .constants import BASE_URL, CHARACTER_CACHE_DIR
from .manifest import (
    cached_latest_version,
    clear_manifest_cache,
    fetch_manifest,
    get_latest_version,
)
from .models import get_name

logger = logging.getLogger(__name__)

# Memory cache for character data: {game: {version: data}}
_character_cache = {}


def _version_key(version: str) -> tuple[int, ...]:
    """Return a sortable key for version strings such as ``"4.0"``."""
    return tuple(int(part) for part in re.findall(r"\d+", str(version)))


def cached_versions(game: str) -> list[str]:
    """Return every character version cached on disk for *game*, newest first."""
    versions = []
    try:
        for path in CHARACTER_CACHE_DIR.glob(f"{game}_*.json"):
            version = path.name[len(game) + 1 : -len(".json")]
            if version:
                versions.append(version)
    except OSError as exc:
        logger.debug("Could not list character cache for %s: %s", game, exc)
    return sorted(versions, key=_version_key, reverse=True)


def _newest_cached_version(game: str) -> str | None:
    """Return the newest character version cached on disk for *game*.

    Used as an offline fallback when the manifest cannot be refreshed or names
    a version whose character file was never downloaded.
    """
    versions = cached_versions(game)
    return versions[0] if versions else None


def _read_character_cache(game: str, version: str):
    """Load one character cache file, or return ``None`` when unusable."""
    cache_file = CHARACTER_CACHE_DIR / f"{game}_{version}.json"
    try:
        if not cache_file.exists():
            return None
        with open(cache_file, "r") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.error(
            "Error reading character disk cache for %s version %s: %s",
            game,
            version,
            exc,
        )
        return None
    return data


def _remember(game: str, version: str, data) -> None:
    _character_cache.setdefault(game, {})[version] = data


def fetch_characters(game):
    """Fetch character data for a game with caching.

    When the network is unavailable the newest cached character file is used
    instead, even if the manifest on disk is older than its freshness window or
    names a version whose file was never downloaded.
    """
    try:
        version = get_latest_version(game)
    except (requests.RequestException, KeyError, TypeError) as exc:
        cached_version = _newest_cached_version(game)
        if cached_version is None:
            raise
        logger.warning(
            "Could not resolve the latest version for %s (%s); "
            "falling back to cached version %s",
            game,
            exc,
            cached_version,
        )
        version = cached_version

    # Check memory cache first
    if game in _character_cache and version in _character_cache[game]:
        logger.debug(
            f"Using cached character data from memory for {game} version {version}"
        )
        return _character_cache[game][version]

    # Check disk cache
    data = _read_character_cache(game, version)
    if data is not None:
        logger.info(
            f"Using cached character data from disk for {game} version {version}"
        )
        _remember(game, version, data)
        return data

    # Fetch from network
    logger.info(f"Fetching new character data for {game} version {version}")
    url = f"{BASE_URL}/{game}/{version}/character.json"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        # The manifest may name a version we have never downloaded.  Anything
        # already on disk is better than an empty screen while offline.
        cached_version = _newest_cached_version(game)
        if cached_version is not None and cached_version != version:
            cached = _read_character_cache(game, cached_version)
            if cached is not None:
                logger.warning(
                    "Could not fetch %s characters for version %s; "
                    "using cached version %s",
                    game,
                    version,
                    cached_version,
                )
                _remember(game, cached_version, cached)
                return cached
        raise

    # Update caches
    _remember(game, version, data)
    try:
        character_cache_file = CHARACTER_CACHE_DIR / f"{game}_{version}.json"
        with open(character_cache_file, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(
            f"Error writing character disk cache for {game} version {version}: {e}"
        )

    return data


def cached_character_count(game):
    """Return how many characters are cached for *game* without networking.

    Returns ``None`` when no character data has been downloaded yet.  Like
    :func:`get_all_characters_with_new_status`, the Genshin Manekina/Manekin
    variants are excluded so the number matches what the viewer displays.
    """
    version = cached_latest_version(game)
    if version is None:
        return None

    data = _character_cache.get(game, {}).get(version)
    if data is None:
        cache_file = CHARACTER_CACHE_DIR / f"{game}_{version}.json"
        try:
            if not cache_file.exists():
                return None
            with open(cache_file, "r") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            logger.debug("Could not read character cache for %s: %s", game, exc)
            return None

    if not isinstance(data, dict):
        return None
    if game == "gi":
        return sum(
            1
            for char_id in data
            if not char_id.startswith("10000118-")
            and not char_id.startswith("10000117-")
        )
    return len(data)


def parse_release(game, release_data):
    """Parse release date string to timestamp."""
    if not release_data:
        return 0

    if game == "gi":
        from datetime import datetime

        try:
            dt = datetime.strptime(release_data, "%Y-%m-%d %H:%M:%S")
            ts = dt.timestamp()
            if ts < 100000000:
                return 0
            return ts
        except:
            return 0
    elif game == "hsr":
        try:
            ts = int(release_data)
            # Convert from milliseconds to seconds
            ts = ts / 1000
            if ts < 100000000:
                return 0
            return ts
        except:
            return 0
    return 0


def is_released(game, char_data):
    """Check if a character is released."""
    release = char_data.get("release")
    if not release:
        if game == "zzz":
            return True
        return False

    ts = parse_release(game, release)
    return ts > 0


def get_newest_characters(game):
    """Get only the newest characters for a game."""
    data = fetch_characters(game)
    manifest = fetch_manifest()
    new_ids = manifest[game].get("new", {}).get("character", [])

    result = []
    if new_ids:
        for char_id in new_ids:
            char_id_str = str(char_id)
            if char_id_str in data:
                result.append((char_id_str, data[char_id_str]))

    return result


def get_all_characters_with_new_status(game):
    """
    Get all characters for a game with their new status.
    Returns: List of tuples (char_id, char_data, is_new)
    """
    # Get manifest to know which characters are new
    manifest = fetch_manifest()
    new_ids_raw = manifest[game].get("new", {}).get("character", [])
    new_ids = set(str(char_id) for char_id in new_ids_raw)
    logger.info(f"New character IDs for {game}: {list(new_ids)} (raw: {new_ids_raw})")

    # Get all character data
    data = fetch_characters(game)

    # Filter out Manekina and Manekin for GI (as requested)
    if game == "gi":
        # Remove Manekina variants (IDs starting with 10000118-)
        # Remove Manekin variants (IDs starting with 10000117-)
        original_count = len(data)
        data = {
            k: v
            for k, v in data.items()
            if not k.startswith("10000118-") and not k.startswith("10000117-")
        }
        filtered_count = len(data)
        logger.info(
            f"After filtering out Manekina/Manekin: {filtered_count} characters for GI "
            f"(removed {original_count - filtered_count} characters)"
        )

    logger.info(f"Total characters for {game}: {len(data)}")
    logger.info(f"Sample character IDs: {list(data.keys())[:5]}")

    # Process all characters
    result = []
    new_count = 0
    for char_id_str, char_data in data.items():
        is_new = char_id_str in new_ids
        if is_new:
            new_count += 1
            logger.info(
                f"Found new character: {char_id_str} - {get_name(game, char_data, char_id_str)}"
            )
        result.append((char_id_str, char_data, is_new))

    logger.info(f"Found {new_count} new characters out of {len(data)} total for {game}")
    return result


def clear_cache():
    """Clear all cached data (manifest and characters)."""
    global _character_cache
    _character_cache = {}
    clear_manifest_cache()
    try:
        from .details import clear_detail_cache

        clear_detail_cache()
    except Exception as e:
        logger.error(f"Error clearing detail cache: {e}")

    # Clear character disk cache
    try:
        for cache_file in CHARACTER_CACHE_DIR.glob("*.json"):
            cache_file.unlink()
        logger.info("Character disk cache cleared")
    except Exception as e:
        logger.error(f"Error clearing character disk cache: {e}")
