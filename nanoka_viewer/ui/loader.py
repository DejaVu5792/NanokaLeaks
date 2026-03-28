"""Data loading thread for fetching character data."""

import time
import logging
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, Signal

from ..api import get_all_characters_with_new_status, parse_release, GAMES

logger = logging.getLogger(__name__)


class LoadThread(QThread):
    """Thread for loading character data without blocking the UI."""

    game_loaded = Signal(str, list)
    load_finished = Signal()

    def _get_sort_key(self, game, c):
        """Calculate sort key for a character."""
        char_id, char_data, is_new = c
        release_ts = parse_release(game, char_data.get("release"))

        is_traveler_avatar = False
        if game == "gi":
            icon = char_data.get("icon", "")
            if icon in ["UI_AvatarIcon_PlayerGirl", "UI_AvatarIcon_PlayerBoy"]:
                is_traveler_avatar = True

        if game == "gi" and (release_ts == 0 or is_traveler_avatar):
            sort_ts = float("inf") if is_new else float("-inf")
        elif game == "hsr":
            numeric_part = "".join(filter(str.isdigit, char_id))
            id_num = int(numeric_part) if numeric_part else 0
            if id_num > 8000 and not is_new:
                sort_ts = float("-inf")
            else:
                sort_ts = release_ts
        else:
            sort_ts = release_ts

        numeric_part = "".join(filter(str.isdigit, char_id))
        id_num = int(numeric_part) if numeric_part else 0

        return (is_new, sort_ts, id_num)

    def _load_game(self, game):
        """Fetch and process data for a single game."""
        start = time.time()
        try:
            chars = get_all_characters_with_new_status(game)
            chars.sort(key=lambda c: self._get_sort_key(game, c), reverse=True)
            elapsed = time.time() - start
            logger.info(f"Loaded {len(chars)} characters for {game} in {elapsed:.3f}s")
            self.game_loaded.emit(game, chars)
        except Exception as e:
            logger.error(f"Error loading {game}: {e}")
            self.game_loaded.emit(game, [])

    def run(self):
        """Load data for all games in parallel."""
        total_start = time.time()
        
        # Use ThreadPoolExecutor to fetch games in parallel
        with ThreadPoolExecutor(max_workers=len(GAMES)) as executor:
            executor.map(self._load_game, GAMES.keys())

        total_elapsed = time.time() - total_start
        logger.info(f"All data loaded in {total_elapsed:.3f}s")
        self.load_finished.emit()
