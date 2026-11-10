"""Regression tests for the shared card-strip scrollbar.

The shared ``AppScrollBar`` contentItem originally only set ``implicitWidth``
(the thickness of a *vertical* bar).  A horizontal bar is sized by its
contentItem's ``implicitHeight``, so it collapsed to zero height and the
scrollbar disappeared after the QML deduplication work.

The hover tests pin the KDE HIG behaviour: hovering signals interactivity by
shading the handle and must not change its thickness, which would reflow the
content beside it.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Property, QPoint, QPointF, QUrl, Qt, Signal, Slot
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from support import QtTestCase, find_qml_item, flush, wait, wait_for

from nanoka_viewer.ui import filter_model, qml_host, view_model
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
    def _open_card_strip(self):
        """Build a window whose card strip overflows and return its bar."""
        self.viewer = _StubViewer()
        self.sections = SectionsModel()
        with (
            patch.object(filter_model, "get_element_image", return_value=""),
            patch.object(filter_model, "get_specialty_image", return_value=""),
        ):
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
        return widget, scrollbars[0]

    def test_horizontal_scrollbar_content_item_has_thickness(self):
        _widget, scrollbar = self._open_card_strip()
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

    def test_scrollbar_highlights_on_hover_without_changing_size(self):
        widget, scrollbar = self._open_card_strip()
        content = scrollbar.property("contentItem")
        root = widget.rootObject()
        idle_color = content.property("color")
        idle_size = (content.width(), content.height())

        # Hovering only changes shading (KDE HIG: signal interactivity through
        # a hover effect), never the bar's thickness, so content must not
        # reflow.  The point is the middle of the handle, mapped to the widget
        # the QQuickWidget paints into.
        center = content.mapToItem(
            root, QPointF(content.width() / 2, content.height() / 2)
        )
        QTest.mouseMove(widget, center.toPoint())

        wait_for(
            lambda: scrollbar.property("hovered"),
            message="the scrollbar never saw the pointer hover",
        )
        wait_for(
            lambda: content.property("color") != idle_color,
            message="the scrollbar handle did not change colour on hover",
        )
        self.assertEqual(
            (content.width(), content.height()),
            idle_size,
            "hover must not resize the scrollbar or reflow its content",
        )

        QTest.mouseMove(widget, QPoint(5, 5))
        wait_for(
            lambda: not scrollbar.property("hovered"),
            message="the scrollbar never saw the pointer leave",
        )
        wait_for(
            lambda: content.property("color") == idle_color,
            message="the hover shading did not fade back out",
        )

    def test_main_list_uses_the_shared_hover_scrollbar(self):
        widget, _scrollbar = self._open_card_strip()
        section_list = find_qml_item(widget.rootObject(), "sectionList")
        self.assertIsNotNone(section_list)

        vertical_bars = [
            child
            for child in section_list.childItems()
            if child.metaObject().className().startswith("AppScrollBar")
        ]
        self.assertTrue(
            vertical_bars,
            "the main list still uses its own scrollbar instead of AppScrollBar",
        )


if __name__ == "__main__":
    unittest.main()
