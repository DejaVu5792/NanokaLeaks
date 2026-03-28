"""Nanoka API module for fetching and caching game data."""

from .constants import BASE_URL, CACHE_DIR, GAMES
from .manifest import fetch_manifest, get_latest_version
from .characters import (
    fetch_characters,
    get_newest_characters,
    get_all_characters_with_new_status,
    parse_release,
    is_released,
    clear_cache,
)
from .models import (
    get_character_url,
    get_rarity,
    get_element,
    get_name,
    get_character_image,
    get_element_image,
    get_specialty_image,
)

__all__ = [
    # Constants
    "BASE_URL",
    "CACHE_DIR",
    "GAMES",
    # Manifest
    "fetch_manifest",
    "get_latest_version",
    # Characters
    "fetch_characters",
    "get_newest_characters",
    "get_all_characters_with_new_status",
    "parse_release",
    "is_released",
    "clear_cache",
    # Models
    "get_character_url",
    "get_rarity",
    "get_element",
    "get_name",
    "get_character_image",
    "get_element_image",
    "get_specialty_image",
]
