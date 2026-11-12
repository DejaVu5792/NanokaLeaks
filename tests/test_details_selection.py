"""Selection behaviour in the details pane.

The details text used to be plain ``Label``/``Text`` items, so nothing could be
copied.  ``SelectableText`` wraps a read-only ``TextEdit``: double-clicking
picks the word under the pointer, dragging after the double-click extends the
selection word by word, and the character name in the artwork column takes part
too.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from support import (
    SAMPLE_DETAIL,
    QtTestCase,
    find_qml_item,
    flush,
    make_details_host,
    open_details_for,
    wait,
    wait_for,
)

import nanoka_viewer.ui.details as details_ui

OVERVIEW = "Alpha beta gamma delta epsilon"

# The popup loads details asynchronously, so wait for the cards to exist.
TIMEOUT = 4000


class SelectableDetailsTests(QtTestCase):
    def _open(self, detail=None):
        details_ui.load_character_detail = lambda game, char_id: (
            detail or replace(SAMPLE_DETAIL, overview=OVERVIEW)
        )
        window, _central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)
        wait_for(
            lambda: popup._model.state == "ready",
            timeout=TIMEOUT,
            message="the details never became ready",
        )
        wait(80)
        return popup

    def _find(self, popup, object_name):
        item = find_qml_item(popup._qml.rootObject(), object_name)
        self.assertIsNotNone(item, f"QML item {object_name!r} was not created")
        return item

    def _point_in(self, popup, item, x, y):
        """Map a point inside *item* into the QML widget's coordinates."""
        point = item.mapToItem(popup._qml.rootObject(), x, y)
        return QPoint(round(point.x()), round(point.y()))

    def _double_click(self, popup, item, x=2):
        QTest.mouseDClick(
            popup._qml,
            Qt.MouseButton.LeftButton,
            pos=self._point_in(popup, item, x, item.height() / 2),
        )
        flush()

    def _send_mouse(self, popup, kind, point, buttons, button):
        event = QMouseEvent(
            kind,
            QPointF(point),
            QPointF(popup._qml.mapToGlobal(point)),
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(popup._qml, event)
        flush(2)

    def _drag_from_double_click(self, popup, item, start_x, end_x):
        """Click twice, then drag from the word selected by the double-click.

        ``QTest.mouseDClick`` releases the button between clicks, so it cannot
        express a double-click-drag.  Send the events by hand instead: a full
        first click, a second press, the double-click event, then the moves
        with the button still held.
        """
        start = self._point_in(popup, item, start_x, item.height() / 2)
        end = self._point_in(popup, item, end_x, item.height() / 2)
        left = Qt.MouseButton.LeftButton
        none = Qt.MouseButton.NoButton

        self._send_mouse(popup, QEvent.Type.MouseButtonPress, start, left, left)
        self._send_mouse(popup, QEvent.Type.MouseButtonRelease, start, none, left)
        self._send_mouse(popup, QEvent.Type.MouseButtonPress, start, left, left)
        self._send_mouse(popup, QEvent.Type.MouseButtonDblClick, start, left, left)
        for step in range(1, 5):
            point = QPoint(
                round(start.x() + (end.x() - start.x()) * step / 4),
                start.y(),
            )
            self._send_mouse(popup, QEvent.Type.MouseMove, point, left, none)
        self._send_mouse(popup, QEvent.Type.MouseButtonRelease, end, none, left)
        flush()

    def test_double_click_selects_the_word_under_the_pointer(self):
        popup = self._open()
        overview = self._find(popup, "detailsOverview")

        self._double_click(popup, overview)

        self.assertEqual(overview.property("selectedText"), "Alpha")

    def test_double_click_drag_extends_the_selection_by_words(self):
        popup = self._open()
        overview = self._find(popup, "detailsOverview")

        # Stop inside "delta": word selection must take the whole word, not
        # the characters up to the pointer.
        self._drag_from_double_click(
            popup,
            overview,
            start_x=2,
            end_x=overview.property("contentWidth") * 0.65,
        )

        self.assertEqual(
            overview.property("selectedText"),
            "Alpha beta gamma delta",
        )

    def test_character_name_in_the_art_column_is_selectable(self):
        popup = self._open()
        name = self._find(popup, "detailArtName")

        self._double_click(popup, name)

        self.assertEqual(name.property("selectedText"), "Test")


if __name__ == "__main__":
    unittest.main()
