"""Data loading thread for fetching character data."""

import time
import logging

from PySide6.QtCore import QThread, Signal

from ..api import get_all_characters_with_new_status, parse_release, GAMES

logger = logging.getLogger(__name__)


class LoadThread(QThread):
    """Thread for loading character data without blocking the UI."""

    game_loaded = Signal(str, list)
    load_finished = Signal()

    def run(self):
        """Load data for all games."""
        total_start = time.time()
        for game in GAMES.keys():
            start = time.time()
            try:
                chars = get_all_characters_with_new_status(game)

                # Sort by release date (newest first), then by ID (newest first)
                # Special handling:
                # - NEW characters should always be first (leftmost)
                # - GI Travelers (1970-01-01 or with PlayerGirl/PlayerBoy avatars): if not new -> treat as OLDEST
                # - HSR Trailblazers (ID > 8000): if not new -> treat as OLDEST
                def get_sort_key(c):
                    char_id, char_data, is_new = c
                    # Get release timestamp - pass the release field, not the whole char_data
                    release_ts = parse_release(game, char_data.get("release"))

                    # Check if this is a GI Traveler with PlayerGirl/PlayerBoy avatar
                    is_traveler_avatar = False
                    if game == "gi":
                        icon = char_data.get("icon", "")
                        if icon in [
                            "UI_AvatarIcon_PlayerGirl",
                            "UI_AvatarIcon_PlayerBoy",
                        ]:
                            is_traveler_avatar = True

                    # Special handling for GI Travelers (1970-01-01 or with PlayerGirl/PlayerBoy avatars)
                    if game == "gi" and (release_ts == 0 or is_traveler_avatar):
                        # 1970 date or Traveler avatar: if it's new, treat as newest; if not new, treat as oldest
                        sort_ts = float("inf") if is_new else float("-inf")
                    # Special handling for HSR Trailblazers (ID > 8000)
                    elif game == "hsr":
                        # Check if this is a Trailblazer (ID > 8000)
                        numeric_part = "".join(filter(str.isdigit, char_id))
                        id_num = int(numeric_part) if numeric_part else 0
                        if id_num > 8000 and not is_new:
                            # Trailblazers that are NOT new should be treated as oldest
                            sort_ts = float("-inf")
                        else:
                            # For all other HSR characters: use actual timestamp
                            sort_ts = release_ts
                    else:
                        # For all other cases (ZZZ, and GI/HSr with valid non-special dates):
                        # Higher timestamp = newer
                        sort_ts = release_ts

                    # Extract numeric part from ID for secondary sorting
                    # For newest-first sorting: higher ID = newer
                    numeric_part = "".join(filter(str.isdigit, char_id))
                    id_num = int(numeric_part) if numeric_part else 0

                    # Return tuple for sorting: (is_new, release_sort_value, id_number)
                    # We want:
                    # 1. NEW characters first (is_new = True first)
                    # 2. Then by release date (newest first - higher sort_ts)
                    # 3. Then by ID (newest first - higher id_num)
                    return (is_new, sort_ts, id_num)

                chars.sort(key=get_sort_key, reverse=True)
                elapsed = time.time() - start
                logger.info(
                    f"Loaded {len(chars)} characters for {game} in {elapsed:.3f}s"
                )
                self.game_loaded.emit(game, chars)
            except Exception as e:
                logger.error(f"Error loading {game}: {e}")
                self.game_loaded.emit(game, [])

        total_elapsed = time.time() - total_start
        logger.info(f"All data loaded in {total_elapsed:.3f}s")
        self.load_finished.emit()
