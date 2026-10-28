"""Tests for persisted cache and game settings."""

from __future__ import annotations

import unittest

from nanoka_viewer import settings as app_settings


class SettingsPersistenceTests(unittest.TestCase):
    def test_builds_setting_is_preserved(self):
        normalized = app_settings._normalize(
            {"cache_character_builds": False, "cache_character_artwork": False}
        )

        self.assertFalse(normalized["cache_character_builds"])
        self.assertTrue(normalized["cache_character_details"])
        self.assertFalse(normalized["cache_character_artwork"])

    def test_games_are_enabled_by_default(self):
        normalized = app_settings._normalize({})

        self.assertEqual(normalized["disabled_games"], [])
        self.assertEqual(normalized["game_order"], list(app_settings.all_game_ids()))

    def test_disabled_games_are_preserved_and_filtered(self):
        normalized = app_settings._normalize({"disabled_games": ["hsr", "bogus"]})

        self.assertEqual(normalized["disabled_games"], ["hsr"])

    def test_game_order_is_sanitized_and_completed(self):
        normalized = app_settings._normalize(
            {"game_order": ["ww", "nope", "ww", "hsr"]}
        )

        expected = ["ww", "hsr"] + [
            game for game in app_settings.all_game_ids() if game not in {"ww", "hsr"}
        ]
        self.assertEqual(normalized["game_order"], expected)

    def test_old_settings_file_gets_all_games_enabled(self):
        normalized = app_settings._normalize({"cache_character_details": False})

        self.assertEqual(normalized["disabled_games"], [])
        self.assertEqual(normalized["game_order"], list(app_settings.all_game_ids()))


if __name__ == "__main__":
    unittest.main()
