"""Regression test for the card strip's horizontal scrollbar.

The shared ``AppScrollBar`` contentItem originally only set ``implicitWidth``
(the thickness of a *vertical* bar).  A horizontal bar is sized by its
contentItem's ``implicitHeight``, so it collapsed to zero height and the
scrollbar disappeared after the QML deduplication work.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Property, QUrl, Qt, Signal, Slot
from PySide6.QtWidgets import QWidget

from support import QtTestCase, find_qml_item, flush, wait

from nanoka_viewer.ui import qml_host, view_model
from nanoka_viewer.ui.view_model import SectionsModel

_HSR_CHAR = {
    "en": "Testchar",
    "rank": 5,
    "damageType": "Physical",
    "baseType": "Warrior",
    "icon": "TestIcon",
    "release": None,
}


class _StubViewer(QObject):
    """The smallest object ``Main.qml`` accepts as its ``viewer``."""

    changed = Signal()
    statusText = Property(str, lambda self: "Ready", notify=changed)
    cacheText = Property(str, lambda self: "", notify=changed)
    reloadText = Property(str, lambda self: "Reload", notify=changed)
    reloadEnabled = Property(bool, lambda self: True, notify=changed)

    @Slot()
    def reload(self):
        pass

    @Slot()
    def openSettings(self):
        pass

    @Slot(str, str)
    def openDetails(self, game, char_id):
        pass

    @Slot(str)
    def openExternal(self, url):
        pass


class GameSectionScrollBarTests(QtTestCase):
    def test_horizontal_scrollbar_content_item_has_thickness(self):
        self.viewer = _StubViewer()
        self.sections = SectionsModel()
        self.sections.sync(["hsr"])
        section = self.sections.section("hsr")
        self.assertIsNotNone(section)
        # Real artwork URLs would make the offscreen QML engine fetch remote
        # images from its pixmap thread while the delegates are created, which
        # hangs this test.  The scrollbar geometry does not depend on artwork.
        with (
            patch.object(view_model, "get_character_image", return_value=""),
            patch.object(view_model, "get_element_image", return_value=""),
            patch.object(view_model, "get_specialty_image", return_value=""),
        ):
            section.characters.append_many(
                [(f"10{index:02d}", _HSR_CHAR, False) for index in range(10)]
            )

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
        # Drop the bindings before either object dies, as in test_qml_host.
        self.addCleanup(widget.setSource, QUrl())
        widget.setGeometry(0, 0, 640, 480)
        self.host.show()
        wait(100)
        flush()

        root = widget.rootObject()
        self.assertIsNotNone(root)
        card_list = find_qml_item(root, "cardList")
        self.assertIsNotNone(card_list)
        self.assertGreater(
            card_list.property("contentWidth"),
            card_list.width(),
            "the fixture must overflow the card strip",
        )

        scrollbars = [
            child
            for child in card_list.childItems()
            if child.metaObject().className().startswith("AppScrollBar")
        ]
        self.assertTrue(scrollbars, "the card strip lost its scrollbar")
        scrollbar = scrollbars[0]
        self.assertEqual(
            scrollbar.property("orientation"), Qt.Orientation.Horizontal
        )

        content = scrollbar.property("contentItem")
        self.assertIsNotNone(content)
        self.assertGreater(
            content.height(),
            0,
            "a horizontal scrollbar's contentItem needs implicitHeight",
        )
        self.assertEqual(content.height(), 6)


if __name__ == "__main__":
    unittest.main()
