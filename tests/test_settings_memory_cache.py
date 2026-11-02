"""Tests for the in-memory settings snapshot.

``get_setting`` sits on the hot detail/artwork/preload paths, so the JSON file
must be parsed once and only re-read when it actually changes.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nanoka_viewer import settings as app_settings


class SettingsMemoryCacheTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        root = Path(self._temp.name)
        self.settings_file = root / "settings.json"
        self._patches = [
            patch.object(app_settings, "SETTINGS_DIR", root),
            patch.object(app_settings, "SETTINGS_FILE", self.settings_file),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        app_settings.clear_settings_cache()
        self.addCleanup(app_settings.clear_settings_cache)

    def _write(self, payload: dict) -> None:
        self.settings_file.write_text(json.dumps(payload), encoding="utf-8")

    def test_repeated_reads_parse_the_file_once(self):
        self._write({"cache_character_details": False})

        with patch.object(app_settings.json, "load", wraps=json.load) as loader:
            self.assertFalse(app_settings.get_setting("cache_character_details"))
            self.assertTrue(app_settings.get_setting("cache_character_builds"))

        self.assertEqual(loader.call_count, 1)

    def test_changed_file_is_picked_up(self):
        self._write({"cache_character_details": True})
        self.assertTrue(app_settings.get_setting("cache_character_details"))

        # A different size guarantees a different stamp even on filesystems
        # with coarse mtime resolution.
        self._write({"cache_character_details": False, "changed": True})

        self.assertFalse(app_settings.get_setting("cache_character_details"))

    def test_save_updates_the_cache_without_a_reread(self):
        app_settings.save_settings({"cache_character_details": False})

        with patch.object(
            app_settings.json, "load", side_effect=AssertionError("file read")
        ):
            self.assertFalse(app_settings.get_setting("cache_character_details"))

    def test_clear_settings_cache_forces_a_reread(self):
        self._write({"cache_character_details": False})
        self.assertFalse(app_settings.get_setting("cache_character_details"))

        app_settings.clear_settings_cache()

        with patch.object(app_settings.json, "load", wraps=json.load) as loader:
            app_settings.get_setting("cache_character_details")

        self.assertEqual(loader.call_count, 1)

    def test_returned_lists_cannot_mutate_the_cached_value(self):
        loaded = app_settings.load_settings()
        loaded["game_order"].clear()
        loaded["disabled_games"].append("zzz")

        self.assertEqual(
            app_settings.load_settings()["game_order"],
            list(app_settings.all_game_ids()),
        )
        self.assertNotIn("zzz", app_settings.load_settings()["disabled_games"])


if __name__ == "__main__":
    unittest.main()
