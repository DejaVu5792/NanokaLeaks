"""Smoke tests for the QML host scaffold.

These pin down the environment-sensitive parts of the QML bridge: source
discovery, loading under the headless ``offscreen`` platform, size coupling
between the host widget and the QML root, and palette-driven background
painting (the app must follow the system light/dark theme).
"""

from __future__ import annotations

import unittest

from PySide6.QtGui import QPalette
from PySide6.QtQuickWidgets import QQuickWidget

from support import QtTestCase, flush

from nanoka_viewer.ui import qml_host


class QmlHostTests(QtTestCase):
    def test_qml_sources_live_next_to_the_package(self):
        directory = qml_host.qml_dir()
        self.assertTrue(directory.is_dir(), directory)
        self.assertTrue(qml_host.qml_file().is_file())

    def test_missing_qml_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            qml_host.qml_file("NoSuchFile.qml")

    def _load_widget(self) -> QQuickWidget:
        widget = qml_host.create_qml_widget()
        self.addCleanup(widget.deleteLater)
        widget.resize(640, 480)
        widget.show()
        flush()
        return widget

    def test_widget_loads_main_qml_without_errors(self):
        widget = self._load_widget()

        self.assertEqual(widget.status(), QQuickWidget.Status.Ready)
        self.assertEqual(list(widget.errors()), [])

        root = widget.rootObject()
        self.assertIsNotNone(root)
        self.assertEqual(root.property("objectName"), "mainRoot")

    def test_root_item_follows_the_host_size(self):
        widget = self._load_widget()
        root = widget.rootObject()

        self.assertEqual(
            (root.property("x"), root.property("y")), (0.0, 0.0)
        )
        self.assertEqual(
            (root.property("width"), root.property("height")), (640.0, 480.0)
        )

        widget.resize(500, 360)
        flush()
        self.assertEqual(
            (root.property("width"), root.property("height")), (500.0, 360.0)
        )

    def test_root_paints_the_theme_background(self):
        """The QML root must resolve palette(window), not hard-coded colours."""
        widget = self._load_widget()
        root = widget.rootObject()

        expected = self.application.palette().color(QPalette.ColorRole.Window)
        bound = root.property("color")
        self.assertEqual(bound, expected, "root color must bind to palette.window")

        actual = widget.grab().toImage().pixelColor(4, 4)
        self.assertLessEqual(
            max(abs(a - b) for a, b in zip(actual.getRgb()[:3], expected.getRgb()[:3])),
            2,
            f"root background must render as {expected.name()}, got {actual.name()}",
        )


if __name__ == "__main__":
    unittest.main()
