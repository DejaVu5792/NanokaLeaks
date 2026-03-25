import requests
import time
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_URL = "https://static.nanoka.cc"

# Cache directory using XDG_CACHE_HOME or fallback to ~/.cache
cache_home = os.environ.get("XDG_CACHE_HOME")
if cache_home:
    CACHE_DIR = Path(cache_home) / "nanoka_leaks"
else:
    CACHE_DIR = Path.home() / ".cache" / "nanoka_leaks"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Memory cache for manifest
_manifest_cache = None
_manifest_cache_time = 0
_MEMORY_CACHE_TIMEOUT = 300  # 5 minutes for in-memory cache
_DISK_CACHE_TIMEOUT = 86400  # 24 hours for disk cache (persist across sessions)

# Memory cache for character data: {game: {version: data}}
_character_cache = {}

# Disk cache file paths
MANIFEST_CACHE_FILE = CACHE_DIR / "manifest.json"
CHARACTER_CACHE_DIR = CACHE_DIR / "characters"
CHARACTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)

GAMES = {
    "zzz": {"name": "Zenless Zone Zero", "url": "https://zzz.nanoka.cc"},
    "hsr": {"name": "Honkai: Star Rail", "url": "https://hsr.nanoka.cc"},
    "gi": {"name": "Genshin Impact", "url": "https://gi.nanoka.cc"},
}


