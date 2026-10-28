"""Tests for the network-free cache probes used by the details popup.

Each probe mirrors the caching rules of its loader, so a probe hit means the
loader can serve the data without a skeleton screen.  A probe must never touch
the network and must respect the individual cache settings.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import nanoka_viewer.api.details as details_api
import nanoka_viewer.api.manifest as manifest_api
from nanoka_viewer.api.details import BuildContext, CharacterDetail


def make_detail(
    *,
    game: str = "hsr",
    raw: dict | None = None,
    build_context: bool = False,
) -> CharacterDetail:
    return CharacterDetail(
        game=game,
        char_id="1",
        name="Test",
        subtitle="",
        overview="",
        level_label="Lv. 1",
        build_context=(BuildContext(game, "1.0", raw) if build_context else None),
    )


class ProbeTestCase(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        root = Path(self._temp.name)
        self.detail_dir = root / "details"
        self.metadata_dir = root / "metadata"
        self.art_dir = root / "art"
        for directory in (self.detail_dir, self.metadata_dir, self.art_dir):
            directory.mkdir()

        self._saved_caches = (
            details_api._detail_cache,
            details_api._metadata_cache,
            details_api._art_cache,
        )
        details_api._detail_cache = {}
        details_api._metadata_cache = {}
        details_api._art_cache = {}

        self.settings = {
            "cache_character_details": True,
            "cache_character_builds": True,
            "cache_character_artwork": True,
        }

        self._patches = [
            patch.object(details_api, "DETAIL_CACHE_DIR", self.detail_dir),
            patch.object(details_api, "METADATA_CACHE_DIR", self.metadata_dir),
            patch.object(details_api, "DETAIL_ART_CACHE_DIR", self.art_dir),
            patch.object(
                details_api,
                "cached_latest_version",
                return_value="1.0",
            ),
            patch.object(
                details_api,
                "get_setting",
                side_effect=lambda key: self.settings.get(key, True),
            ),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self._restore_caches)

    def _restore_caches(self):
        (
            details_api._detail_cache,
            details_api._metadata_cache,
            details_api._art_cache,
        ) = self._saved_caches


class DetailProbeTests(ProbeTestCase):
    def test_memory_hit_is_used_even_when_disk_caching_is_disabled(self):
        details_api._detail_cache[("hsr", "1.0", "1")] = make_detail()
        self.settings["cache_character_details"] = False

        self.assertTrue(details_api.has_cached_detail("hsr", "1"))

    def test_disk_hit_counts_when_the_setting_is_enabled(self):
        path = details_api._detail_disk_path(("hsr", "1.0", "1"))
        path.write_bytes(b"cached")

        self.assertTrue(details_api.has_cached_detail("hsr", "1"))

    def test_disk_hit_is_ignored_when_the_setting_is_disabled(self):
        path = details_api._detail_disk_path(("hsr", "1.0", "1"))
        path.write_bytes(b"cached")
        self.settings["cache_character_details"] = False

        self.assertFalse(details_api.has_cached_detail("hsr", "1"))

    def test_miss_returns_false(self):
        self.assertFalse(details_api.has_cached_detail("hsr", "1"))

    def test_unknown_version_returns_false(self):
        with patch.object(details_api, "cached_latest_version", return_value=None):
            self.assertFalse(details_api.has_cached_detail("hsr", "1"))


class BuildProbeTests(ProbeTestCase):
    _HSR_RAW: ClassVar[dict] = {"relics": [{"id": "1"}]}

    def _detail(self):
        return make_detail(raw=self._HSR_RAW, build_context=True)

    def _cache_all_resources(self):
        for resource in ("relicset", "lightcone", "character"):
            details_api._metadata_cache[("hsr", "1.0", resource)] = {}

    def test_memory_hit(self):
        self._cache_all_resources()

        self.assertTrue(details_api.has_cached_build(self._detail()))

    def test_disk_hit(self):
        for resource in ("relicset", "lightcone", "character"):
            details_api._metadata_disk_path(("hsr", "1.0", resource)).write_bytes(
                b"cached"
            )

        self.assertTrue(details_api.has_cached_build(self._detail()))

    def test_partial_disk_hit_is_a_miss(self):
        details_api._metadata_disk_path(("hsr", "1.0", "relicset")).write_bytes(b"x")
        details_api._metadata_disk_path(("hsr", "1.0", "lightcone")).write_bytes(b"x")

        self.assertFalse(details_api.has_cached_build(self._detail()))

    def test_disk_hit_is_ignored_when_the_setting_is_disabled(self):
        for resource in ("relicset", "lightcone", "character"):
            details_api._metadata_disk_path(("hsr", "1.0", resource)).write_bytes(
                b"cached"
            )
        self.settings["cache_character_builds"] = False

        self.assertFalse(details_api.has_cached_build(self._detail()))

    def test_detail_without_a_build_has_nothing_to_wait_for(self):
        self.assertTrue(details_api.has_cached_build(make_detail()))

    def test_build_context_without_build_data_has_nothing_to_wait_for(self):
        detail = make_detail(raw={}, build_context=True)

        self.assertTrue(details_api.has_cached_build(detail))

    def test_other_games_use_their_own_resource(self):
        raw = {"recommend": {"weapon": {"id": "1"}}}
        detail = make_detail(game="ww", raw=raw, build_context=True)
        details_api._metadata_disk_path(("ww", "1.0", "weapon")).write_bytes(b"x")

        self.assertTrue(details_api.has_cached_build(detail))


class ArtProbeTests(ProbeTestCase):
    URL = "https://example.test/art.webp"

    def test_memory_hit_is_used_even_when_disk_caching_is_disabled(self):
        details_api._art_cache[self.URL] = b"art"
        self.settings["cache_character_artwork"] = False

        self.assertTrue(details_api.has_cached_art(self.URL))

    def test_disk_hit_counts_when_the_setting_is_enabled(self):
        details_api._art_disk_path(self.URL).write_bytes(b"art")

        self.assertTrue(details_api.has_cached_art(self.URL))

    def test_disk_hit_is_ignored_when_the_setting_is_disabled(self):
        details_api._art_disk_path(self.URL).write_bytes(b"art")
        self.settings["cache_character_artwork"] = False

        self.assertFalse(details_api.has_cached_art(self.URL))

    def test_empty_url_is_a_miss(self):
        self.assertFalse(details_api.has_cached_art(""))

    def test_miss_returns_false(self):
        self.assertFalse(details_api.has_cached_art(self.URL))


class CachedManifestVersionTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.manifest_file = Path(self._temp.name) / "manifest.json"

        self._saved = (
            manifest_api._manifest_cache,
            manifest_api._manifest_cache_time,
        )
        manifest_api._manifest_cache = None
        manifest_api._manifest_cache_time = 0
        self.addCleanup(self._restore)
        self._patch = patch.object(
            manifest_api, "MANIFEST_CACHE_FILE", self.manifest_file
        )
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def _restore(self):
        manifest_api._manifest_cache, manifest_api._manifest_cache_time = self._saved

    def test_reads_the_disk_manifest_without_network_io(self):
        self.manifest_file.write_text(
            json.dumps({"hsr": {"latest": "2.0"}}), encoding="utf-8"
        )
        with patch.object(
            manifest_api.requests, "get", side_effect=AssertionError("network")
        ):
            self.assertEqual(manifest_api.cached_latest_version("hsr"), "2.0")

    def test_reads_the_memory_manifest_first(self):
        manifest_api._manifest_cache = {"hsr": {"latest": "3.0"}}

        self.assertEqual(manifest_api.cached_latest_version("hsr"), "3.0")

    def test_missing_manifest_returns_none(self):
        with patch.object(
            manifest_api.requests, "get", side_effect=AssertionError("network")
        ):
            self.assertIsNone(manifest_api.cached_latest_version("hsr"))

    def test_unknown_game_returns_none(self):
        self.manifest_file.write_text(json.dumps({"hsr": {"latest": "2.0"}}))

        self.assertIsNone(manifest_api.cached_latest_version("zzz"))
