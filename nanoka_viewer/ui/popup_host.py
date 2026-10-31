"""Full-size widget that hosts one popup's QML overlay.

Qt places and raises child widgets itself, so each popup keeps a thin
``QWidget`` that covers the central widget.  Everything the user sees and
interacts with -- the dimmed backdrop, the centred rounded panel, Escape,
click-outside-to-close and blocking input to the window underneath -- lives in
``qml/Overlay.qml``.  This module only keeps the widget plumbing Qt requires:
sizing against the host, raising, focus and dropping stale hover state.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QRect, Qt, QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from .qml_host import create_qml_widget

logger = logging.getLogger(__name__)

# Events that must never reach the host content while a modal overlay is open.
# The QML backdrop already swallows pointer input over the covered area; this
# guard is the safety net for the native-subsurface stacking case, where a
# host surface can end up painted above the popup and receive events directly.
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


class PopupHost(QWidget):
    """Child widget that shows one ``qml/Overlay.qml`` tree over the host.

    Subclasses set :attr:`source` and the panel sizing attributes, build their
    view model, then call :meth:`_create_view` with the context properties the
    QML tree needs.
    """

    overlay_object_name = "overlay"
    log_name = "overlay"
    logger = logger

    #: Whether input aimed at the host content is dropped while open.
    blocks_host_input = False

    #: QML source, relative to the QML directory.
    source = ""

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
        self._qml = None
        self._input_guard_installed = False

        self.setObjectName(self.overlay_object_name)
        # The QML tree paints the backdrop and the panel; the widget and the
        # view must both stay transparent so the window shows through.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Coalesce the burst of resize/state events a maximise produces.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh)
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._refresh)

        self._host.installEventFilter(self)

    # -- content -----------------------------------------------------------

    def _create_view(self, context_properties, image_providers=None):
        """Load :attr:`source` and wire the shell's sizing and close signal."""
        self._qml = create_qml_widget(
            self,
            dict(context_properties or {}),
            source=self.source,
            image_providers=image_providers,
            translucent=True,
        )
        self.layout().addWidget(self._qml, 1)

        root = self._qml.rootObject()
        root.setProperty("panelWidthRatio", float(self.width_ratio))
        root.setProperty("minPanelWidth", int(self.min_width))
        root.setProperty("maxPanelWidth", int(self.max_width))
        root.setProperty("hardMinPanelWidth", int(self.hard_min_width))
        root.setProperty("panelHeightRatio", float(self.height_ratio))
        root.setProperty("minPanelHeight", int(self.min_height))
        root.setProperty("maxPanelHeight", int(self.max_height))
        root.setProperty("hardMinPanelHeight", int(self.hard_min_height))
        root.setProperty("edgeMargin", int(self.margin))
        root.closeRequested.connect(self._request_close)
        return self._qml

    def panel_rect(self) -> QRect:
        """Return the QML panel's geometry in this widget's coordinates."""
        if self._qml is None:
            return QRect()
        rect = self._qml.rootObject().property("panelGeometry")
        if rect is None:
            return QRect()
        return QRect(
            round(rect.x()),
            round(rect.y()),
            round(rect.width()),
            round(rect.height()),
        )

    # -- lifecycle ---------------------------------------------------------

    def show_overlay(self):
        """Show, size and focus the overlay."""
        self.show()  # showEvent sizes it against the host
        if self.blocks_host_input:
            self._install_input_guard()
        self.setFocus()
        if self._qml is not None:
            self._qml.setFocus()
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
            self.clearFocus()
            self.hide()
            self._host.setFocus()
            self._host.activateWindow()
        finally:
            self._input_guard_installed = False
        if source is not None:
            self.clear_stale_input_state(source)

    def _request_close(self):
        """Defer closing so it never happens inside the event being handled."""
        self.logger.debug("close requested for %s", self.log_name)
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

    # -- host tracking -----------------------------------------------------

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

    # -- stale input -------------------------------------------------------

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
