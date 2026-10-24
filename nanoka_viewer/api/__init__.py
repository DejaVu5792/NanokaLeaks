"""Nanoka API module for fetching and caching game data."""

from .characters import (
    clear_cache,
    fetch_characters,
    get_all_characters_with_new_status,
    get_newest_characters,
    is_released,
    parse_release,
)
from .constants import BASE_URL, CACHE_DIR, GAMES
from .details import (
    BuildSection,
    CharacterDetail,
    ContentEntry,
    DetailUnavailable,
    ExtraSection,
    SkillDetail,
    load_character_detail,
)
from .manifest import fetch_manifest, get_latest_version
from .models import (
    get_character_image,
    get_character_url,
    get_element,
    get_element_image,
    get_name,
    get_rarity,
    get_specialty_image,
)

__all__ = [
    "BASE_URL",
    "CACHE_DIR",
    "GAMES",
    "BuildSection",
    "CharacterDetail",
    "ContentEntry",
    "DetailUnavailable",
    "ExtraSection",
    "SkillDetail",
    "clear_cache",
    "fetch_characters",
    "fetch_manifest",
    "get_all_characters_with_new_status",
    "get_character_image",
    "get_character_url",
    "get_element",
    "get_element_image",
    "get_latest_version",
    "get_name",
    "get_newest_characters",
    "get_rarity",
    "get_specialty_image",
    "is_released",
    "load_character_detail",
    "parse_release",
]
