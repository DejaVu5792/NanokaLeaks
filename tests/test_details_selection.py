"""Selection behaviour in the details pane.

The details text used to be plain ``Label``/``Text`` items, so nothing could be
copied.  ``SelectableText`` wraps a read-only ``TextEdit``: double-clicking
picks the word under the pointer, dragging after the double-click extends the
selection word by word, and the character name in the artwork column takes part
too.  Dragging blank space beside the glyphs scrolls the pane instead, because
text rows are full-width layout items.
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
from nanoka_viewer.api.detail_models import SkillDetail

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

    def _hover(self, popup, item, x):
        """Move the pointer inside *item* and return the widget cursor shape."""
        point = self._point_in(popup, item, x, item.height() / 2)
        event = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(point),
            QPointF(popup._qml.mapToGlobal(point)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(popup._qml, event)
        flush()
        return popup._qml.cursor().shape()

    def _drag_vertically(self, popup, item, x, start_y, delta_y):
        """Press at (*x*, *start_y*) inside *item* and drag by *delta_y*."""
        start = self._point_in(popup, item, x, start_y)
        left = Qt.MouseButton.LeftButton
        none = Qt.MouseButton.NoButton

        self._send_mouse(popup, QEvent.Type.MouseButtonPress, start, left, left)
        for step in range(1, 7):
            point = QPoint(start.x(), round(start.y() + delta_y * step / 6))
            self._send_mouse(popup, QEvent.Type.MouseMove, point, left, none)
        end = QPoint(start.x(), start.y() + delta_y)
        self._send_mouse(popup, QEvent.Type.MouseButtonRelease, end, none, left)
        wait(80)

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

    def _open_with_scrollable_overview(self):
        detail = replace(
            SAMPLE_DETAIL,
            overview="Short",
            # Enough collapsed skills to make the pane scrollable, so a drag
            # over blank space has somewhere to go.
            skills=[
                SkillDetail(f"Skill {index}", "Attack", "Body", [], 1)
                for index in range(20)
            ],
        )
        return self._open(detail)

    def test_cursor_is_an_i_beam_over_glyphs(self):
        popup = self._open()
        overview = self._find(popup, "detailsOverview")

        self.assertEqual(
            self._hover(popup, overview, 2),
            Qt.CursorShape.IBeamCursor,
        )

    def test_cursor_is_an_arrow_over_blank_space(self):
        popup = self._open_with_scrollable_overview()
        overview = self._find(popup, "detailsOverview")

        self.assertEqual(
            self._hover(popup, overview, overview.width() * 0.9),
            Qt.CursorShape.ArrowCursor,
        )

    def test_cursor_is_a_hand_over_rule_term_links(self):
        popup = self._open(
            replace(
                SAMPLE_DETAIL,
                overview='<a href="term:term-1">Gradient</a> is a rule term.',
            )
        )
        overview = self._find(popup, "detailsOverview")

        self.assertEqual(
            self._hover(popup, overview, 8),
            Qt.CursorShape.PointingHandCursor,
        )

    def test_dragging_blank_space_scrolls_the_pane(self):
        popup = self._open_with_scrollable_overview()
        overview = self._find(popup, "detailsOverview")
        scroll = self._find(popup, "detailsScroll")
        scroll.setProperty("contentY", 0.0)
        flush()

        # Far right of the overview row: past the end of "Short", so the press
        # lands on blank space and must reach the Flickable.
        self._drag_vertically(
            popup,
            overview,
            overview.width() * 0.9,
            overview.height() / 2,
            -120,
        )

        self.assertGreater(
            scroll.property("contentY"),
            0.0,
            "dragging blank space must scroll the details pane",
        )
        self.assertEqual(
            overview.property("selectedText"),
            "",
            "dragging blank space must not start a text selection",
        )

    def test_dragging_across_text_still_selects(self):
        popup = self._open_with_scrollable_overview()
        overview = self._find(popup, "detailsOverview")
        scroll = self._find(popup, "detailsScroll")
        scroll.setProperty("contentY", 0.0)
        flush()

        # Start on a glyph: this drag belongs to the TextEdit, not the pane.
        self._drag_vertically(
            popup,
            overview,
            2,
            overview.height() / 2,
            -120,
        )

        self.assertNotEqual(
            overview.property("selectedText"),
            "",
            "dragging across text must still select it",
        )
        self.assertEqual(
            scroll.property("contentY"),
            0.0,
            "a text drag must not scroll the details pane",
        )


if __name__ == "__main__":
    unittest.main()
