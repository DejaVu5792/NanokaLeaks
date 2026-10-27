"""Tests for bulk cache preloading and the preload-aware detail cache."""

from __future__ import annotations

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
        build_calls = []
        progress = []

        def fake_detail(game, char_id, *, remember=True):
            detail_calls.append((game, char_id, remember))
            return details_by_key[(game, char_id)]

        def fake_build(detail):
            build_calls.append(detail.name)
            return []

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
            patch.object(preload, "load_character_build", side_effect=fake_build),
        ):
            summary = preload_characters(PRELOAD_DETAILS, progress.append)

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.completed, 3)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.skipped, 0)
        self.assertEqual(
            detail_calls,
            [("hsr", "1", False), ("hsr", "2", False), ("ww", "3", False)],
            "preloading must not pin every raw detail in the session cache",
        )
        self.assertEqual(
            build_calls,
            [],
            "the details preload must not pull build metadata",
        )
        self.assertEqual(progress[0].completed, 0)
        self.assertEqual(progress[0].total, 3)
        self.assertEqual(progress[-1].completed, 3)
        self.assertEqual(progress[-1].name, "Gamma")

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

    def test_cancellation_stops_between_characters(self):
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
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.total, 2)
        self.assertEqual(detail_calls, ["1"])

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


class PreloadBuildsTests(unittest.TestCase):
    def test_caches_only_characters_with_build_data(self):
        details_by_id = {
            "1": make_detail("hsr", "1", "Alpha", build=True),
            "2": make_detail("hsr", "2", "Beta"),
            "3": make_detail("hsr", "3", "Gamma", build=True),
        }
        build_calls = []
        snapshots = []

        def fake_build(detail):
            build_calls.append(detail.name)
            return []

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
            patch.object(preload, "load_character_build", side_effect=fake_build),
            patch.object(
                preload,
                "record_build_cache_snapshot",
                side_effect=lambda: snapshots.append(True),
            ),
        ):
            summary = preload_characters(PRELOAD_BUILDS)

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.completed, 3)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(build_calls, ["Alpha", "Gamma"])
        self.assertEqual(snapshots, [True], "the live version snapshot is recorded")

    def test_snapshot_is_not_recorded_when_nothing_completed(self):
        def fake_detail(game, char_id, *, remember=True):
            raise DetailUnavailable("not ready")

        snapshots = []
        with (
            patch.object(preload, "GAMES", {"hsr": {}}),
            patch.object(preload, "fetch_characters", return_value={"1": {}}),
            patch.object(preload, "load_character_detail", side_effect=fake_detail),
            patch.object(
                preload,
                "record_build_cache_snapshot",
                side_effect=lambda: snapshots.append(True),
            ),
        ):
            summary = preload_characters(PRELOAD_BUILDS)

        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(snapshots, [])

    def test_cancelled_run_does_not_claim_every_game_was_cached(self):
        snapshots = []
        checks = {"count": 0}

        def should_stop():
            checks["count"] += 1
            return checks["count"] > 1

        with (
            patch.object(preload, "GAMES", {"hsr": {}}),
            patch.object(
                preload, "fetch_characters", return_value={"1": {}, "2": {}}
            ),
            patch.object(
                preload,
                "load_character_detail",
                side_effect=lambda game, char_id, *, remember=True: make_detail(
                    game, char_id, build=True
                ),
            ),
            patch.object(preload, "load_character_build", return_value=[]),
            patch.object(
                preload,
                "record_build_cache_snapshot",
                side_effect=lambda: snapshots.append(True),
            ),
        ):
            summary = preload_characters(
                PRELOAD_BUILDS, should_stop=should_stop
            )

        self.assertTrue(summary.cancelled)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(snapshots, [])

    def test_build_failure_is_reported(self):
        def fake_build(detail):
            raise RuntimeError("metadata missing")

        with (
            patch.object(preload, "GAMES", {"hsr": {}}),
            patch.object(preload, "fetch_characters", return_value={"1": {}}),
            patch.object(
                preload,
                "load_character_detail",
                side_effect=lambda game, char_id, *, remember=True: make_detail(
                    game, char_id, build=True
                ),
            ),
            patch.object(preload, "load_character_build", side_effect=fake_build),
            patch.object(preload, "record_build_cache_snapshot"),
            patch.object(preload.logger, "exception"),
        ):
            summary = preload_characters(PRELOAD_BUILDS)

        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.skipped, 0)


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
        self.assertEqual(
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
