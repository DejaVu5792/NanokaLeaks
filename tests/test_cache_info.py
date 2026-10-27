"""Tests for build-cache metadata and cache size reporting."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nanoka_viewer.api import cache_info
from nanoka_viewer.api import details as details_api


class BuildCacheInfoTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.info_file = Path(self._temp.name) / "build_cache_info.json"
        self.manifest = {
            "hsr": {"live": "3.8", "latest": "3.9"},
            "ww": {"live": "2.6", "latest": "2.7"},
        }
        self._patches = [
            patch.object(cache_info, "BUILD_CACHE_INFO_FILE", self.info_file),
            patch.object(cache_info, "fetch_manifest", return_value=self.manifest),
            patch.object(
                cache_info,
                "GAMES",
                {"hsr": {"name": "HSR"}, "ww": {"name": "WW"}},
            ),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_missing_info_is_empty(self):
        info = cache_info.read_build_cache_info()

        self.assertEqual(info["last_cached"], 0.0)
        self.assertEqual(info["games"], {})

    def test_records_one_game_and_keeps_other_entries(self):
        cache_info.record_build_cache_for_game("hsr", timestamp=1000.0)
        cache_info.record_build_cache_for_game("ww", timestamp=2000.0)

        info = cache_info.read_build_cache_info()
        self.assertEqual(info["last_cached"], 2000.0)
        self.assertEqual(info["games"]["hsr"]["live"], "3.8")
        self.assertEqual(info["games"]["hsr"]["latest"], "3.9")
        self.assertEqual(info["games"]["hsr"]["cached_at"], 1000.0)
        self.assertEqual(info["games"]["ww"]["live"], "2.6")
        self.assertEqual(info["games"]["ww"]["cached_at"], 2000.0)

    def test_entry_lookup(self):
        self.assertIsNone(cache_info.build_cache_entry("hsr"))

        cache_info.record_build_cache_for_game("hsr", timestamp=1000.0)

        entry = cache_info.build_cache_entry("hsr")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["live"], "3.8")
        self.assertIsNone(cache_info.build_cache_entry("ww"))

    def test_snapshot_records_every_game(self):
        cache_info.record_build_cache_snapshot(timestamp=3000.0)

        info = cache_info.read_build_cache_info()
        self.assertEqual(info["last_cached"], 3000.0)
        self.assertEqual(set(info["games"]), {"hsr", "ww"})
        self.assertEqual(info["games"]["hsr"]["live"], "3.8")
        self.assertEqual(info["games"]["ww"]["latest"], "2.7")
        self.assertTrue(self.info_file.exists())

    def test_clear_removes_the_record(self):
        cache_info.record_build_cache_snapshot(timestamp=3000.0)
        self.assertTrue(self.info_file.exists())

        cache_info.clear_build_cache_info()

        self.assertFalse(self.info_file.exists())
        self.assertEqual(cache_info.read_build_cache_info()["games"], {})

    def test_bad_payload_is_normalized(self):
        self.info_file.write_text(
            '{"last_cached": "bad", "games": {"hsr": {"live": 3.8}, "ww": 4}}',
            encoding="utf-8",
        )

        info = cache_info.read_build_cache_info()

        self.assertEqual(info["last_cached"], 0.0)
        self.assertEqual(info["games"]["hsr"]["live"], "3.8")
        self.assertNotIn("ww", info["games"])


class CacheSizeTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        root = Path(self._temp.name)
        self.detail_dir = root / "details"
        self.metadata_dir = root / "metadata"
        self.art_dir = root / "art"
        for directory in (self.detail_dir, self.metadata_dir, self.art_dir):
            directory.mkdir()

        self._patches = [
            patch.object(details_api, "DETAIL_CACHE_DIR", self.detail_dir),
            patch.object(details_api, "METADATA_CACHE_DIR", self.metadata_dir),
            patch.object(details_api, "DETAIL_ART_CACHE_DIR", self.art_dir),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_reports_each_cache_directory_in_bytes(self):
        (self.detail_dir / "a.pkl").write_bytes(b"a" * 1024)
        (self.metadata_dir / "b.pkl").write_bytes(b"b" * 2048)
        (self.art_dir / "c.bin").write_bytes(b"c" * 3072)
        (self.art_dir / "nested").mkdir()
        (self.art_dir / "nested" / "d.bin").write_bytes(b"d" * 512)

        sizes = details_api.cache_sizes()

        self.assertEqual(sizes["details"], 1024)
        self.assertEqual(sizes["builds"], 2048)
        self.assertEqual(sizes["artwork"], 3072 + 512)


if __name__ == "__main__":
    unittest.main()
