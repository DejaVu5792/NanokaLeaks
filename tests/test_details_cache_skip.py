"""Tests for cache-aware loading placeholders in the details popup.

When the detail, build, or artwork caches are warm the popup must render the
content without flashing a skeleton.  A short fallback timer keeps a slow or
stale cache read from leaving the panel blank: after
``LOADING_FALLBACK_MS`` the normal loading placeholder appears.
"""

from __future__ import annotations

import time
import unittest

from PySide6.QtWidgets import QFrame, QLabel, QWidget
from support import SAMPLE_DETAIL, QtTestCase, flush, wait

import nanoka_viewer.ui.details as details_ui
from nanoka_viewer.api.details import BuildContext, BuildSection, CharacterDetail

ART_URL = "https://example.test/art.webp"


def make_detail(
    *,
    build_context: BuildContext | None = None,
    art_url: str = "",
) -> CharacterDetail:
    return CharacterDetail(
        game="hsr",
        char_id="1",
        name="Test Character",
        subtitle="",
        overview="A cached character.",
        level_label="Lv. 1",
        art_url=art_url,
        build_context=build_context,
    )


class CacheAwareLoadingTests(QtTestCase):
    def _make_popup(self):
        host = QWidget()
        host.resize(900, 700)
        host.show()
        self.addCleanup(host.deleteLater)
        popup = details_ui.CharacterDetailsPopup(host)
        self.addCleanup(popup.deleteLater)
        flush()
        return popup

    def _wait_for(self, predicate, message="condition was not met", timeout=4000):
        elapsed = 0
        while not predicate():
            if elapsed >= timeout:
                self.fail(message)
            wait(20)
            elapsed += 20

    def _wait_for_detail(self, popup):
        self._wait_for(
            lambda: popup._thread is None and popup._art_label is not None,
            "detail load did not finish",
        )

    def _wait_for_build(self, popup):
        self._wait_for(
            lambda: popup._build_thread is None and popup._build_insert_index is None,
            "build load did not finish",
        )

    def _wait_for_art(self, popup):
        self._wait_for(
            lambda: popup._art_thread is None,
            "art load did not finish",
        )

    def _record_loading(self, popup):
        calls = []
        popup._show_loading = lambda: calls.append(1)
        return calls

    def _record_build_skeletons(self, popup):
        calls = []
        original = popup._build_build_skeleton

        def record():
            calls.append(1)
            return original()

        popup._build_build_skeleton = record
        return calls

    def _build_labels(self, popup):
        return [label.text() for label in popup.content.findChildren(QLabel)]

    def _skeleton_cards(self, popup):
        return [
            frame
            for frame in popup.findChildren(QFrame)
            if frame.objectName() == "detailSkeletonCard"
        ]

    # -- detail cache ------------------------------------------------------

    def test_cached_detail_skips_the_loading_screen(self):
        details_ui.has_cached_detail = lambda game, char_id: True
        popup = self._make_popup()
        loading = self._record_loading(popup)

        popup.open_character("hsr", "1")
        self.assertEqual(loading, [], "a cached detail must not show the skeleton")

        self._wait_for_detail(popup)
        self.assertIn(
            "A test character used by the rendering regression tests.",
            self._build_labels(popup),
        )
        self.assertEqual(self._skeleton_cards(popup), [])

    def test_uncached_detail_shows_the_loading_screen_immediately(self):
        details_ui.has_cached_detail = lambda game, char_id: False
        popup = self._make_popup()
        loading = self._record_loading(popup)

        popup.open_character("hsr", "1")
        self.assertEqual(loading, [1], "a cold detail must show the skeleton at once")

        self._wait_for_detail(popup)

    def test_slow_cached_detail_falls_back_to_the_skeleton(self):
        details_ui.has_cached_detail = lambda game, char_id: True

        def slow_loader(game, char_id):
            time.sleep(0.5)
            return SAMPLE_DETAIL

        details_ui.load_character_detail = slow_loader
        popup = self._make_popup()
        loading = self._record_loading(popup)

        popup.open_character("hsr", "1")
        self.assertEqual(loading, [], "the skeleton must wait for the fallback delay")

        wait(details_ui.LOADING_FALLBACK_MS + 100)
        self.assertEqual(
            loading,
            [1],
            "a slow cache read must fall back to the skeleton",
        )

        self._wait_for_detail(popup)
        self.assertEqual(self._skeleton_cards(popup), [])
        self.assertIn("A test character", " ".join(self._build_labels(popup)))

    # -- build cache -------------------------------------------------------

    def test_cached_build_skips_the_build_skeleton(self):
        context = BuildContext("hsr", "1.0", {"relics": [{"id": "1"}]})
        details_ui.has_cached_detail = lambda game, char_id: True
        details_ui.has_cached_build = lambda detail: True
        details_ui.load_character_detail = lambda game, char_id: make_detail(
            build_context=context
        )
        details_ui.load_character_build = lambda detail: [
            BuildSection("Relic", ["Test Relic"])
        ]
        popup = self._make_popup()
        skeletons = self._record_build_skeletons(popup)

        popup.open_character("hsr", "1")
        self._wait_for_detail(popup)
        self._wait_for_build(popup)

        self.assertEqual(
            skeletons,
            [],
            "a cached build must not insert the build skeleton",
        )
        self.assertIn("Recommended Build", self._build_labels(popup))

    def test_uncached_build_shows_the_build_skeleton(self):
        context = BuildContext("hsr", "1.0", {"relics": [{"id": "1"}]})
        details_ui.has_cached_detail = lambda game, char_id: True
        details_ui.has_cached_build = lambda detail: False
        details_ui.load_character_detail = lambda game, char_id: make_detail(
            build_context=context
        )
        details_ui.load_character_build = lambda detail: []
        popup = self._make_popup()
        skeletons = self._record_build_skeletons(popup)

        popup.open_character("hsr", "1")
        self._wait_for_detail(popup)

        self.assertEqual(len(skeletons), 1, "the build skeleton must be shown")
        self._wait_for_build(popup)

    def test_slow_cached_build_falls_back_to_the_build_skeleton(self):
        context = BuildContext("hsr", "1.0", {"relics": [{"id": "1"}]})
        details_ui.has_cached_detail = lambda game, char_id: True
        details_ui.has_cached_build = lambda detail: True
        details_ui.load_character_detail = lambda game, char_id: make_detail(
            build_context=context
        )

        def slow_build(detail):
            time.sleep(0.5)
            return [BuildSection("Relic", ["Test Relic"])]

        details_ui.load_character_build = slow_build
        popup = self._make_popup()
        skeletons = self._record_build_skeletons(popup)

        popup.open_character("hsr", "1")
        self._wait_for_detail(popup)
        self.assertEqual(
            skeletons,
            [],
            "the build skeleton must wait for the fallback delay",
        )

        wait(details_ui.LOADING_FALLBACK_MS + 100)
        self.assertEqual(
            len(skeletons),
            1,
            "a slow cached build must fall back to the skeleton",
        )

        self._wait_for_build(popup)
        self.assertEqual(self._skeleton_cards(popup), [])
        self.assertIn("Recommended Build", self._build_labels(popup))

    # -- artwork cache -----------------------------------------------------

    def _record_art_skeletons(self, popup):
        shown = []
        original = popup._build_art_panel

        def record(detail):
            widget = original(detail)
            skeleton = popup._art_skeleton
            shown.append(bool(skeleton is not None and not skeleton.isHidden()))
            return widget

        popup._build_art_panel = record
        return shown

    def test_cached_art_skips_the_loading_placeholder(self):
        details_ui.has_cached_detail = lambda game, char_id: True
        details_ui.has_cached_art = lambda url: True
        details_ui.load_character_detail = lambda game, char_id: make_detail(
            art_url=ART_URL
        )
        popup = self._make_popup()
        shown = self._record_art_skeletons(popup)

        popup.open_character("hsr", "1")
        self._wait_for_detail(popup)

        self.assertEqual(
            shown[:1], [False], "cached art must not flash the art skeleton"
        )
        self._wait_for_art(popup)

    def test_uncached_art_shows_the_loading_placeholder(self):
        details_ui.has_cached_detail = lambda game, char_id: True
        details_ui.has_cached_art = lambda url: False
        details_ui.load_character_detail = lambda game, char_id: make_detail(
            art_url=ART_URL
        )
        popup = self._make_popup()
        shown = self._record_art_skeletons(popup)

        popup.open_character("hsr", "1")
        self._wait_for_detail(popup)

        self.assertEqual(shown[:1], [True])
        self._wait_for_art(popup)

    def test_slow_cached_art_falls_back_to_the_placeholder(self):
        details_ui.has_cached_detail = lambda game, char_id: True
        details_ui.has_cached_art = lambda url: True
        details_ui.load_character_detail = lambda game, char_id: make_detail(
            art_url=ART_URL
        )

        def slow_art(url):
            time.sleep(0.5)

        details_ui.load_character_art = slow_art
        popup = self._make_popup()
        shown = self._record_art_skeletons(popup)

        popup.open_character("hsr", "1")
        self._wait_for_detail(popup)
        self.assertEqual(shown[:1], [False])

        wait(details_ui.LOADING_FALLBACK_MS + 100)
        self.assertIsNotNone(popup._art_skeleton)
        self.assertFalse(
            popup._art_skeleton.isHidden(),
            "a slow cached artwork read must fall back to the art skeleton",
        )
        self._wait_for_art(popup)


if __name__ == "__main__":
    unittest.main()
