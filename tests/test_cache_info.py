"""Tests for build-cache timestamp metadata and cache size reporting."""

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
        self._patch = patch.object(
            cache_info, "BUILD_CACHE_INFO_FILE", self.info_file
        )
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_missing_info_is_empty(self):
        info = cache_info.read_build_cache_info()

        self.assertEqual(info["last_cached"], 0.0)
        self.assertEqual(cache_info.build_cache_last_cached(), 0.0)

    def test_records_write_timestamp(self):
        cache_info.record_build_cache_write(timestamp=1000.0)

        info = cache_info.read_build_cache_info()
        self.assertEqual(info["last_cached"], 1000.0)
        self.assertEqual(cache_info.build_cache_last_cached(), 1000.0)
        self.assertTrue(self.info_file.exists())

    def test_keeps_the_latest_timestamp(self):
        cache_info.record_build_cache_write(timestamp=2000.0)
        cache_info.record_build_cache_write(timestamp=1000.0)

        self.assertEqual(cache_info.build_cache_last_cached(), 2000.0)

    def test_clear_removes_the_record(self):
        cache_info.record_build_cache_write(timestamp=1000.0)
        self.assertTrue(self.info_file.exists())

        cache_info.clear_build_cache_info()

        self.assertFalse(self.info_file.exists())
        self.assertEqual(cache_info.build_cache_last_cached(), 0.0)

    def test_bad_payload_is_normalized(self):
        self.info_file.write_text(
            '{"last_cached": "bad", "games": {"hsr": {"live": "3.8"}}}',
            encoding="utf-8",
        )

        info = cache_info.read_build_cache_info()

        self.assertEqual(info["last_cached"], 0.0)
        self.assertNotIn("games", info)

    def test_old_version_fields_are_ignored(self):
        self.info_file.write_text(
            '{"last_cached": 1234.0, "games": {"hsr": {"live": "3.8"}}}',
            encoding="utf-8",
        )

        info = cache_info.read_build_cache_info()

        self.assertEqual(info["last_cached"], 1234.0)
        self.assertNotIn("games", info)


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
