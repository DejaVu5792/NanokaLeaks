"""Tests for the detail/artwork cache write behaviour."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nanoka_viewer.api import details as details_api


class DetailCacheRememberTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        root = Path(self._temp.name)
        self.detail_dir = root / "details"
        self.metadata_dir = root / "metadata"
        self.art_dir = root / "art"
        for directory in (self.detail_dir, self.metadata_dir, self.art_dir):
            directory.mkdir()

        self._detail_cache = details_api._detail_cache
        self._art_cache = details_api._art_cache
        details_api._detail_cache = {}
        details_api._art_cache = {}
        self.addCleanup(self._restore_caches)

        self._patches = [
            patch.object(details_api, "DETAIL_CACHE_DIR", self.detail_dir),
            patch.object(details_api, "METADATA_CACHE_DIR", self.metadata_dir),
            patch.object(details_api, "DETAIL_ART_CACHE_DIR", self.art_dir),
            patch.object(details_api, "get_latest_version", return_value="1.0"),
            patch.object(details_api, "get_setting", return_value=True),
            patch.object(
                details_api,
                "_get_json",
                return_value={
                    "name": "Test",
                    "desc": "A test character.",
                    "rarity": "5",
                },
            ),
            patch.object(details_api, "_get_bytes", return_value=b"artwork"),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _restore_caches(self):
        details_api._detail_cache = self._detail_cache
        details_api._art_cache = self._art_cache

    def test_remember_false_writes_disk_without_pinning_memory(self):
        detail = details_api.load_character_detail("hsr", "1", remember=False)

        self.assertEqual(detail.name, "Test")
        self.assertEqual(details_api._detail_cache, {})
        files = list(self.detail_dir.glob("*.pkl"))
        self.assertEqual(len(files), 1, "the detail should still be written to disk")

    def test_remember_true_uses_the_memory_cache(self):
        details_api.load_character_detail("hsr", "1", remember=True)

        self.assertIn(("hsr", "1.0", "1"), details_api._detail_cache)

    def test_artwork_remember_false_writes_disk_without_pinning_memory(self):
        data = details_api.load_character_art("https://example/art.webp", remember=False)

        self.assertEqual(data, b"artwork")
        self.assertEqual(details_api._art_cache, {})
        files = list(self.art_dir.glob("*.bin"))
        self.assertEqual(len(files), 1, "the artwork should still be written to disk")

    def test_artwork_remember_true_fills_the_memory_cache(self):
        details_api.load_character_art("https://example/art.webp", remember=True)

        self.assertIn("https://example/art.webp", details_api._art_cache)


if __name__ == "__main__":
    unittest.main()
