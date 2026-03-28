"""API constants and configuration."""

import os
from pathlib import Path

BASE_URL = "https://static.nanoka.cc"

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

# Game configuration
GAMES = {
    "zzz": {"name": "Zenless Zone Zero", "url": "https://zzz.nanoka.cc"},
    "hsr": {"name": "Honkai: Star Rail", "url": "https://hsr.nanoka.cc"},
    "gi": {"name": "Genshin Impact", "url": "https://gi.nanoka.cc"},
}
