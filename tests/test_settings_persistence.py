"""Tests for persisted cache settings."""

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


if __name__ == "__main__":
    unittest.main()
