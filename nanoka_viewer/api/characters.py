"""Character data fetching and caching."""

import json
import logging

import requests

from .constants import BASE_URL, CHARACTER_CACHE_DIR
from .manifest import fetch_manifest, get_latest_version
from .models import get_name

logger = logging.getLogger(__name__)

# Memory cache for character data: {game: {version: data}}
_character_cache = {}


def fetch_characters(game):
    """Fetch character data for a game with caching."""
    version = get_latest_version(game)

    # Check memory cache first
    if game in _character_cache and version in _character_cache[game]:
        logger.debug(
            f"Using cached character data from memory for {game} version {version}"
        )
        return _character_cache[game][version]

    # Check disk cache
    try:
        character_cache_file = CHARACTER_CACHE_DIR / f"{game}_{version}.json"
        if character_cache_file.exists():
            # Check if disk cache is still valid by comparing with manifest
            manifest_data = (
                fetch_manifest()
            )  # This will use cached manifest if available
            latest_version = manifest_data[game]["latest"]
            if latest_version == version:  # Only use cache if version matches latest
                with open(character_cache_file, "r") as f:
                    data = json.load(f)
                logger.info(
                    f"Using cached character data from disk for {game} version {version}"
                )
                # Update memory cache
                if game not in _character_cache:
                    _character_cache[game] = {}
                _character_cache[game][version] = data
                return data
    except Exception as e:
        logger.error(
            f"Error reading character disk cache for {game} version {version}: {e}"
        )

    # Fetch from network
    logger.info(f"Fetching new character data for {game} version {version}")
    url = f"{BASE_URL}/{game}/{version}/character.json"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    # Update caches
    if game not in _character_cache:
        _character_cache[game] = {}
    _character_cache[game][version] = data
    try:
        character_cache_file = CHARACTER_CACHE_DIR / f"{game}_{version}.json"
        with open(character_cache_file, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(
            f"Error writing character disk cache for {game} version {version}: {e}"
        )

    return data


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
    """Clear all cached data."""
    global _manifest_cache, _manifest_cache_time, _character_cache
    _manifest_cache = None
    _manifest_cache_time = 0
    _character_cache = {}

    # Clear disk cache
    try:
        from .constants import MANIFEST_CACHE_FILE

        if MANIFEST_CACHE_FILE.exists():
            MANIFEST_CACHE_FILE.unlink()
        # Clear character cache files
        for cache_file in CHARACTER_CACHE_DIR.glob("*.json"):
            cache_file.unlink()
    except Exception as e:
        logger.error(f"Error clearing disk cache: {e}")
