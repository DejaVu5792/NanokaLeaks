"""Regression tests for the View-button click-through / stale-hover bug.

Scenario reported: click a card's View button, leave the pointer on it, the
details overlay opens - and the button can still be pressed underneath it.

The overlay is a native Wayland subsurface that must stay above the cards'
native scroll-area surface. Even when compositor stacking misbehaves, the
popup installs a modal input guard so presses, releases, wheel and keyboard
input can never reach the host content. Opening also clears the stale hover
state the View button kept because Wayland never delivered a Leave event.
"""

from __future__ import annotations

import unittest

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

import nanoka_viewer.ui.details as details
from support import (
    QtTestCase,
    button_center_in,
    find_qml_item,
    flush,
    make_details_host,
    open_details_for,
)


class ViewButtonInteractionTests(QtTestCase):
    def test_widget_under_view_button_is_the_overlay(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)

        self.assertTrue(popup.isVisible())
        hit = central.childAt(button_center_in(button, central))
        self.assertIsNotNone(hit, "something must cover the card View button")
        self.assertTrue(
            hit is popup or popup.isAncestorOf(hit),
            "the overlay must hit-test above the card View button",
        )
        at_cursor = QApplication.widgetAt(
            button.mapToGlobal(button.rect().center())
        )
        self.assertTrue(
            at_cursor is popup or popup.isAncestorOf(at_cursor),
            "the overlay must be the widget under the pointer",
        )

    def test_open_clears_stale_hover_and_pressed_state(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)

        # Simulate Wayland not delivering a Leave event when the overlay shows.
        button.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, True)
        button.setDown(True)
        self.assertTrue(button.underMouse())

        popup = open_details_for(window, button)

        self.assertTrue(popup.isVisible())
        self.assertFalse(
            button.underMouse(),
            "the View button must not keep its hover state under the overlay",
        )
        self.assertFalse(button.isDown())

    def test_press_on_host_content_is_blocked_while_open(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)

        clicks = []
        button.clicked.connect(lambda: clicks.append(1))
        popup = open_details_for(window, button)
        request_id = popup._request_id

        # Bypass hit-testing on purpose: this is what happens when the native
        # scroll-area surface is mistakenly stacked above the overlay.
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        flush()

        self.assertEqual(clicks, [], "View must not activate under the overlay")
        self.assertTrue(popup.isVisible())
        self.assertEqual(popup._request_id, request_id, "popup must not reload")

    def test_keyboard_activation_of_focused_view_button_is_blocked(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)

        clicks = []
        button.clicked.connect(lambda: clicks.append(1))
        popup = open_details_for(window, button)
        self.assertTrue(popup.isVisible())

        button.setFocus()
        QTest.keyClick(button, Qt.Key.Key_Space)
        QTest.keyClick(button, Qt.Key.Key_Return)
        flush()

        self.assertEqual(clicks, [], "Space/Return must not re-trigger View")

    def test_wheel_over_host_content_is_blocked_while_open(self):
        window, central, scroll, button, _anchor = make_details_host()
        self.track_window(window)

        content_layout = scroll.widget().layout()
        for index in range(60):
            content_layout.addWidget(QLabel(f"row {index}"))
        flush()

        popup = open_details_for(window, button)
        viewport = scroll.viewport()

        def wheel():
            event = QWheelEvent(
                QPointF(10, 10),
                QPointF(viewport.mapToGlobal(QPoint(10, 10))),
                QPoint(0, 0),
                QPoint(0, -120),
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.NoScrollPhase,
                False,
            )
            QApplication.sendEvent(viewport, event)
            flush(2)

        wheel()
        self.assertEqual(
            scroll.verticalScrollBar().value(),
            0,
            "wheel events must not scroll the card list under the overlay",
        )

        popup.close_popup()
        flush()
        wheel()
        self.assertGreater(
            scroll.verticalScrollBar().value(),
            0,
            "the same wheel event must work again once the overlay is closed",
        )

    def test_unrelated_windows_are_not_blocked(self):
        window, _central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)

        other = QPushButton("Other window")
        other_clicked = []
        other.clicked.connect(lambda: other_clicked.append(1))
        other.show()
        self.addCleanup(other.deleteLater)
        flush()

        QTest.mouseClick(other, Qt.MouseButton.LeftButton)
        flush()

        self.assertTrue(popup.isVisible())
        self.assertEqual(
            other_clicked,
            [1],
            "the guard must only apply to the popup's own host window",
        )


class BackdropAndLifecycleTests(QtTestCase):
    def test_press_on_backdrop_does_not_close_until_release(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)

        QTest.mousePress(
            popup._qml, Qt.MouseButton.LeftButton, pos=QPoint(4, 4)
        )
        flush()
        self.assertTrue(
            popup.isVisible(),
            "the overlay must stay open between press and release so the "
            "underlying View button never receives a lone release",
        )

        QTest.mouseRelease(
            popup._qml, Qt.MouseButton.LeftButton, pos=QPoint(4, 4)
        )
        flush()
        self.assertFalse(popup.isVisible())
        self.assertFalse(popup._input_guard_installed)

    def test_click_inside_the_panel_keeps_the_popup_open(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)

        point = popup.panel_rect().center()
        QTest.mouseClick(popup._qml, Qt.MouseButton.LeftButton, pos=point)
        flush()

        self.assertTrue(popup.isVisible())

    def test_popup_controls_remain_interactive(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)

        close_button = find_qml_item(
            popup._qml.rootObject(), "detailsCloseButton"
        )
        self.assertIsNotNone(close_button, "the QML Close button was not created")
        root = popup._qml.rootObject()
        centre = close_button.mapToItem(
            root, close_button.width() / 2, close_button.height() / 2
        )
        QTest.mouseClick(
            popup._qml,
            Qt.MouseButton.LeftButton,
            pos=QPoint(round(centre.x()), round(centre.y())),
        )
        flush()

        self.assertFalse(
            popup.isVisible(),
            "the input guard must not swallow events inside the popup",
        )

    def test_escape_still_closes_the_popup(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)

        QTest.keyClick(popup._qml, Qt.Key.Key_Escape)
        flush()

        self.assertFalse(popup.isVisible())

    def test_opening_the_same_character_twice_does_not_reload(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)
        request_id = popup._request_id

        details.open_details("hsr", "1", None, window, source=button)
        details.open_details("hsr", "1", None, window, source=button)
        flush()

        self.assertTrue(popup.isVisible())
        self.assertEqual(
            popup._request_id,
            request_id,
            "a second View activation must not reset the details to loading",
        )

    def test_close_removes_guard_and_returns_focus(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)

        self.assertTrue(popup._input_guard_installed)
        focused = QApplication.focusWidget()
        self.assertTrue(
            focused is popup or popup.isAncestorOf(focused),
            "focus must start inside the overlay",
        )

        popup.close_popup()
        flush()

        self.assertFalse(popup.isVisible())
        self.assertFalse(popup._input_guard_installed)
        focused = QApplication.focusWidget()
        self.assertFalse(
            focused is not None and (focused is popup or popup.isAncestorOf(focused)),
            "focus must leave the overlay when it closes",
        )

    def test_opening_clears_hover_of_previously_hovered_button(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)

        popup = open_details_for(window, button)
        popup.close_popup()
        flush()

        button.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, True)
        popup = open_details_for(window, button)
        self.assertFalse(button.underMouse())
        self.assertTrue(popup.isVisible())


if __name__ == "__main__":
    unittest.main()