def fetch_manifest():
    global _manifest_cache, _manifest_cache_time
    current_time = time.time()

    # Check memory cache first
    if (
        _manifest_cache is not None
        and (current_time - _manifest_cache_time) < _MEMORY_CACHE_TIMEOUT
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
            if cache_age < _DISK_CACHE_TIMEOUT:
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
    manifest = fetch_manifest()
    return manifest[game]["latest"]


def fetch_characters(game):
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
            if ts < 100000000:
                return 0
            return ts
        except:
            return 0
    return 0


def is_released(game, char_data):
    release = char_data.get("release")
    if not release:
        if game == "zzz":
            return True
        return False

    ts = parse_release(game, release)
    return ts > 0


def get_newest_characters(game, count=6):
    data = fetch_characters(game)
    manifest = fetch_manifest()
    new_ids = manifest[game].get("new", {}).get("character", [])

    result = []
    seen_ids = set()

    if new_ids:
        for char_id in new_ids:
            char_id_str = str(char_id)
            if char_id_str in data and char_id_str not in seen_ids:
                result.append((char_id_str, data[char_id_str]))
                seen_ids.add(char_id_str)

    released_chars = [
        (id, char_data)
        for id, char_data in data.items()
        if is_released(game, char_data)
    ]

    if game == "zzz":
        released_chars.sort(
            key=lambda x: int(x[0]) if x[0].isdigit() else 0, reverse=True
        )
    else:
        released_chars.sort(
            key=lambda x: parse_release(game, x[1].get("release")), reverse=True
        )

    for char_id, char_data in released_chars:
        if char_id not in seen_ids:
            result.append((char_id, char_data))
            seen_ids.add(char_id)
        if len(result) >= count:
            break

    if len(result) < count:
        unreleased = [
            (id, char_data) for id, char_data in data.items() if id not in seen_ids
        ]
        for char_id, char_data in unreleased:
            if len(result) >= count:
                break
            result.append((char_id, char_data))

    return result[:count]


def clear_cache():
    """Clear all cached data"""
    global _manifest_cache, _manifest_cache_time, _character_cache
    _manifest_cache = None
    _manifest_cache_time = 0
    _character_cache = {}

    # Clear disk cache
    try:
        if MANIFEST_CACHE_FILE.exists():
            MANIFEST_CACHE_FILE.unlink()
        # Clear character cache files
        for cache_file in CHARACTER_CACHE_DIR.glob("*.json"):
            cache_file.unlink()
    except Exception as e:
        logger.error(f"Error clearing disk cache: {e}")


def get_character_url(game, char_id, char_data):
    if game == "zzz":
        return f"https://zzz.nanoka.cc/character/{char_id}/"
    elif game == "hsr":
        return f"https://hsr.nanoka.cc/character/{char_id}"
    elif game == "gi":
        return f"https://gi.nanoka.cc/character/{char_id}"
    return ""


def get_rarity(game, char_data):
    if game == "zzz" or game == "hsr":
        rank = char_data.get("rank", 3)
        if game == "zzz":
            return "S" if rank == 4 else "A"
        return "5" if "5" in str(rank) else "4"
    elif game == "gi":
        rank = char_data.get("rank", "QUALITY_PURPLE")
        if "ORANGE" in str(rank):
            return "5"
        return "4"
    return "?"


def get_element(game, char_data):
    if game == "zzz":
        elements = {
            200: "Physical",
            201: "Fire",
            202: "Ice",
            203: "Electric",
            204: "Ether",
            205: "Physical",
        }
        return elements.get(char_data.get("element", 200), "Physical")
    elif game == "hsr":
        return char_data.get("damageType", "Physical")
    elif game == "gi":
        elements = {
            "Pyro": "Pyro",
            "Hydro": "Hydro",
            "Anemo": "Anemo",
            "Electro": "Electro",
            "Dendro": "Dendro",
            "Cryo": "Cryo",
            "Geo": "Geo",
        }
        return elements.get(char_data.get("element", "Physical"), "Physical")
    return "Physical"


def get_name(game, char_data):
    if game == "zzz":
        name = char_data.get("en", char_data.get("code", ""))
        if name.startswith("Avatar_") or name.startswith("UI_"):
            return char_data.get("code", name).replace("_En", "")
        return name
    elif game == "hsr":
        return char_data.get("en", "Unknown")
    elif game == "gi":
        return char_data.get("en", "Unknown")
    return "Unknown"


def is_released_char(game, char_data):
    return is_released(game, char_data)


def get_character_image(game, char_data, char_id=None):
    icon = char_data.get("icon", "")
    if game == "zzz":
        return f"https://static.nanoka.cc/assets/zzz/{icon}.webp"
    elif game == "hsr":
        if char_id:
            return f"https://static.nanoka.cc/assets/hsr/avatarshopicon/{char_id}.webp"
        return f"https://static.nanoka.cc/assets/hsr/avatarshopicon/{icon}.webp"
    elif game == "gi":
        return f"https://static.nanoka.cc/assets/gi/{icon}.webp"
    return ""


def get_element_image(game, char_data):
    element = get_element(game, char_data)
    if game == "zzz":
        element_map = {
            "Physical": "Physical",
            "Fire": "Fire",
            "Ice": "Ice",
            "Electric": "Electric",
            "Ether": "Anomaly",
        }
        return f"https://static.nanoka.cc/assets/zzz/Icon{element_map.get(element, 'Physical')}.webp"
    elif game == "hsr":
        return f"https://static.nanoka.cc/assets/hsr/element/{element.lower()}.webp"
    elif game == "gi":
        return f"https://static.nanoka.cc/assets/gi/{element}.webp"
    return ""


def get_specialty_image(game, char_data):
    if game == "zzz":
        type_map = {
            1: "Attack",
            2: "Defense",
            3: "Anomaly",
            4: "Support",
            5: "Star",
        }
        specialty = type_map.get(char_data.get("type", 1), "Attack")
        return f"https://static.nanoka.cc/assets/zzz/Icon{specialty}.webp"
    elif game == "hsr":
        path = char_data.get("baseType", "")
        return f"https://static.nanoka.cc/assets/hsr/pathicon/{path.lower()}.webp"
    elif game == "gi":
        weapon = char_data.get("weapon", "")
        return f"https://static.nanoka.cc/assets/gi/{weapon}.webp"
    return ""
