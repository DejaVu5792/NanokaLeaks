"""Tests for the settings cache rows, sizes, metadata, and clear confirmation."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMainWindow, QWidget

import nanoka_viewer.ui.settings as settings_ui
from nanoka_viewer.api import GAMES
from nanoka_viewer.api.preload import (
    PRELOAD_ARTWORK,
    PRELOAD_BUILDS,
    PRELOAD_DETAILS,
    PreloadProgress,
    PreloadSummary,
)
from support import QtTestCase, flush


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


class SettingsCacheTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.manager = FakePreloadManager()
        self.saved = []
        self.cache_sizes_value = {
            "details": 2048,
            "builds": 3072,
            "artwork": 5 * 1024 * 1024,
        }
        self.build_info = {
            "last_cached": 1_700_000_000.0,
            "games": {
                "hsr": {
                    "live": "3.8",
                    "latest": "3.9",
                    "cached_at": 1_700_000_000.0,
                },
                "ww": {
                    "live": "2.6",
                    "latest": "2.7",
                    "cached_at": 1_700_000_000.0,
                },
            },
        }
        self.clear_calls = []

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
            patch.object(
                settings_ui,
                "get_cached_manifest",
                return_value={
                    "hsr": {"live": "3.9", "latest": "3.9"},
                    "ww": {"live": "2.6", "latest": "2.7"},
                },
            ),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.popup = settings_ui.SettingsPopup(self.central)
        self.addCleanup(self._destroy_popup)
        self.popup.open_popup()
        flush()

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
        self.build_info = {"last_cached": 0.0, "games": {}}

    def test_cache_buttons_are_aligned_right(self):
        for checkbox, button in (
            (self.popup.cache_details, self.popup.cache_details_btn),
            (self.popup.cache_builds, self.popup.cache_builds_btn),
            (self.popup.cache_artwork, self.popup.cache_artwork_btn),
        ):
            top = button.parentWidget()
            layout = top.layout()
            self.assertEqual(layout.indexOf(checkbox), 0)
            self.assertEqual(layout.indexOf(button), 1)
            self.assertTrue(
                layout.itemAt(1).alignment() & Qt.AlignmentFlag.AlignRight,
                "the Cache button must be right-aligned in its row",
            )
            self.assertEqual(button.text(), "Cache")

    def test_sizes_are_shown_in_kb(self):
        self.assertEqual(self.popup.details_size.text(), "2 kB")
        self.assertEqual(self.popup.builds_size.text(), "3 kB")
        self.assertEqual(self.popup.artwork_size.text(), "5,120 kB")

    def test_builds_row_shows_last_cached_and_version_info(self):
        self.assertIn("Last cached:", self.popup.builds_last.text())
        self.assertNotIn("never", self.popup.builds_last.text())
        self.assertIsNotNone(self.popup.builds_info)

        tooltip = self.popup.builds_info.toolTip()
        self.assertIn(GAMES["hsr"]["name"], tooltip)
        self.assertIn("live 3.8", tooltip)
        self.assertIn("latest 3.9", tooltip)
        self.assertIn("(now 3.9)", tooltip)
        self.assertIn(GAMES["ww"]["name"], tooltip)
        self.assertIn("live 2.6", tooltip)

    def test_builds_row_shows_never_without_metadata(self):
        self.build_info = {"last_cached": 0.0, "games": {}}
        self.popup._update_cache_meta()

        self.assertEqual(self.popup.builds_last.text(), "Last cached: never")
        self.assertIn("No build cache recorded", self.popup.builds_info.toolTip())

    def test_artwork_warning_cancel_does_not_start(self):
        self.popup._confirm_artwork_download = lambda: False

        QTest.mouseClick(self.popup.cache_artwork_btn, Qt.MouseButton.LeftButton)
        flush()

        self.assertEqual(self.manager.started, [])
        self.assertFalse(self.manager.cancelled)

    def test_artwork_warning_accept_starts_and_enables_the_setting(self):
        self.popup.cache_artwork.setChecked(False)
        self.saved.clear()
        self.popup._confirm_artwork_download = lambda: True

        QTest.mouseClick(self.popup.cache_artwork_btn, Qt.MouseButton.LeftButton)
        flush()

        self.assertEqual(self.manager.started, [PRELOAD_ARTWORK])
        self.assertTrue(
            self.popup.cache_artwork.isChecked(),
            "an explicit Cache click should enable the matching setting",
        )
        self.assertEqual(self.saved[-1]["cache_character_artwork"], True)
        self.assertEqual(self.popup.cache_artwork_btn.text(), "Cancel")
        self.assertFalse(self.popup.cache_details_btn.isEnabled())
        self.assertFalse(self.popup.cache_builds_btn.isEnabled())
        self.assertFalse(self.popup.clear_cache_btn.isEnabled())

    def test_details_button_starts_the_details_cache_only(self):
        self.popup.cache_details.setChecked(False)
        self.saved.clear()

        QTest.mouseClick(self.popup.cache_details_btn, Qt.MouseButton.LeftButton)
        flush()

        self.assertEqual(self.manager.started, [PRELOAD_DETAILS])
        self.assertTrue(self.popup.cache_details.isChecked())
        self.assertEqual(
            self.saved[-1],
            {
                "cache_character_details": True,
                "cache_character_builds": True,
                "cache_character_artwork": True,
            },
        )

    def test_builds_button_starts_the_builds_cache_only(self):
        self.popup.cache_details.setChecked(False)
        self.popup.cache_builds.setChecked(False)
        self.popup.cache_artwork.setChecked(False)
        self.saved.clear()

        QTest.mouseClick(self.popup.cache_builds_btn, Qt.MouseButton.LeftButton)
        flush()

        self.assertEqual(self.manager.started, [PRELOAD_BUILDS])
        self.assertTrue(self.popup.cache_builds.isChecked())
        self.assertFalse(self.popup.cache_details.isChecked())
        self.assertFalse(self.popup.cache_artwork.isChecked())
        self.assertEqual(
            self.saved[-1],
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

        self.assertEqual(self.popup.cache_builds_btn.text(), "Cancel")
        self.assertIn("2/10", self.popup.cache_status.text())

        QTest.mouseClick(self.popup.cache_builds_btn, Qt.MouseButton.LeftButton)
        flush()

        self.assertTrue(self.manager.cancelled)
        self.assertEqual(self.popup.cache_builds_btn.text(), "Stopping...")

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

        self.assertIn("before clearing", self.popup.cache_status.text())

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

        clear_api.assert_called_once()
        clear_images.assert_called_once()
        self.assertEqual(self.clear_calls, ["api"])
        self.assertEqual(self.popup.details_size.text(), "0 kB")
        self.assertEqual(self.popup.builds_size.text(), "0 kB")
        self.assertEqual(self.popup.artwork_size.text(), "0 kB")
        self.assertEqual(self.popup.builds_last.text(), "Last cached: never")
        self.assertEqual(self.popup.cache_status.text(), "Cache cleared.")

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

        text = self.popup.cache_status.text()
        self.assertIn("Cached 7 builds.", text)
        self.assertIn("1 failed", text)
        self.assertIn("2 without builds", text)

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

        text = self.popup.cache_status.text()
        self.assertIn("Cached 7 detail pages.", text)
        self.assertIn("2 unavailable", text)


if __name__ == "__main__":
    unittest.main()
