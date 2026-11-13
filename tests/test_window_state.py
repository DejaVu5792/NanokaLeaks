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
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QByteArray, QDataStream, QRect, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMainWindow

from support import QtTestCase, flush

import nanoka_viewer.ui.main_window as main_window
from nanoka_viewer import settings as app_settings


def saved_window_state(settings: QSettings):
    """Return the normal rect and window flags stored for the viewer."""
    data = settings.value(main_window._WINDOW_GEOMETRY_KEY)
    assert isinstance(data, QByteArray)
    stream = QDataStream(data)
    stream.setVersion(QDataStream.Qt_4_0)
    assert stream.readUInt32() == main_window._GEOMETRY_MAGIC
    stream.readUInt16()
    stream.readUInt16()
    main_window._read_rect(stream)  # frame geometry
    normal = main_window._read_rect(stream)
    stream.readInt32()  # screen number
    maximized = stream.readUInt8()
    fullscreen = stream.readUInt8()
    return normal, maximized, fullscreen


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

    def _saved_window_state(self):
        return saved_window_state(self.settings)

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

    def test_maximised_geometry_is_saved_as_normal(self):
        original = self._shown_window(720, 560)
        original.showMaximized()
        flush()
        main_window.save_window_geometry(original)

        normal, maximized, fullscreen = self._saved_window_state()
        self.assertEqual((maximized, fullscreen), (0, 0))
        self.assertEqual((normal.width(), normal.height()), (720, 560))

    def test_maximised_blob_from_an_older_version_restores_unmaximised(self):
        original = self._shown_window(720, 560)
        original.showMaximized()
        flush()
        # Before the fix the viewer stored saveGeometry() untouched.
        self.settings.setValue(
            main_window._WINDOW_GEOMETRY_KEY, original.saveGeometry()
        )
        self.settings.sync()

        reopened = self._window(500, 400)
        self.assertTrue(main_window.restore_window_geometry(reopened))
        self.assertFalse(reopened.isMaximized())
        self.assertEqual((reopened.width(), reopened.height()), (720, 560))

    def test_explicit_normal_geometry_wins_over_the_saved_blob(self):
        original = self._shown_window(720, 560)
        original.showMaximized()
        flush()
        main_window.save_window_geometry(original, QRect(40, 30, 720, 560))

        normal, maximized, fullscreen = self._saved_window_state()
        self.assertEqual((maximized, fullscreen), (0, 0))
        self.assertEqual(
            (normal.x(), normal.y(), normal.width(), normal.height()),
            (40, 30, 720, 560),
        )


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

            save.assert_called_once_with(window, window._normal_geometry)


class ViewerNormalGeometryTests(QtTestCase):
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

    def test_closing_maximised_saves_the_previous_normal_geometry(self):
        window = main_window.NanokaViewer(load_data=False)
        self.addCleanup(window.deleteLater)
        window.show()
        flush()
        window.resize(900, 700)
        flush()
        # The normal size is committed only after the resize settles.
        QTest.qWait(main_window._NORMAL_GEOMETRY_DEBOUNCE_MS + 100)
        expected = (window.width(), window.height())

        window.showMaximized()
        flush()
        self.assertTrue(window.isMaximized())
        self.assertEqual(
            (window._normal_geometry.width(), window._normal_geometry.height()),
            expected,
        )

        window.close()
        flush()

        normal, maximized, fullscreen = saved_window_state(self.settings)
        self.assertEqual((maximized, fullscreen), (0, 0))
        self.assertEqual((normal.width(), normal.height()), expected)


class WindowSettingsLocationTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.config_dir = Path(self._temp.name) / ".config"
        self.settings_dir = self.config_dir / "nanoka_leaks"
        self.config_dir.mkdir(parents=True)
        self.settings_dir.mkdir(parents=True)

        self._patches = [
            patch.object(app_settings, "CONFIG_DIR", self.config_dir),
            patch.object(app_settings, "SETTINGS_DIR", self.settings_dir),
            patch.object(
                app_settings,
                "WINDOW_SETTINGS_FILE",
                self.settings_dir / "window.ini",
            ),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def test_default_window_settings_uses_existing_settings_dir(self):
        settings = main_window._window_settings()
        self.assertEqual(
            Path(settings.fileName()).resolve(),
            (self.settings_dir / "window.ini").resolve(),
        )
        self.assertFalse((self.config_dir / "NanokaLeaks").exists())

    def test_legacy_window_settings_migration(self):
        legacy_dir = self.config_dir / "NanokaLeaks"
        legacy_dir.mkdir(parents=True)
        legacy_file = legacy_dir / "NanokaLeaks.conf"

        legacy_settings = QSettings(
            str(legacy_file), QSettings.Format.IniFormat
        )
        legacy_settings.setValue(
            main_window._WINDOW_GEOMETRY_KEY, QByteArray(b"legacy_geometry")
        )
        legacy_settings.sync()
        self.assertTrue(legacy_file.is_file())

        settings = main_window._window_settings()
        self.assertEqual(
            settings.value(main_window._WINDOW_GEOMETRY_KEY),
            QByteArray(b"legacy_geometry"),
        )
        self.assertFalse(legacy_file.exists())
        self.assertFalse(legacy_dir.exists())

    def test_saving_window_geometry_does_not_create_nanokaleaks_subfolder(self):
        window = QMainWindow()
        window.resize(720, 560)
        self.addCleanup(window.deleteLater)

        main_window.save_window_geometry(window)

        self.assertTrue((self.settings_dir / "window.ini").is_file())
        self.assertFalse((self.config_dir / "NanokaLeaks").exists())

        restored_settings = QSettings(
            str(self.settings_dir / "window.ini"), QSettings.Format.IniFormat
        )
        self.assertIn(
            main_window._WINDOW_GEOMETRY_KEY, restored_settings.allKeys()
        )


if __name__ == "__main__":
    unittest.main()
