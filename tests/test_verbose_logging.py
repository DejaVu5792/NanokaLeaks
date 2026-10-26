"""Tests for the verbose (``-v``) diagnostics added around the mouse bug.

The fix relies on ``-v`` logs to prove where a stray press went, so the
logging itself is part of the contract:
* opening details logs the grabber / widget under the cursor / focus,
* a stale hover on the triggering View button is logged and cleared,
* the modal input guard logs every event it swallows,
* ``NANOKA_TRACE_MOUSE=1`` provides a widget-level mouse trace.
"""

from __future__ import annotations

import unittest

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QWidget

from support import QtTestCase, flush, make_details_host, open_details_for

from nanoka_viewer.ui.main_window import _MouseTraceFilter


class DetailsLoggingTests(QtTestCase):
    def test_open_logs_trigger_state_and_guard(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        button.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, True)

        with self.assertLogs("nanoka_viewer.ui.details", level="DEBUG") as logs:
            open_details_for(window, button)

        output = "\n".join(logs.output)
        self.assertIn("open details hsr/1", output)
        self.assertIn("widget_at_cursor=", output)
        self.assertIn("grabber=", output)
        self.assertIn("cleared stale hover", output)
        self.assertIn("installed modal input guard", output)
        self.assertIn("details shown:", output)

    def test_blocked_press_is_logged(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        open_details_for(window, button)

        with self.assertLogs("nanoka_viewer.ui.details", level="DEBUG") as logs:
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            flush()

        output = "\n".join(logs.output)
        self.assertIn("blocked MouseButtonPress", output)
        self.assertIn("blocked MouseButtonRelease", output)

    def test_backdrop_close_is_logged(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)

        with self.assertLogs("nanoka_viewer.ui.details", level="DEBUG") as logs:
            QTest.mouseClick(popup, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
            flush()

        output = "\n".join(logs.output)
        self.assertIn("overlay press", output)
        self.assertIn("overlay release", output)
        self.assertIn("closing details popup", output)


class MouseTraceTests(QtTestCase):
    def test_mouse_trace_reports_receiver_and_hover_state(self):
        host = QWidget()
        self.addCleanup(host.deleteLater)
        host.resize(240, 100)
        host.show()
        host.activateWindow()
        button = QPushButton("Trace")
        button.setParent(host)
        button.setGeometry(10, 10, 120, 30)
        button.show()
        flush()

        trace = _MouseTraceFilter()
        self.application.installEventFilter(trace)
        self.addCleanup(self.application.removeEventFilter, trace)

        with self.assertLogs("mouse.trace", level="DEBUG") as logs:
            event = QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                QPointF(5, 5),
                QPointF(button.mapToGlobal(QPoint(5, 5))),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            self.application.sendEvent(button, event)
            flush(2)

        output = "\n".join(logs.output)
        self.assertIn("MouseButtonPress", output)
        self.assertIn("QPushButton", output)
        self.assertIn("underMouse=", output)
        self.assertIn("grabber=", output)


if __name__ == "__main__":
    unittest.main()
