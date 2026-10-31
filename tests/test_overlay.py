"""Regression tests for the shared overlay base and popup lifecycles."""

from __future__ import annotations

import unittest

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

import nanoka_viewer.ui.settings as settings_ui
from support import (
    QtTestCase,
    find_qml_item,
    flush,
    make_details_host,
    open_details_for,
    wait,
    wait_for,
)

from nanoka_viewer.ui.settings import open_settings
from nanoka_viewer.ui.styles import STYLESHEET


def reset_settings_popup():
    popup = settings_ui._settings_popup
    settings_ui._settings_popup = None
    if popup is None:
        return
    try:
        popup.close_popup()
    except RuntimeError:
        return
    popup.deleteLater()
    flush()


def destroy_widget(widget):
    widget.close()
    widget.deleteLater()
    QApplication.instance().sendPostedEvents(None, QEvent.Type.DeferredDelete)
    flush(2)


class _WheelSpy(QObject):
    """Records the wheel events that reach a widget."""

    def __init__(self):
        super().__init__()
        self.events = []

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            # Keep plain values: Qt destroys the event after delivery, so a
            # stored QWheelEvent would crash the failure message.
            self.events.append(
                (
                    event.position().x(),
                    event.position().y(),
                    event.angleDelta().x(),
                    event.angleDelta().y(),
                )
            )
        return False


class SettingsOverlayTests(QtTestCase):
    def tearDown(self):
        reset_settings_popup()
        super().tearDown()

    def make_host(self):
        host = QWidget()
        host.setStyleSheet(STYLESHEET)
        host.resize(900, 700)
        host.show()
        host.activateWindow()
        self.addCleanup(destroy_widget, host)
        flush()
        return host

    def test_settings_overlay_is_sized_to_host(self):
        host = self.make_host()
        popup = open_settings(host)

        self.assertTrue(popup.isVisible())
        self.assertEqual(popup.geometry(), host.rect())
        self.assertLessEqual(popup.panel_rect().width(), host.width())
        self.assertLessEqual(popup.panel_rect().height(), host.height())

    def test_backdrop_view_is_stacked_above_the_window_content(self):
        host = self.make_host()
        popup = open_settings(host)

        # Qt draws translucent QQuickWidgets before the other widgets of the
        # window, which turns the dimmed backdrop black; the documented fix
        # is WA_AlwaysStackOnTop.
        self.assertTrue(
            popup._qml.testAttribute(
                Qt.WidgetAttribute.WA_AlwaysStackOnTop
            ),
            "the translucent popup view must be stacked on top, or its "
            "backdrop is composited against uninitialised pixels",
        )
        self.assertFalse(
            popup.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground),
            "the popup host itself must not paint a translucent surface",
        )

    def test_wheel_over_the_popup_does_not_reach_the_window(self):
        host = self.make_host()
        popup = open_settings(host)
        flush()
        wait(120)

        local = popup._qml.mapTo(host, popup.panel_rect().center())
        self.assertIs(
            host.childAt(local),
            popup._qml,
            "the wheel must be aimed at the popup view for this test",
        )

        spy = _WheelSpy()
        host.installEventFilter(spy)
        self.addCleanup(host.removeEventFilter, spy)

        # QTest sends a spontaneous event, and Qt only propagates those up
        # the parent widget chain when the scene ignores them; a synthetic
        # QApplication.sendEvent() stops at the view and would prove nothing.
        QTest.wheelEvent(host.windowHandle(), QPointF(local), QPoint(0, -120))
        flush()

        self.assertEqual(
            spy.events,
            [],
            "a wheel event the page does not use must stop at the popup, "
            "not scroll the window content underneath",
        )

    def test_wheel_still_scrolls_an_overflowing_settings_page(self):
        host = self.make_host()
        popup = open_settings(host)
        popup._model.setTab(1)
        flush()
        wait(120)

        page = find_qml_item(popup._qml.rootObject(), "settingsViewPage")
        self.assertGreater(page.property("contentHeight"), page.property("height"))

        # Aim above the reorder list: an inner ListView that can scroll would
        # take the wheel for itself, and this test is about the page.
        point = page.mapToItem(
            popup._qml.rootObject(), QPointF(page.width() / 2, 20)
        ).toPoint()
        event = self._wheel_event(popup._qml, point)
        QApplication.sendEvent(popup._qml, event)
        flush()

        # Wheel scrolling is eased, so the offset settles a moment later.
        wait_for(
            lambda: page.property("contentY") > 0,
            message="the page never scrolled under the wheel",
        )

    @staticmethod
    def _wheel_event(widget, point):
        return QWheelEvent(
            QPointF(point),
            QPointF(widget.mapToGlobal(point)),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )

    def test_escape_closes_settings(self):
        host = self.make_host()
        popup = open_settings(host)

        QTest.keyClick(popup._qml, Qt.Key.Key_Escape)
        flush()

        self.assertFalse(popup.isVisible())

    def test_backdrop_click_closes_but_panel_click_does_not(self):
        host = self.make_host()
        popup = open_settings(host)

        QTest.mouseClick(
            popup._qml,
            Qt.MouseButton.LeftButton,
            pos=popup.panel_rect().center(),
        )
        flush()
        self.assertTrue(popup.isVisible())

        QTest.mouseClick(
            popup._qml, Qt.MouseButton.LeftButton, pos=QPoint(2, 2)
        )
        flush()
        self.assertFalse(popup.isVisible())

    def test_destroyed_host_does_not_leave_a_dangling_popup(self):
        first_host = QWidget()
        first_host.resize(400, 300)
        first_host.show()
        first = open_settings(first_host)
        self.assertIs(settings_ui._settings_popup, first)

        destroy_widget(first_host)

        # Opening settings for a fresh host must not touch the dead wrapper.
        second_host = self.make_host()
        second = open_settings(second_host)
        self.assertTrue(second.isVisible())
        self.assertIsNot(second, first)


class DetailsOverlayLifecycleTests(QtTestCase):
    def test_details_reopens_after_its_host_is_destroyed(self):
        import nanoka_viewer.ui.details as details

        window, _central, _scroll, button, _anchor = make_details_host()
        popup = open_details_for(window, button)
        self.assertTrue(popup.isVisible())

        destroy_widget(window)

        second_window, _central, _scroll, second_button, _anchor = make_details_host()
        self.track_window(second_window)
        second_popup = open_details_for(second_window, second_button)

        self.assertTrue(second_popup.isVisible())
        self.assertIsNot(second_popup, popup)
        self.assertIs(details._popup, second_popup)


if __name__ == "__main__":
    unittest.main()
