"""Tests for native window geometry persistence.

The window no longer carries a hardcoded initial size: it restores the normal
(unmaximised) size and position from the platform-native ``QSettings`` store
and falls back to Qt's default sizing (bounded by the minimum size) on first
run.  Closing while maximised or fullscreen still remembers the size the
window had before it entered that state.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMainWindow

from support import QtTestCase, flush

import nanoka_viewer.ui.main_window as main_window


class WindowGeometryTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.settings = QSettings(
            os.path.join(self._temp.name, "window.ini"),
            QSettings.IniFormat,
        )
        patcher = patch.object(
            main_window, "_window_settings", return_value=self.settings
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _window(self, width: int, height: int) -> QMainWindow:
        window = QMainWindow()
        window.resize(width, height)
        self.addCleanup(window.deleteLater)
        return window

    def test_missing_geometry_leaves_the_window_untouched(self):
        window = self._window(700, 500)

        self.assertFalse(main_window.restore_window_geometry(window))
        self.assertEqual((window.width(), window.height()), (700, 500))

    def test_saved_geometry_is_restored(self):
        original = self._window(720, 560)
        main_window.save_window_geometry(original)

        reopened = self._window(500, 400)
        self.assertTrue(main_window.restore_window_geometry(reopened))
        self.assertEqual((reopened.width(), reopened.height()), (720, 560))

    def test_saving_uses_the_native_settings_store(self):
        main_window.save_window_geometry(self._window(720, 560))

        self.assertIn(
            main_window._WINDOW_GEOMETRY_KEY, self.settings.allKeys()
        )

    def _shown_window(self, width: int, height: int) -> QMainWindow:
        window = self._window(width, height)
        window.show()
        flush()
        return window

    def test_maximised_state_is_not_remembered(self):
        original = self._shown_window(720, 560)
        original.showMaximized()
        flush()
        self.assertTrue(original.isMaximized())
        main_window.save_window_geometry(original)

        reopened = self._window(500, 400)
        self.assertTrue(main_window.restore_window_geometry(reopened))
        self.assertFalse(reopened.isMaximized())
        self.assertEqual((reopened.width(), reopened.height()), (720, 560))

    def test_fullscreen_state_is_not_remembered(self):
        original = self._shown_window(720, 560)
        original.showFullScreen()
        flush()
        self.assertTrue(original.isFullScreen())
        main_window.save_window_geometry(original)

        reopened = self._window(500, 400)
        self.assertTrue(main_window.restore_window_geometry(reopened))
        self.assertFalse(reopened.isFullScreen())
        self.assertEqual((reopened.width(), reopened.height()), (720, 560))


class ViewerWindowStateTests(QtTestCase):
    def test_viewer_restores_on_startup_and_saves_on_close(self):
        with (
            patch.object(main_window, "restore_window_geometry") as restore,
            patch.object(main_window, "save_window_geometry") as save,
        ):
            window = main_window.NanokaViewer(load_data=False)
            self.addCleanup(window.deleteLater)

            restore.assert_called_once_with(window)
            # No hardcoded 950x750: the minimum size is the first-run size.
            self.assertEqual((window.width(), window.height()), (800, 600))

            window.close()
            flush()

            save.assert_called_once_with(window)


if __name__ == "__main__":
    unittest.main()
