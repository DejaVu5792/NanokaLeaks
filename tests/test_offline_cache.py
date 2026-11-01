"""Offline behaviour of the character/detail caches.

The app is expected to keep working from its on-disk cache when the network is
unavailable.  The dangerous case is a *stale* cache: the manifest has a 24 hour
freshness window, so after a day offline the old code tried the network, failed,
and reported "Failed to load characters" even though every character file was
still sitting in the cache directory.

These tests drive the API layer with the network mocked out and assert that
data is still served from disk.  They deliberately do not mock the loaders
themselves: the files are real files written to a temporary cache directory.
"""

from __future__ import annotations

import json
import os
import pickle
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import nanoka_viewer.api.characters as characters_api
import nanoka_viewer.api.details as details_api
import nanoka_viewer.api.manifest as manifest_api
from nanoka_viewer.api.details import CharacterDetail
from nanoka_viewer.api.manifest import (
    DISK_CACHE_TIMEOUT,
    fetch_manifest,
    get_latest_version,
)

OFFLINE = requests.ConnectionError("network is unreachable")


def offline_manifest(*args, **kwargs):
    raise OFFLINE


class OfflineCacheTestCase(unittest.TestCase):
    """Shared temporary cache and network stubs for the offline scenarios."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        root = Path(self._temp.name)
        self.manifest_file = root / "manifest.json"
        self.character_dir = root / "characters"
        self.detail_dir = root / "details"
        self.metadata_dir = root / "details_metadata"
        self.art_dir = root / "details_art"
        for directory in (
            self.character_dir,
            self.detail_dir,
            self.metadata_dir,
            self.art_dir,
        ):
            directory.mkdir()

        self._saved_manifest = (
            manifest_api._manifest_cache,
            manifest_api._manifest_cache_time,
        )
        manifest_api._manifest_cache = None
        manifest_api._manifest_cache_time = 0
        self.addCleanup(self._restore_manifest)

        self._saved_character_cache = characters_api._character_cache
        characters_api._character_cache = {}
        self.addCleanup(self._restore_character_cache)

        self._saved_detail_caches = (
            details_api._detail_cache,
            details_api._metadata_cache,
            details_api._art_cache,
        )
        details_api._detail_cache = {}
        details_api._metadata_cache = {}
        details_api._art_cache = {}
        self.addCleanup(self._restore_detail_caches)

        self._patches = [
            patch.object(manifest_api, "MANIFEST_CACHE_FILE", self.manifest_file),
            patch.object(characters_api, "CHARACTER_CACHE_DIR", self.character_dir),
            patch.object(details_api, "DETAIL_CACHE_DIR", self.detail_dir),
            patch.object(details_api, "METADATA_CACHE_DIR", self.metadata_dir),
            patch.object(details_api, "DETAIL_ART_CACHE_DIR", self.art_dir),
            patch.object(details_api, "get_setting", return_value=True),
            # Keep the retry path but skip the exponential backoff sleeps.
            patch.object(details_api, "_retry_delay", return_value=0.0),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        # ``fetch_characters`` and ``details`` import the manifest helpers by
        # name, but those functions still read the (patched) manifest module
        # globals, so no re-patching is needed there.
        self.offline = patch.object(manifest_api.requests, "get", offline_manifest)
        self.offline.start()
        self.addCleanup(self.offline.stop)

        # ``details`` uses a shared requests.Session rather than requests.get.
        self.offline_session = patch.object(
            details_api._session, "get", side_effect=OFFLINE
        )
        self.offline_session.start()
        self.addCleanup(self.offline_session.stop)

    def _restore_manifest(self):
        (
            manifest_api._manifest_cache,
            manifest_api._manifest_cache_time,
        ) = self._saved_manifest

    def _restore_character_cache(self):
        characters_api._character_cache = self._saved_character_cache

    def _restore_detail_caches(self):
        (
            details_api._detail_cache,
            details_api._metadata_cache,
            details_api._art_cache,
        ) = self._saved_detail_caches

    # -- fixtures ---------------------------------------------------------

    def write_manifest(self, *, latest="4.0", age=0.0, games=None):
        games = games or {
            "hsr": {"latest": latest, "live": latest},
            "gi": {"latest": latest, "live": latest},
        }
        self.manifest_file.write_text(json.dumps(games), encoding="utf-8")
        if age:
            stamp = time.time() - age
            os.utime(self.manifest_file, (stamp, stamp))
        return games

    def write_characters(self, version, data=None, *, game="hsr"):
        data = data if data is not None else {"1001": {"en": "Cached"}}
        path = self.character_dir / f"{game}_{version}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return data

    def write_detail(self, version, *, game="hsr", char_id="1001", name="Cached"):
        detail = CharacterDetail(
            game=game,
            char_id=char_id,
            name=name,
            subtitle="",
            overview="cached overview",
            level_label="Lv. 80",
        )
        path = details_api._detail_disk_path((game, version, str(char_id)))
        path.write_bytes(pickle.dumps(detail))
        return detail


class OfflineManifestTests(OfflineCacheTestCase):
    def test_stale_manifest_is_served_when_offline(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)

        manifest = fetch_manifest()

        self.assertEqual(manifest["hsr"]["latest"], "4.0")
        self.assertEqual(get_latest_version("hsr"), "4.0")

    def test_fresh_manifest_is_served_from_disk(self):
        self.write_manifest(latest="4.1")

        self.assertEqual(fetch_manifest()["hsr"]["latest"], "4.1")

    def test_offline_without_any_cache_raises(self):
        with self.assertRaises(requests.ConnectionError):
            fetch_manifest()

    def test_offline_with_a_corrupt_cache_raises(self):
        self.manifest_file.write_text("{not json", encoding="utf-8")
        stamp = time.time() - DISK_CACHE_TIMEOUT - 60
        os.utime(self.manifest_file, (stamp, stamp))

        with self.assertRaises((requests.ConnectionError, ValueError)):
            fetch_manifest()

    def test_stale_manifest_is_reused_for_the_memory_cache_window(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)

        first = fetch_manifest()
        # The fallback must not leave the cache empty, otherwise every game
        # load would hit the 30 second network timeout again.
        self.assertIs(fetch_manifest(), first)


class OfflineCharacterTests(OfflineCacheTestCase):
    def test_cached_characters_load_offline_with_a_stale_manifest(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        cached = self.write_characters("4.0")

        self.assertEqual(characters_api.fetch_characters("hsr"), cached)

    def test_newest_cached_version_loads_when_the_manifest_is_newer(self):
        # The manifest was refreshed to 4.0 but the character file for 4.0 was
        # never downloaded before the connection dropped.
        self.write_manifest(latest="4.0")
        older = self.write_characters("3.9", {"2002": {"en": "Older"}})

        self.assertEqual(characters_api.fetch_characters("hsr"), older)

    def test_cached_characters_load_offline_when_the_manifest_is_missing(self):
        self.write_characters("4.0")

        self.assertEqual(
            characters_api.fetch_characters("hsr")["1001"],
            {"en": "Cached"},
        )

    def test_offline_without_cached_characters_raises(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)

        with self.assertRaises(requests.RequestException):
            characters_api.fetch_characters("hsr")

    def test_requested_game_does_not_borrow_another_games_cache(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        self.write_characters("4.0", game="hsr")

        with self.assertRaises(requests.RequestException):
            characters_api.fetch_characters("gi")

    def test_offline_character_count_uses_the_cache(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        self.write_characters("4.0", {"1": {}, "2": {}, "3": {}})

        self.assertEqual(characters_api.cached_character_count("hsr"), 3)


class OfflineDetailTests(OfflineCacheTestCase):
    def test_cached_detail_loads_offline_with_a_stale_manifest(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        cached = self.write_detail("4.0")

        detail = details_api.load_character_detail("hsr", "1001")

        self.assertEqual(detail.name, cached.name)
        self.assertEqual(detail.overview, "cached overview")

    def test_cached_detail_is_not_discarded_when_offline(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        cached = self.write_detail("4.0")
        path = details_api._detail_disk_path(("hsr", "4.0", "1001"))

        details_api.load_character_detail("hsr", "1001")

        self.assertTrue(path.exists(), "a cached entry must survive an offline read")
        self.assertEqual(pickle.loads(path.read_bytes()).name, cached.name)

    def test_cached_detail_from_the_previous_version_loads_offline(self):
        # The manifest moved on to 4.0 but only 3.9 was ever downloaded.
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        self.write_characters("3.9")
        self.write_detail("3.9", name="Previous version")

        detail = details_api.load_character_detail("hsr", "1001")

        self.assertEqual(detail.name, "Previous version")
        self.assertTrue(detail.build_context is None)

    def test_cached_detail_loads_offline_when_the_manifest_is_missing(self):
        self.write_characters("4.0")
        self.write_detail("4.0", name="No manifest")

        detail = details_api.load_character_detail("hsr", "1001")

        self.assertEqual(detail.name, "No manifest")

    def test_previous_version_fallback_does_not_cross_games(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        self.write_characters("3.9", game="hsr")
        self.write_detail("3.9", game="hsr", char_id="1001")

        with self.assertRaises(details_api.DetailUnavailable):
            details_api.load_character_detail("gi", "1001")

    def test_previous_version_fallback_respects_the_cache_setting(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        self.write_characters("3.9")
        self.write_detail("3.9", name="Previous version")

        with patch.object(details_api, "get_setting", return_value=False):
            with self.assertRaises(details_api.DetailUnavailable):
                details_api.load_character_detail("hsr", "1001")

    def test_detail_without_cache_reports_a_connection_problem(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)

        with self.assertRaises(details_api.DetailUnavailable) as caught:
            details_api.load_character_detail("hsr", "1001")

        self.assertIn("connection", str(caught.exception).lower())

    def test_cached_artwork_loads_offline(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        url = "https://example.test/art.webp"
        details_api._art_disk_path(url).write_bytes(b"artwork")

        self.assertEqual(details_api.load_character_art(url), b"artwork")

    def test_cached_build_metadata_loads_offline(self):
        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        cache_key = ("hsr", "4.0", "relicset")
        data = {"1": {"name": "Cached set"}}
        details_api._metadata_disk_path(cache_key).write_bytes(pickle.dumps(data))

        loaded = details_api._fetch_metadata_file(
            "hsr", "4.0", "relicset", "https://example.test/relicset.json"
        )

        self.assertEqual(loaded, data)


class OfflineLoadThreadTests(OfflineCacheTestCase):
    def test_load_thread_emits_cached_characters_offline(self):
        from support import app, flush

        app()
        from nanoka_viewer.ui.loader import LoadThread

        self.write_manifest(latest="4.0", age=DISK_CACHE_TIMEOUT + 3600)
        self.write_characters(
            "4.0",
            {
                "1001": {"en": "Cached", "release": "2024-01-01 00:00:00"},
            },
        )

        events = []
        thread = LoadThread(games=["hsr"])
        thread.game_loaded.connect(lambda game, chars: events.append((game, chars)))
        thread.load_finished.connect(lambda: events.append("finished"))

        thread.run()
        # game_loaded is emitted from the worker pool, so the delivery is
        # queued to this thread's event loop.
        flush()

        self.assertIn(
            (
                "hsr",
                [
                    (
                        "1001",
                        {"en": "Cached", "release": "2024-01-01 00:00:00"},
                        False,
                    )
                ],
            ),
            events,
            "cached characters must still reach the window while offline",
        )
        self.assertIn("finished", events)
