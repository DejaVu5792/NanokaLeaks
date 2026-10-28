"""Tests for the network-free cached character count helper."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nanoka_viewer.api.characters as characters_api


class CachedCharacterCountTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.cache_dir = Path(self._temp.name)
        self._saved_memory = characters_api._character_cache
        characters_api._character_cache = {}
        self.addCleanup(self._restore_memory)

        self._patches = [
            patch.object(characters_api, "CHARACTER_CACHE_DIR", self.cache_dir),
            patch.object(characters_api, "cached_latest_version", return_value="1.0"),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _restore_memory(self):
        characters_api._character_cache = self._saved_memory

    def _write_cache(self, game: str, data: dict) -> None:
        path = self.cache_dir / f"{game}_1.0.json"
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_returns_none_without_a_known_version(self):
        with patch.object(characters_api, "cached_latest_version", return_value=None):
            self.assertIsNone(characters_api.cached_character_count("hsr"))

    def test_returns_none_when_the_game_has_not_been_cached(self):
        self.assertIsNone(characters_api.cached_character_count("hsr"))

    def test_counts_characters_from_the_disk_cache(self):
        self._write_cache("hsr", {"1": {}, "2": {}, "3": {}})

        self.assertEqual(characters_api.cached_character_count("hsr"), 3)

    def test_counts_use_the_in_memory_cache_first(self):
        characters_api._character_cache = {"hsr": {"1.0": {"1": {}, "2": {}}}}

        self.assertEqual(characters_api.cached_character_count("hsr"), 2)

    def test_genshin_variants_are_excluded_like_the_viewer_list(self):
        self._write_cache(
            "gi",
            {
                "10000001": {},
                "10000117-1": {},
                "10000118-1": {},
            },
        )

        self.assertEqual(characters_api.cached_character_count("gi"), 1)

    def test_malformed_cache_is_ignored(self):
        (self.cache_dir / "hsr_1.0.json").write_text("not json", encoding="utf-8")

        self.assertIsNone(characters_api.cached_character_count("hsr"))


if __name__ == "__main__":
    unittest.main()
