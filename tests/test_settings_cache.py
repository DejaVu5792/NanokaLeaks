"""Tests for the settings cache rows, sizes, metadata, and clear confirmation."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMainWindow, QWidget

import nanoka_viewer.ui.settings as settings_ui
from nanoka_viewer.api.preload import (
    PRELOAD_ARTWORK,
    PRELOAD_BUILDS,
    PRELOAD_DETAILS,
    PreloadProgress,
    PreloadSummary,
)
from support import (
    QtTestCase,
    click_qml,
    find_qml_item,
    flush,
    wait,
)


class FakePreloadManager(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.kind = ""
        self.last_progress = None
        self.last_summary = None
        self.last_error = ""
        self.started = []
        self.cancelled = False

    def start(self, kind):
        self.started.append(kind)
        self.running = True
        self.kind = kind
        return True

    def cancel(self):
        self.cancelled = True


class SettingsCacheTabTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.manager = FakePreloadManager()
        self.saved = []
        self.clear_calls = []
        self.cache_sizes_value = {
            "details": 2048,
            "builds": 3072,
            "artwork": 5 * 1024 * 1024,
        }
        self.build_info = {"last_cached": 1700000000.0}

        self.window = QMainWindow()
        self.central = QWidget()
        self.central.setObjectName("centralWidget")
        self.window.setCentralWidget(self.central)
        self.window.resize(900, 700)
        self.window.show()
        self.track_window(self.window)

        self._patches = [
            patch.object(
                settings_ui, "get_preload_manager", return_value=self.manager
            ),
            patch.object(
                settings_ui,
                "load_settings",
                return_value={
                    "cache_character_details": True,
                    "cache_character_builds": True,
                    "cache_character_artwork": True,
                    "sr_centroid_centering": True,
                },
            ),
            patch.object(settings_ui, "save_settings", side_effect=self._save),
            patch.object(
                settings_ui, "cache_sizes", side_effect=lambda: self.cache_sizes_value
            ),
            patch.object(
                settings_ui,
                "read_build_cache_info",
                side_effect=lambda: self.build_info,
            ),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.popup = settings_ui.SettingsPopup(self.central)
        self.addCleanup(self._destroy_popup)
        self.popup.open_popup()
        flush()
        wait(120)

    def _save(self, settings):
        self.saved.append(dict(settings))
        return settings

    def _destroy_popup(self):
        try:
            self.popup.close_popup()
            self.popup.deleteLater()
        except RuntimeError:
            pass
        flush()

    def _clear_api(self):
        self.clear_calls.append("api")
        self.cache_sizes_value = {"details": 0, "builds": 0, "artwork": 0}
        self.build_info = {"last_cached": 0.0}

    @staticmethod
    def _cache_flags(saved):
        """Return just the three cache flags from a saved settings dict."""
        return {
            key: saved[key]
            for key in (
                "cache_character_details",
                "cache_character_builds",
                "cache_character_artwork",
            )
        }

    def _qml(self, name):
        item = find_qml_item(self.popup._qml.rootObject(), name)
        self.assertIsNotNone(item, f"{name} was not created")
        return item

    def test_cache_buttons_are_aligned_right(self):
        for row_name, button_name in (
            ("cacheRow-details", "preloadDetails"),
            ("cacheRow-builds", "preloadBuilds"),
            ("cacheRow-artwork", "preloadArtwork"),
        ):
            row = self._qml(row_name)
            button = self._qml(button_name)
            root = self.popup._qml.rootObject()
            row_right = row.mapToItem(root, row.width(), 0).x()
            button_right = button.mapToItem(root, button.width(), 0).x()
            self.assertAlmostEqual(
                button_right,
                row_right,
                delta=2,
                msg=f"the {button_name} button must sit at the row's right edge",
            )
            self.assertEqual(button.property("text"), "Preload")

    def test_sizes_are_shown_in_kb(self):
        model = self.popup._model
        self.assertEqual(model.detailsSize, "2 kB")
        self.assertEqual(model.buildsSize, "3 kB")
        self.assertEqual(model.artworkSize, "5,120 kB")

        row = self._qml("cacheRow-details")
        size = find_qml_item(row, "cacheSize")
        self.assertEqual(size.property("text"), "2 kB")

    def test_builds_row_shows_last_cached(self):
        text = self.popup._model.buildsLast
        self.assertIn("Last cached:", text)
        self.assertNotIn("never", text)

        row = self._qml("cacheRow-builds")
        last = find_qml_item(row, "cacheLastCached")
        self.assertEqual(last.property("text"), text)

    def test_builds_row_shows_never_without_metadata(self):
        self.build_info = {"last_cached": 0.0}
        self.popup._update_cache_meta()

        self.assertEqual(
            self.popup._model.buildsLast, "Last cached: never"
        )

    def test_checkboxes_are_disabled_while_preloading(self):
        self.manager.running = True
        self.manager.kind = PRELOAD_DETAILS
        self.popup._sync_preload_state()

        self.assertFalse(self.popup._model.cacheEnabled)
        row = self._qml("cacheRow-details")
        box = find_qml_item(row, "cacheCheck")
        self.assertFalse(box.property("enabled"))

    def test_artwork_warning_cancel_does_not_start(self):
        self.popup._confirm_artwork_download = lambda: False

        click_qml(self.popup._qml, self._qml("preloadArtwork"))

        self.assertEqual(self.manager.started, [])
        self.assertFalse(self.manager.cancelled)

    def test_artwork_warning_accept_starts_and_enables_the_setting(self):
        self.popup._model.setCache("artwork", False)
        self.saved.clear()
        self.popup._confirm_artwork_download = lambda: True

        click_qml(self.popup._qml, self._qml("preloadArtwork"))

        model = self.popup._model
        self.assertEqual(self.manager.started, [PRELOAD_ARTWORK])
        self.assertTrue(
            model.cacheArtwork,
            "an explicit Cache click should enable the matching setting",
        )
        self.assertEqual(self.saved[-1]["cache_character_artwork"], True)
        self.assertEqual(model.artworkButtonText, "Cancel")
        self.assertFalse(model.detailsButtonEnabled)
        self.assertFalse(model.buildsButtonEnabled)
        self.assertFalse(model.clearCacheEnabled)

    def test_details_button_starts_the_details_cache_only(self):
        self.popup._model.setCache("details", False)
        self.saved.clear()

        click_qml(self.popup._qml, self._qml("preloadDetails"))

        model = self.popup._model
        self.assertEqual(self.manager.started, [PRELOAD_DETAILS])
        self.assertTrue(model.cacheDetails)
        self.assertEqual(
            self._cache_flags(self.saved[-1]),
            {
                "cache_character_details": True,
                "cache_character_builds": True,
                "cache_character_artwork": True,
            },
        )

    def test_builds_button_starts_the_builds_cache_only(self):
        model = self.popup._model
        model.setCache("details", False)
        model.setCache("builds", False)
        model.setCache("artwork", False)
        self.saved.clear()

        click_qml(self.popup._qml, self._qml("preloadBuilds"))

        self.assertEqual(self.manager.started, [PRELOAD_BUILDS])
        self.assertTrue(model.cacheBuilds)
        self.assertFalse(model.cacheDetails)
        self.assertFalse(model.cacheArtwork)
        self.assertEqual(
            self._cache_flags(self.saved[-1]),
            {
                "cache_character_details": False,
                "cache_character_builds": True,
                "cache_character_artwork": False,
            },
        )

    def test_active_button_cancels_the_running_preload(self):
        self.manager.running = True
        self.manager.kind = PRELOAD_BUILDS
        self.manager.last_progress = PreloadProgress(
            kind=PRELOAD_BUILDS, completed=2, total=10, name="Test"
        )
        self.popup._sync_preload_state()

        model = self.popup._model
        self.assertEqual(model.buildsButtonText, "Cancel")
        self.assertIn("2/10", model.cacheStatus)

        click_qml(self.popup._qml, self._qml("preloadBuilds"))

        self.assertTrue(self.manager.cancelled)
        self.assertEqual(model.buildsButtonText, "Stopping...")

    def test_clear_cache_is_blocked_while_preloading(self):
        self.manager.running = True
        self.manager.kind = PRELOAD_ARTWORK
        self.popup._sync_preload_state()

        with (
            patch.object(settings_ui, "clear_cache") as clear_api,
            patch.object(settings_ui, "clear_image_cache") as clear_images,
        ):
            self.popup._clear_cache()
            clear_api.assert_not_called()
            clear_images.assert_not_called()

        self.assertIn("before clearing", self.popup._model.cacheStatus)

    def test_clear_cache_requires_confirmation(self):
        self.popup._confirm_clear_cache = lambda: False

        with (
            patch.object(settings_ui, "clear_cache") as clear_api,
            patch.object(settings_ui, "clear_image_cache") as clear_images,
        ):
            self.popup._clear_cache()
            clear_api.assert_not_called()
            clear_images.assert_not_called()

    def test_clear_cache_resets_sizes_and_metadata(self):
        self.popup._confirm_clear_cache = lambda: True

        with (
            patch.object(
                settings_ui, "clear_cache", side_effect=self._clear_api
            ) as clear_api,
            patch.object(settings_ui, "clear_image_cache") as clear_images,
        ):
            self.popup._clear_cache()

        model = self.popup._model
        clear_api.assert_called_once()
        clear_images.assert_called_once()
        self.assertEqual(self.clear_calls, ["api"])
        self.assertEqual(model.detailsSize, "0 kB")
        self.assertEqual(model.buildsSize, "0 kB")
        self.assertEqual(model.artworkSize, "0 kB")
        self.assertEqual(model.buildsLast, "Last cached: never")
        self.assertEqual(model.cacheStatus, "Cache cleared.")
        self.assertEqual(model.clearCacheText, "Cleared")
        self.assertFalse(model.clearCacheEnabled)

    def test_clear_cache_button_reports_completion(self):
        self.popup._confirm_clear_cache = lambda: True

        with (
            patch.object(settings_ui, "clear_cache"),
            patch.object(settings_ui, "clear_image_cache"),
        ):
            click_qml(self.popup._qml, self._qml("clearCacheButton"))

        self.assertEqual(self.popup._model.cacheStatus, "Cache cleared.")

    def test_summary_reports_builds_without_builds(self):
        summary = PreloadSummary(
            kind=PRELOAD_BUILDS,
            total=10,
            completed=10,
            failed=1,
            skipped=2,
        )
        self.manager.last_summary = summary

        self.popup._on_preload_finished(summary)

        text = self.popup._model.cacheStatus
        self.assertIn("Preloaded 7 build tables.", text)
        self.assertIn("1 failed", text)
        self.assertIn("2 without build tables", text)

    def test_summary_reports_unavailable_details(self):
        summary = PreloadSummary(
            kind=PRELOAD_DETAILS,
            total=10,
            completed=10,
            failed=1,
            skipped=2,
        )
        self.manager.last_summary = summary

        self.popup._on_preload_finished(summary)

        text = self.popup._model.cacheStatus
        self.assertIn("Preloaded 7 detail pages.", text)
        self.assertIn("2 unavailable", text)


if __name__ == "__main__":
    unittest.main()
