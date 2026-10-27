"""Shared behaviour for in-window lightbox overlays.

Both the character-details and settings popups are plain child widgets that
cover the central widget.  Their geometry, backdrop painting, host tracking,
Escape handling and (for modal overlays) input guarding were duplicated nearly
verbatim.  This base class keeps that logic in one place so the two popups only
own their content.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Events that must never reach the host content while a modal overlay is open.
_BLOCKED_INPUT_EVENTS = frozenset(
    {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.Wheel,
        QEvent.Type.ContextMenu,
        QEvent.Type.KeyPress,
        QEvent.Type.KeyRelease,
    }
)


def is_alive(widget: QWidget | None) -> bool:
    """Return whether *widget* still has a live C++ object behind it."""
    if widget is None:
        return False
    try:
        widget.objectName()
    except RuntimeError:
        return False
    return True


class OverlayPopup(QWidget):
    """Base class for the in-window popups.

    Subclasses set the object names / sizing attributes and build their content
    inside ``self.panel_layout``.  They may override :meth:`_on_geometry_changed`
    and :meth:`_on_close` for popup-specific work.
    """

    overlay_object_name = "overlay"
    panel_object_name = "overlayPanel"
    blocks_host_input = False
    log_name = "overlay"
    logger = logging.getLogger(__name__)

    width_ratio = 0.92
    min_width = 560
    max_width = 1180
    hard_min_width = 300
    height_ratio = 0.9
    min_height = 420
    max_height = 880
    hard_min_height = 240
    margin = 24

    def __init__(self, host: QWidget, parent: QWidget | None = None):
        super().__init__(host if parent is None else parent)
        self._host = host
        self._input_guard_installed = False
        self._backdrop_pressed = False

        self.setObjectName(self.overlay_object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

        self.panel = QFrame(self)
        self.panel.setObjectName(self.panel_object_name)
        self.panel_layout = QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(0, 0, 0, 0)
        self.panel_layout.setSpacing(0)

        # Coalesce the burst of resize/state events a maximise produces.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh)
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._refresh)

        self._esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc_shortcut.activated.connect(self._request_close)

        self._host.installEventFilter(self)

    # -- lifecycle ---------------------------------------------------------

    def show_overlay(self):
        """Show, size, focus and (optionally) guard the overlay."""
        self.show()  # showEvent sizes it against the host
        if self.blocks_host_input:
            self._install_input_guard()
        self.setFocus()
        self.bring_to_front()
        return self

    def close_popup(self):
        """Hide the popup, drop popup state and return focus to the host."""
        if not self.isVisible() and not self._input_guard_installed:
            return
        self.logger.debug("closing %s", self.log_name)
        source = self._source_widget()
        try:
            self._remove_input_guard()
            self._on_close()
            self._backdrop_pressed = False
            self.clearFocus()
            self.hide()
            self.repaint()
            self._host.repaint()
            self._host.setFocus()
            self._host.activateWindow()
        finally:
            self._input_guard_installed = False
        if source is not None:
            self.clear_stale_input_state(source)

    def _request_close(self):
        """Defer closing so it never happens inside the event being handled."""
        QTimer.singleShot(0, self.close_popup)

    def _on_close(self):
        """Hook: drop popup-specific data (content, request ids, ...)."""

    def _source_widget(self) -> QWidget | None:
        """Hook: widget whose hover state should be cleared on close."""
        return None

    # -- geometry ----------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._update_geometry()
        self.bring_to_front()
        # Re-run after the layout settles so the panel centres correctly.
        self._refresh_timer.start(0)

    def _update_geometry(self):
        if not self.isVisible():
            return
        rect = self._host.rect()
        old_geometry = self.geometry()
        self.setGeometry(rect)
        if old_geometry != rect:
            self.logger.debug("overlay geometry: %s -> %s", old_geometry, rect)

        width = min(
            self.max_width,
            max(self.min_width, int(rect.width() * self.width_ratio)),
            max(self.hard_min_width, rect.width() - self.margin),
        )
        height = min(
            self.max_height,
            max(self.min_height, int(rect.height() * self.height_ratio)),
            max(self.hard_min_height, rect.height() - self.margin),
        )
        self.panel.setGeometry(
            (rect.width() - width) // 2,
            (rect.height() - height) // 2,
            width,
            height,
        )
        self._on_geometry_changed(width, height)
        self.update()
        self.panel.update()

    def _on_geometry_changed(self, width: int, height: int):
        """Hook: adapt popup columns to the panel size."""

    def _refresh(self):
        if not self.isVisible():
            return
        self._update_geometry()
        self.bring_to_front()

    def bring_to_front(self):
        """Raise the overlay above its sibling widgets.

        Everything paints into the main-window backing store, so a QWidget
        level raise is enough.
        """
        if not self.isVisible():
            return
        self.raise_()
        self.panel.raise_()

    # -- host tracking / input guard --------------------------------------

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.WindowStateChange,
        ):
            if self.isVisible():
                self._update_geometry()
                self._refresh_timer.start(0)
                if event.type() == QEvent.Type.WindowStateChange:
                    self._settle_timer.start(80)
        elif self._should_block_input(obj, event):
            self.logger.debug(
                "blocked %s targeted at %r while overlay is open",
                event.type().name,
                obj,
            )
            return True
        return super().eventFilter(obj, event)

    @staticmethod
    def _is_inside(widget: QWidget | None, root: QWidget | None) -> bool:
        while widget is not None:
            if widget is root:
                return True
            widget = widget.parentWidget()
        return False

    def _should_block_input(self, obj, event) -> bool:
        if not self._input_guard_installed or not self.isVisible():
            return False
        if event.type() not in _BLOCKED_INPUT_EVENTS:
            return False
        if not isinstance(obj, QWidget):
            return False
        if self._is_inside(obj, self):
            return False
        return self._is_inside(obj, self._host)

    def _install_input_guard(self):
        app = QApplication.instance()
        if app is None or self._input_guard_installed:
            return
        app.installEventFilter(self)
        self._input_guard_installed = True
        self.logger.debug("installed modal input guard")

    def _remove_input_guard(self):
        app = QApplication.instance()
        if app is None or not self._input_guard_installed:
            return
        app.removeEventFilter(self)
        self._input_guard_installed = False
        self.logger.debug("removed modal input guard")

    def clear_stale_input_state(self, widget: QWidget | None):
        """Drop hover/pressed state a Wayland click may have left behind."""
        if widget is None:
            return
        from PySide6.QtWidgets import QAbstractButton

        was_hovered = widget.testAttribute(Qt.WidgetAttribute.WA_UnderMouse)
        was_down = isinstance(widget, QAbstractButton) and widget.isDown()
        if isinstance(widget, QAbstractButton):
            widget.setDown(False)
        widget.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
        QApplication.sendEvent(widget, QEvent(QEvent.Type.Leave))
        widget.update()
        self.logger.debug(
            "cleared stale hover on %r (hovered=%s down=%s)",
            widget,
            was_hovered,
            was_down,
        )

    # -- painting / backdrop ----------------------------------------------

    def paintEvent(self, event):
        """Paint the dimmed backdrop without relying on Wayland QSS support."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        super().paintEvent(event)

    def _is_backdrop(self, event) -> bool:
        global_pos = event.globalPosition().toPoint()
        return not self.panel.rect().contains(self.panel.mapFromGlobal(global_pos))

    def mousePressEvent(self, event):
        self._backdrop_pressed = self._is_backdrop(event)
        self.logger.debug(
            "overlay press backdrop=%s at %s",
            self._backdrop_pressed,
            event.position().toPoint(),
        )
        event.accept()

    def mouseReleaseEvent(self, event):
        backdrop = self._is_backdrop(event)
        self.logger.debug(
            "overlay release backdrop=%s pressed_on_backdrop=%s at %s",
            backdrop,
            self._backdrop_pressed,
            event.position().toPoint(),
        )
        if backdrop and self._backdrop_pressed:
            self._request_close()
        self._backdrop_pressed = False
        event.accept()
