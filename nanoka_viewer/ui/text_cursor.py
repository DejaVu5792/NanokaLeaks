"""Show text cursors over QML ``SelectableText`` inside a ``QQuickWidget``.

Qt Quick resolves cursors against its window: ``MouseArea.cursorShape``,
``HoverHandler`` and ``TextEdit``'s own I-beam all end up on the offscreen
``QQuickWindow`` that a ``QQuickWidget`` renders through.  ``QQuickWidget``
never forwards that cursor to the widget, so none of those QML cursor shapes
are visible in this application.

This filter does the hit testing on the widget instead: when the pointer moves
without a button pressed it finds the ``SelectableText`` under the cursor and
sets the widget cursor directly -- an I-beam over glyphs, a pointing hand over
rule-term links, and the normal arrow over blank space (where a drag scrolls
the details pane).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QCursor
from PySide6.QtQuick import QQuickItem
from PySide6.QtWidgets import QWidget


class SelectableTextCursor(QObject):
    """Keep *widget*'s cursor in sync with the ``SelectableText`` under it."""

    def __init__(self, widget: QWidget) -> None:
        super().__init__(widget)
        self._widget = widget
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is not self._widget:
            return False

        kind = event.type()
        if kind == QEvent.Type.Leave:
            self._widget.unsetCursor()
        elif kind == QEvent.Type.Enter:
            self._apply(QPointF(self._widget.mapFromGlobal(QCursor.pos())))
        elif kind in (
            QEvent.Type.MouseMove,
            QEvent.Type.HoverMove,
            QEvent.Type.HoverEnter,
        ):
            # Dragging text should keep the cursor it started with.
            if kind == QEvent.Type.MouseMove and event.buttons():
                return False
            self._apply(event.position())
        return False

    def _apply(self, position: QPointF) -> None:
        root = self._widget.rootObject()
        shape = Qt.CursorShape.ArrowCursor
        if isinstance(root, QQuickItem):
            hit = _text_item_at(root, position)
            if hit is not None:
                item, local = hit
                if item.pointIsOnText(local.x(), local.y()):
                    link = item.linkAt(local.x(), local.y()) or ""
                    shape = (
                        Qt.CursorShape.PointingHandCursor
                        if link.startswith("term:")
                        else Qt.CursorShape.IBeamCursor
                    )
        if self._widget.cursor().shape() != shape:
            self._widget.setCursor(QCursor(shape))


def _text_item_at(
    item: QQuickItem, position: QPointF
) -> tuple[QQuickItem, QPointF] | None:
    """Return the topmost ``SelectableText`` containing *position*, if any.

    Child items paint above their parents, so they are tested first.
    """
    if not item.isVisible():
        return None

    for child in reversed(item.childItems()):
        hit = _text_item_at(child, position)
        if hit is not None:
            return hit

    if not hasattr(item, "pointIsOnText"):
        return None
    local = item.mapFromScene(position)
    if 0 <= local.x() < item.width() and 0 <= local.y() < item.height():
        return item, local
    return None
