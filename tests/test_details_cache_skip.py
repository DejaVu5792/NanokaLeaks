"""Tests for cache-aware loading placeholders in the details popup.

When the detail, build, or artwork caches are warm the popup must render the
content without flashing a skeleton.  A short fallback timer keeps a slow or
stale cache read from leaving the panel blank: after
``LOADING_FALLBACK_MS`` the normal loading placeholder appears.

The popup renders through QML now, so the assertions are on the
``DetailsViewModel`` states (which drive the QML tree) instead of widget
internals.
"""

from __future__ import annotations

import time
import unittest

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QWidget

from support import SAMPLE_DETAIL, QtTestCase, flush, wait, wait_for

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


def png_bytes() -> bytes:
    """A tiny valid PNG, as ``load_character_art`` returns raw bytes."""
    image = QImage(40, 80, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ff0000"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


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

    def _wait_for_detail(self, popup):
        wait_for(
            lambda: popup._thread is None and popup._model.state == "ready",
            timeout=4000,
            message="detail load did not finish",
        )
        flush()

    def _wait_for_build(self, popup):
        wait_for(
            lambda: popup._build_thread is None,
            timeout=4000,
            message="build load did not finish",
        )
        flush()

    def _wait_for_art(self, popup):
        wait_for(
            lambda: popup._art_thread is None,
            timeout=4000,
            message="art load did not finish",
        )
        flush()

    def _record_loading(self, popup):
        calls = []
        original = popup._show_loading

        def record():
            calls.append(1)
            original()

        popup._show_loading = record
        return calls

    def _record_build_skeletons(self, popup):
        calls = []
        original = popup._model.show_build_skeleton

        def record():
            calls.append(1)
            original()

        popup._model.show_build_skeleton = record
        return calls

    def _record_art_skeletons(self, popup):
        calls = []
        original = popup._model.show_art_skeleton

        def record():
            calls.append(1)
            original()

        popup._model.show_art_skeleton = record
        return calls

    # -- detail cache ------------------------------------------------------

    def test_cached_detail_skips_the_loading_screen(self):
        details_ui.has_cached_detail = lambda game, char_id: True
        popup = self._make_popup()
        loading = self._record_loading(popup)

        popup.open_character("hsr", "1")
        self.assertEqual(
            loading, [], "a cached detail must not show the skeleton"
        )
        self.assertEqual(popup._model.state, "idle")

        self._wait_for_detail(popup)
        self.assertEqual(popup._model.name, "Test Character")
        self.assertEqual(popup._model.overview, SAMPLE_DETAIL.overview)

    def test_uncached_detail_shows_the_loading_screen_immediately(self):
        details_ui.has_cached_detail = lambda game, char_id: False
        popup = self._make_popup()
        loading = self._record_loading(popup)

        popup.open_character("hsr", "1")
        self.assertEqual(
            loading, [1], "a cold detail must show the skeleton at once"
        )
        self.assertEqual(popup._model.state, "loading")

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
        self.assertEqual(
            loading, [], "the skeleton must wait for the fallback delay"
        )

        wait(details_ui.LOADING_FALLBACK_MS + 100)
        self.assertEqual(
            loading,
            [1],
            "a slow cache read must fall back to the skeleton",
        )
        self.assertEqual(popup._model.state, "loading")

        self._wait_for_detail(popup)
        self.assertEqual(popup._model.state, "ready")
        self.assertEqual(popup._model.name, SAMPLE_DETAIL.name)

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

        self.assertEqual(
            skeletons,
            [],
            "a cached build must not insert the build skeleton",
        )

        self._wait_for_build(popup)
        self.assertEqual(popup._model.buildState, "ready")
        self.assertEqual(popup._model.buildRows[0][0]["title"], "Relic")
        self.assertEqual(popup._model.buildRows[0][0]["items"], ["Test Relic"])

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
        self.assertEqual(
            popup._model.buildState,
            "hidden",
            "an empty build must remove the card entirely",
        )

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
        self.assertEqual(popup._model.buildState, "hidden")

        wait(details_ui.LOADING_FALLBACK_MS + 100)
        self.assertEqual(
            len(skeletons),
            1,
            "a slow cached build must fall back to the skeleton",
        )
        self.assertEqual(popup._model.buildState, "skeleton")

        self._wait_for_build(popup)
        self.assertEqual(popup._model.buildState, "ready")
        self.assertEqual(popup._model.buildRows[0][0]["title"], "Relic")

    # -- artwork cache -----------------------------------------------------

    def test_cached_art_skips_the_loading_placeholder(self):
        details_ui.has_cached_detail = lambda game, char_id: True
        details_ui.has_cached_art = lambda url: True
        details_ui.load_character_detail = lambda game, char_id: make_detail(
            art_url=ART_URL
        )
        details_ui.load_character_art = lambda url: png_bytes()
        popup = self._make_popup()
        skeletons = self._record_art_skeletons(popup)

        popup.open_character("hsr", "1")
        self._wait_for_detail(popup)

        self.assertEqual(
            skeletons, [], "cached art must not flash the art skeleton"
        )

        self._wait_for_art(popup)
        self.assertEqual(popup._model.artState, "ready")
        self.assertTrue(popup._model.artSource.startswith("image://nanokaart/"))

    def test_uncached_art_shows_the_loading_placeholder(self):
        details_ui.has_cached_detail = lambda game, char_id: True
        details_ui.has_cached_art = lambda url: False
        details_ui.load_character_detail = lambda game, char_id: make_detail(
            art_url=ART_URL
        )
        popup = self._make_popup()
        skeletons = self._record_art_skeletons(popup)

        popup.open_character("hsr", "1")
        self._wait_for_detail(popup)

        self.assertEqual(skeletons, [1])

        self._wait_for_art(popup)
        self.assertEqual(
            popup._model.artState,
            "unavailable",
            "the stub loader returns no bytes, so the column explains itself",
        )

    def test_slow_cached_art_falls_back_to_the_placeholder(self):
        details_ui.has_cached_detail = lambda game, char_id: True
        details_ui.has_cached_art = lambda url: True
        details_ui.load_character_detail = lambda game, char_id: make_detail(
            art_url=ART_URL
        )

        def slow_art(url):
            time.sleep(0.5)
            return png_bytes()

        details_ui.load_character_art = slow_art
        popup = self._make_popup()
        skeletons = self._record_art_skeletons(popup)

        popup.open_character("hsr", "1")
        self._wait_for_detail(popup)
        self.assertEqual(skeletons, [])
        self.assertEqual(popup._model.artState, "hidden")

        wait(details_ui.LOADING_FALLBACK_MS + 100)
        self.assertEqual(
            skeletons,
            [1],
            "a slow cached artwork read must fall back to the art skeleton",
        )
        self.assertEqual(popup._model.artState, "skeleton")

        self._wait_for_art(popup)
        self.assertEqual(popup._model.artState, "ready")


if __name__ == "__main__":
    unittest.main()
