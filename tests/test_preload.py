"""Tests for bulk cache preloading and the preload-aware detail cache."""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

from nanoka_viewer.api import preload
from nanoka_viewer.api.details import BuildContext, CharacterDetail, DetailUnavailable
from nanoka_viewer.api.preload import (
    PRELOAD_ARTWORK,
    PRELOAD_BUILDS,
    PRELOAD_DETAILS,
    preload_characters,
)


def make_detail(
    game: str = "hsr",
    char_id: str = "1",
    name: str = "Test",
    *,
    build: bool = False,
    art_url: str = "",
) -> CharacterDetail:
    detail = CharacterDetail(
        game=game,
        char_id=char_id,
        name=name,
        subtitle="",
        overview="",
        level_label="Lv. 80",
    )
    if build:
        detail.build_context = BuildContext(game, "1.0", {"relics": {"set4_id_list": [1]}})
    detail.art_url = art_url
    return detail


class PreloadDetailsTests(unittest.TestCase):
    def test_caches_details_without_touching_builds(self):
        details_by_key = {
            ("hsr", "1"): make_detail("hsr", "1", "Alpha", build=True),
            ("hsr", "2"): make_detail("hsr", "2", "Beta"),
            ("ww", "3"): make_detail("ww", "3", "Gamma", build=True),
        }
        detail_calls = []
        progress = []

        def fake_detail(game, char_id, *, remember=True):
            detail_calls.append((game, char_id, remember))
            return details_by_key[(game, char_id)]

        with (
            patch.object(preload, "GAMES", {"hsr": {}, "ww": {}}),
            patch.object(
                preload,
                "fetch_characters",
                side_effect=lambda game: {"1": {}, "2": {}}
                if game == "hsr"
                else {"3": {}},
            ),
            patch.object(preload, "load_character_detail", side_effect=fake_detail),
        ):
            summary = preload_characters(PRELOAD_DETAILS, progress.append)

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.completed, 3)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.skipped, 0)
        self.assertCountEqual(
            detail_calls,
            [("hsr", "1", False), ("hsr", "2", False), ("ww", "3", False)],
            "preloading must not pin every raw detail in the session cache",
        )
        self.assertEqual(progress[0].completed, 0)
        self.assertEqual(progress[0].total, 3)
        self.assertEqual(progress[-1].completed, 3)
        self.assertEqual(
            {item.name for item in progress if item.name},
            {"Alpha", "Beta", "Gamma"},
        )

    def test_unavailable_details_are_skipped(self):
        def fake_detail(game, char_id, *, remember=True):
            raise DetailUnavailable("not ready")

        with (
            patch.object(preload, "GAMES", {"hsr": {}}),
            patch.object(preload, "fetch_characters", return_value={"1": {}}),
            patch.object(preload, "load_character_detail", side_effect=fake_detail),
        ):
            summary = preload_characters(PRELOAD_DETAILS)

        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.failed, 0)

    def test_cancellation_is_reported(self):
        detail_calls = []
        stop_after_first = {"value": False}

        def fake_detail(game, char_id, *, remember=True):
            detail_calls.append(char_id)
            stop_after_first["value"] = True
            return make_detail(game, char_id)

        def should_stop():
            return stop_after_first["value"]

        with (
            patch.object(preload, "GAMES", {"hsr": {}}),
            patch.object(preload, "fetch_characters", return_value={"1": {}, "2": {}}),
            patch.object(preload, "load_character_detail", side_effect=fake_detail),
        ):
            summary = preload_characters(PRELOAD_DETAILS, should_stop=should_stop)

        self.assertTrue(summary.cancelled)
        self.assertGreaterEqual(summary.completed, 1)
        self.assertLessEqual(summary.completed, summary.total)
        self.assertGreaterEqual(len(detail_calls), 1)

    def test_partial_game_failure_is_reported(self):
        def fake_fetch(game):
            if game == "ww":
                raise OSError("offline")
            return {"1": {}}

        with (
            patch.object(preload, "GAMES", {"hsr": {}, "ww": {}}),
            patch.object(preload, "fetch_characters", side_effect=fake_fetch),
            patch.object(
                preload,
                "load_character_detail",
                side_effect=lambda game, char_id, *, remember=True: make_detail(
                    game, char_id
                ),
            ),
        ):
            summary = preload_characters(PRELOAD_DETAILS)

        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.failed_games, 1)

    def test_all_games_failing_raises(self):
        with (
            patch.object(preload, "GAMES", {"hsr": {}, "ww": {}}),
            patch.object(
                preload,
                "fetch_characters",
                side_effect=OSError("offline"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                preload_characters(PRELOAD_DETAILS)


class PreloadConcurrencyTests(unittest.TestCase):
    def test_worker_count_is_bounded_and_parallel(self):
        active = 0
        max_active = 0
        lock = threading.Lock()

        def fake_store(game, char_id):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return 0, 0, char_id

        ids = {str(index): {} for index in range(12)}
        with (
            patch.object(preload, "PRELOAD_MAX_WORKERS", 3),
            patch.object(preload, "GAMES", {"hsr": {}}),
            patch.object(preload, "fetch_characters", return_value=ids),
            patch.object(preload, "_store_details", side_effect=fake_store),
        ):
            summary = preload_characters(PRELOAD_DETAILS)

        self.assertEqual(summary.completed, 12)
        self.assertGreater(max_active, 1, "jobs should actually run in parallel")
        self.assertLessEqual(max_active, 3, "the worker limit must be respected")
        self.assertEqual(active, 0)


class PreloadBuildsTests(unittest.TestCase):
    def _run(self, fetched_by_game, *, should_stop=None, version_lookup=None):
        writes = []
        progress = []
        versions = {"hsr": "1.0", "ww": "2.0", "gi": "3.0"}
        version_lookup = version_lookup or (lambda game: versions[game])

        with (
            patch.object(
                preload,
                "GAMES",
                {
                    "hsr": {"name": "HSR"},
                    "ww": {"name": "WW"},
                    "gi": {"name": "GI"},
                },
            ),
            patch.object(
                preload, "get_latest_version", side_effect=version_lookup
            ),
            patch.object(
                preload,
                "prefetch_build_metadata",
                side_effect=lambda game, version: fetched_by_game[game],
            ),
            patch.object(
                preload,
                "record_build_cache_write",
                side_effect=lambda: writes.append(True),
            ),
        ):
            summary = preload_characters(
                PRELOAD_BUILDS,
                progress.append,
                should_stop=should_stop,
            )
        return summary, writes, progress

    def test_preloads_shared_build_tables_per_game(self):
        summary, writes, progress = self._run(
            {
                "hsr": (3, 3),
                "ww": (1, 1),
                "gi": (0, 0),
            }
        )

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.completed, 3)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(writes, [True])
        self.assertEqual(progress[0].total, 3)
        self.assertEqual(
            {item.name for item in progress if item.name},
            {"HSR", "WW", "GI"},
        )

    def test_partial_build_tables_are_failures(self):
        summary, writes, _ = self._run(
            {
                "hsr": (2, 3),
                "ww": (0, 1),
                "gi": (0, 0),
            }
        )

        self.assertEqual(summary.failed, 2)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(
            writes,
            [True],
            "partial tables still update the cache timestamp",
        )
        self.assertEqual(summary.completed - summary.failed - summary.skipped, 0)

    def test_nothing_written_does_not_update_timestamp(self):
        summary, writes, _ = self._run(
            {
                "hsr": (0, 3),
                "ww": (0, 1),
                "gi": (0, 0),
            }
        )

        self.assertEqual(summary.failed, 2)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(writes, [])

    def test_cancelled_run_does_not_update_timestamp(self):
        summary, writes, _ = self._run(
            {"hsr": (3, 3), "ww": (1, 1), "gi": (0, 0)},
            should_stop=lambda: True,
        )

        self.assertTrue(summary.cancelled)
        self.assertEqual(summary.completed, 0)
        self.assertEqual(writes, [])

    def test_version_lookup_failure_is_reported(self):
        def fake_version(game):
            if game == "ww":
                raise OSError("offline")
            return {"hsr": "1.0", "gi": "3.0"}[game]

        summary, writes, _ = self._run(
            {"hsr": (3, 3), "ww": (1, 1), "gi": (0, 0)},
            version_lookup=fake_version,
        )

        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(writes, [True])


class PreloadArtworkTests(unittest.TestCase):
    def test_uses_detail_art_url_and_counts_failures(self):
        details_by_id = {
            "1": make_detail("hsr", "1", "Alpha", art_url="https://example/1.webp"),
            "2": make_detail("hsr", "2", "Beta", art_url=""),
            "3": make_detail("hsr", "3", "Gamma", art_url="https://example/3.webp"),
        }
        art_calls = []

        def fake_art(url, *, remember=True):
            art_calls.append((url, remember))
            return b"image" if url.endswith("1.webp") else None

        with (
            patch.object(preload, "GAMES", {"hsr": {}}),
            patch.object(
                preload, "fetch_characters", return_value={"1": {}, "2": {}, "3": {}}
            ),
            patch.object(
                preload,
                "load_character_detail",
                side_effect=lambda game, char_id, *, remember=True: details_by_id[char_id],
            ),
            patch.object(preload, "load_character_art", side_effect=fake_art),
        ):
            summary = preload_characters(PRELOAD_ARTWORK)

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.completed, 3)
        self.assertEqual(summary.skipped, 1, "characters without art are skipped")
        self.assertEqual(summary.failed, 1, "a failed download is reported")
        self.assertCountEqual(
            art_calls,
            [
                ("https://example/1.webp", False),
                ("https://example/3.webp", False),
            ],
        )

    def test_invalid_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            preload_characters("unknown")


if __name__ == "__main__":
    unittest.main()
