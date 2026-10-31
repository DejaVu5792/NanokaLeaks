"""Smoke tests for the QML host.

These pin down the environment-sensitive parts of the QML bridge: source
discovery, loading under the headless ``offscreen`` platform, size coupling
between the host widget and the QML root, palette-driven background painting,
and the registrations the tree depends on (context properties, image
provider).
"""

from __future__ import annotations

import unittest

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QPalette
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget

from support import QtTestCase, find_qml_item, flush, wait

from nanoka_viewer.ui import qml_host
from nanoka_viewer.ui.image_provider import NanokaImageProvider
from nanoka_viewer.ui.view_model import SectionsModel


class _StubViewer(QObject):
    """The smallest object ``Main.qml`` accepts as its ``viewer``."""

    changed = Signal()
    statusText = Property(str, lambda self: "Ready", notify=changed)
    cacheText = Property(str, lambda self: "", notify=changed)
    reloadText = Property(str, lambda self: "Reload", notify=changed)
    reloadEnabled = Property(bool, lambda self: True, notify=changed)

    def __init__(self):
        super().__init__()
        self.calls = []

    @Slot()
    def reload(self):
        self.calls.append("reload")

    @Slot()
    def openSettings(self):
        self.calls.append("settings")

    @Slot(str, str)
    def openDetails(self, game, char_id):
        self.calls.append(("details", game, char_id))

    @Slot(str)
    def openExternal(self, url):
        self.calls.append(("external", url))


class QmlHostTests(QtTestCase):
    def test_qml_sources_live_next_to_the_package(self):
        directory = qml_host.qml_dir()
        self.assertTrue(directory.is_dir(), directory)
        self.assertTrue(qml_host.qml_file().is_file())

    def test_missing_qml_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            qml_host.qml_file("NoSuchFile.qml")

    def _load_widget(self) -> QQuickWidget:
        self.viewer = _StubViewer()
        self.sections = SectionsModel()
        # Keep the QQuickWidget a *child* of a plain host: the offscreen
        # platform resizes top-level windows asynchronously (to 908x1038 on
        # this machine), which would make top-level size assertions racy.
        self.host = QWidget()
        self.addCleanup(self.host.deleteLater)
        widget = qml_host.create_qml_widget(
            self.host,
            context_properties={
                "viewer": self.viewer,
                "sections": self.sections,
            },
        )
        self.addCleanup(widget.deleteLater)
        # Drop the bindings to the stub *before* either object dies, otherwise
        # teardown re-evaluates them against a deleted context object.
        self.addCleanup(widget.setSource, QUrl())
        widget.setGeometry(0, 0, 640, 480)
        self.host.show()
        wait(50)
        flush()
        return widget

    def test_widget_loads_main_qml_without_errors(self):
        widget = self._load_widget()

        self.assertEqual(widget.status(), QQuickWidget.Status.Ready)
        self.assertEqual(list(widget.errors()), [])

        root = widget.rootObject()
        self.assertIsNotNone(root)
        self.assertEqual(root.property("objectName"), "mainRoot")

    def test_context_properties_are_bound_before_loading(self):
        widget = self._load_widget()
        root = widget.rootObject()

        status = find_qml_item(root, "statusLabel")
        self.assertIsNotNone(status)
        self.assertEqual(status.property("text"), "Ready")

        reload_button = find_qml_item(root, "reloadButton")
        self.assertEqual(reload_button.property("text"), "Reload")

    def test_image_provider_is_registered(self):
        widget = self._load_widget()

        provider = widget.engine().imageProvider("nanoka")
        self.assertIsInstance(provider, NanokaImageProvider)

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
