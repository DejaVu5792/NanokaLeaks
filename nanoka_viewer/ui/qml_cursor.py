"""Resolve Qt Quick cursor shapes on the widget side.

``QQuickWidget`` renders its tree through an offscreen ``QQuickWindow`` and
never forwards the cursor set in QML to the widget, so ``MouseArea.cursorShape``,
``HoverHandler`` and ``TextEdit``'s own I-beam have no visible effect.

This filter walks the item tree under the pointer and applies the cursor QML
would have used: an I-beam over selectable glyphs, a pointing hand over
rule-term links, and whatever ``cursorShape`` a ``MouseArea`` declares (the
artwork uses the open/closed hand to advertise that it can be dragged).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QTimer, Qt
from PySide6.QtGui import QCursor
from PySide6.QtQuick import QQuickItem
from PySide6.QtWidgets import QWidget

_MOUSE_EVENTS = frozenset(
    {
        QEvent.Type.MouseMove,
        QEvent.Type.HoverMove,
        QEvent.Type.HoverEnter,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.MouseButtonRelease,
    }
)


class QmlCursorTracker(QObject):
    """Keep *widget*'s cursor in sync with the QML items under it."""

    def __init__(self, widget: QWidget) -> None:
        super().__init__(widget)
        self._widget = widget
        self._position: QPointF | None = None
        # Resolve after QML has handled the event: pressing the artwork flips
        # its ``pressed`` property and must show the closed hand, and releasing
        # must drop it again.  Hover moves coalesce into one lookup per cycle.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._apply_pending)
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is not self._widget:
            return False

        kind = event.type()
        if kind == QEvent.Type.Leave:
            self._timer.stop()
            self._position = None
            self._widget.unsetCursor()
        elif kind == QEvent.Type.Enter:
            self._queue(QPointF(self._widget.mapFromGlobal(QCursor.pos())))
        elif kind in _MOUSE_EVENTS:
            self._queue(QPointF(event.position()))
        return False

    def _queue(self, position: QPointF) -> None:
        self._position = position
        if not self._timer.isActive():
            self._timer.start()

    def _apply_pending(self) -> None:
        position, self._position = self._position, None
        if position is not None:
            self._apply(position)

    def _apply(self, position: QPointF) -> None:
        root = self._widget.rootObject()
        shape = Qt.CursorShape.ArrowCursor
        if isinstance(root, QQuickItem):
            declared = _cursor_at(root, position)
            if declared is not None:
                shape = declared
        if self._widget.cursor().shape() != shape:
            self._widget.setCursor(QCursor(shape))


def _cursor_at(
    item: QQuickItem, position: QPointF
) -> Qt.CursorShape | None:
    """Return the cursor *item* declares at *position*, if any.

    Child items paint above their parents, so they are tested first.  ``None``
    means "nothing here", which lets the caller try the items behind.
    """
    if not item.isVisible():
        return None

    for child in reversed(item.childItems()):
        shape = _cursor_at(child, position)
        if shape is not None:
            return shape

    local = item.mapFromScene(position)
    if not (0 <= local.x() < item.width() and 0 <= local.y() < item.height()):
        return None
    return _shape_for(item, local)


def _shape_for(item: QQuickItem, local: QPointF) -> Qt.CursorShape | None:
    if hasattr(item, "pointIsOnText"):
        if not item.pointIsOnText(local.x(), local.y()):
            return None
        link = item.linkAt(local.x(), local.y()) or ""
        if link.startswith("term:"):
            return Qt.CursorShape.PointingHandCursor
        return Qt.CursorShape.IBeamCursor
    return _declared_cursor(item)


def _declared_cursor(item: QQuickItem) -> Qt.CursorShape | None:
    """Return the non-default ``cursorShape`` an item (a ``MouseArea``) sets."""
    if not item.isEnabled():
        return None
    meta = item.metaObject()
    index = meta.indexOfProperty("cursorShape")
    if index < 0:
        return None
    shape = meta.property(index).read(item)
    if shape is None or shape == Qt.CursorShape.ArrowCursor:
        return None
    return shape
