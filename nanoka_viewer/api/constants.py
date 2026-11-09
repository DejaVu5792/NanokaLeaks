"""API constants and configuration."""

import os
from pathlib import Path

BASE_URL = "https://static.nanoka.cc"

# Keep the version in sync with pyproject.toml; it is only used to identify the
# client to static.nanoka.cc.
APP_VERSION = "6.1.1"
USER_AGENT = f"NanokaLeaks/{APP_VERSION} (+https://nanoka.cc)"

# Cache directory using XDG_CACHE_HOME or fallback to ~/.cache
cache_home = os.environ.get("XDG_CACHE_HOME")
if cache_home:
    CACHE_DIR = Path(cache_home) / "nanoka_leaks"
else:
    CACHE_DIR = Path.home() / ".cache" / "nanoka_leaks"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Disk cache file paths
MANIFEST_CACHE_FILE = CACHE_DIR / "manifest.json"
CHARACTER_CACHE_DIR = CACHE_DIR / "characters"
CHARACTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache timeouts (in seconds)
MEMORY_CACHE_TIMEOUT = 300  # 5 minutes for in-memory cache
DISK_CACHE_TIMEOUT = 86400  # 24 hours for disk cache (persist across sessions)

# Genshin Impact ships two non-playable variants that the card list and the
# preloader both hide.  Keep the prefixes in one place so the two paths cannot
# disagree about which characters exist.
MANEKIN_PREFIXES = ("10000118-", "10000117-")


def is_manekin(char_id: str) -> bool:
    """Return whether *char_id* is a hidden Manekina/Manekin variant."""
    return str(char_id).startswith(MANEKIN_PREFIXES)

# Game configuration
GAMES = {
    "zzz": {"name": "Zenless Zone Zero", "url": "https://zzz.nanoka.cc"},
    "hsr": {"name": "Honkai: Star Rail", "url": "https://hsr.nanoka.cc"},
    "gi": {"name": "Genshin Impact", "url": "https://gi.nanoka.cc"},
    "ww": {"name": "Wuthering Waves", "url": "https://ww.nanoka.cc"},
    "nte": {"name": "Neverness to Everness", "url": "https://nte.nanoka.cc"},
}
