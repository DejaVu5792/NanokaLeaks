"""Reusable placeholder widgets for loading states.

A loading placeholder must occupy exactly the footprint of the content it
replaces, otherwise the real content visibly snaps into position when it
arrives.  The helpers here keep that contract in one place:

* :class:`SkeletonBlock` paints a rounded block using the widget's palette, so
  it follows the system theme without a second stylesheet.
* :class:`SkeletonPulse` animates the *alpha the skeletons paint with*.  It
  deliberately does not use ``QGraphicsOpacityEffect``: an effect rerenders a
  whole widget subtree through a pixmap, which interacts badly with fractional
  display scaling and can make a card row look compressed or misaligned.
* :class:`SkeletonThumbnail` owns the whole lifecycle of an image placeholder:
  it pulses until the pixmap arrives, then cross-fades into the image while
  clipping both to the same rounded shape.

Pulses are parented to the widget they animate, so deleting a skeleton (for
example when the details popup is cleared) also stops its animation.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    Property,
    QRectF,
    Qt,
    QVariantAnimation,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

PULSE_DURATION_MS = 1800
PULSE_LOW_OPACITY = 0.55
PULSE_HIGH_OPACITY = 0.95
REVEAL_DURATION_MS = 180


def skeleton_color(palette: QPalette) -> QColor:
    """Return the fill colour for skeleton blocks in *palette*.

    A 50/50 blend of ``Midlight`` and ``Mid`` stays visible against both
    ``Base`` and ``AlternateBase`` in light and dark themes.  ``Midlight``
    alone is nearly identical to the dark KDE / Catppuccin surfaces, while
    ``Mid`` alone makes large placeholders (the artwork column) too loud.
    """
    midlight = palette.color(QPalette.ColorRole.Midlight)
    mid = palette.color(QPalette.ColorRole.Mid)
    return QColor(
        (midlight.red() + mid.red()) // 2,
        (midlight.green() + mid.green()) // 2,
        (midlight.blue() + mid.blue()) // 2,
    )


class SkeletonPulse(QObject):
    """Animate the alpha of one or more skeleton widgets.

    Targets must expose an integer ``pulseAlpha`` Qt property (0-255).  The
    animation runs on the GUI thread and never reparents or rerenders a widget
    subtree, so skeletons cannot disturb the layout around them.
    """

    def __init__(
        self,
        targets: list[QWidget],
        *,
        low: int = int(PULSE_LOW_OPACITY * 255),
        high: int = int(PULSE_HIGH_OPACITY * 255),
        duration: int = PULSE_DURATION_MS,
        parent: QObject | None = None,
    ):
        super().__init__(parent or targets[0])
        self._targets = [target for target in targets if target is not None]
        self._low = low
        self._high = high
        self._stopped = False

        self._animation = QVariantAnimation(self)
        self._animation.setDuration(duration)
        self._animation.setStartValue(low)
        self._animation.setEndValue(low)
        self._animation.setKeyValueAt(0.0, low)
        self._animation.setKeyValueAt(0.5, high)
        self._animation.setKeyValueAt(1.0, low)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._animation.setLoopCount(-1)
        self._animation.valueChanged.connect(self._apply)

    @property
    def stopped(self) -> bool:
        """Whether :meth:`stop` has already run."""
        return self._stopped

    def _apply(self, value):
        for target in self._targets:
            try:
                target.setProperty("pulseAlpha", int(value))
            except RuntimeError:
                continue

    def start(self):
        """Start (or resume) the pulse."""
        if not self._stopped:
            self._apply(self._low)
            self._animation.start()

    def stop(self):
        """Stop the pulse and leave every target at full opacity."""
        if self._stopped:
            return
        self._stopped = True
        self._animation.stop()
        for target in self._targets:
            try:
                target.setProperty("pulseAlpha", 255)
            except RuntimeError:
                continue


def _skeleton_targets(widget: QWidget) -> list[QWidget]:
    """Return every skeleton inside *widget* (including the widget itself)."""
    targets = []
    if isinstance(widget, (SkeletonBlock, SkeletonThumbnail)):
        targets.append(widget)
    for kind in (SkeletonBlock, SkeletonThumbnail):
        targets.extend(widget.findChildren(kind))
    return targets


def start_pulse(widget: QWidget) -> SkeletonPulse | None:
    """Start a pulse on *widget*'s skeletons, reusing the one it already owns."""
    pulse = getattr(widget, "_skeleton_pulse", None)
    if isinstance(pulse, SkeletonPulse):
        try:
            stopped = pulse.stopped
        except RuntimeError:
            stopped = True
    else:
        stopped = True

    if stopped:
        targets = _skeleton_targets(widget)
        if not targets:
            return None
        pulse = SkeletonPulse(targets, parent=widget)
        widget._skeleton_pulse = pulse
    pulse.start()
    return pulse


def stop_pulse(widget: QWidget):
    """Stop *widget*'s pulse, if it has one."""
    pulse = getattr(widget, "_skeleton_pulse", None)
    if isinstance(pulse, SkeletonPulse):
        try:
            pulse.stop()
        except RuntimeError:
            pass


class SkeletonBlock(QWidget):
    """A plain rounded block used for text lines, icons and artwork."""

    def __init__(
        self,
        radius: float = 4.0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._radius = float(radius)
        self._pulse_alpha = 255
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def _get_pulse_alpha(self) -> int:
        return self._pulse_alpha

    def _set_pulse_alpha(self, value: int):
        self._pulse_alpha = max(0, min(255, int(value)))
        self.update()

    pulseAlpha = Property(int, _get_pulse_alpha, _set_pulse_alpha)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        color = skeleton_color(self.palette())
        color.setAlpha(self._pulse_alpha)
        painter.setBrush(color)

        rect = QRectF(self.rect())
        painter.drawRoundedRect(rect, self._radius, self._radius)


class SkeletonThumbnail(QWidget):
    """Image placeholder that keeps the final thumbnail's exact geometry.

    The skeleton is painted in the same rectangle the image will occupy, and
    the image is clipped to the same rounded shape.  Both states therefore
    line up pixel-for-pixel; only the content changes.
    """

    def __init__(
        self,
        width: int,
        height: int,
        radius: float = 8.0,
        *,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._radius = float(radius)
        self._pixmap: QPixmap | None = None
        self._failed = False
        self._pulse_alpha = 255
        self._image_opacity = 1.0
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._fade = QVariantAnimation(self)
        self._fade.setDuration(REVEAL_DURATION_MS)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.valueChanged.connect(self._set_image_opacity)

        start_pulse(self)

    def _get_pulse_alpha(self) -> int:
        return self._pulse_alpha

    def _set_pulse_alpha(self, value: int):
        self._pulse_alpha = max(0, min(255, int(value)))
        self.update()

    pulseAlpha = Property(int, _get_pulse_alpha, _set_pulse_alpha)

    def _set_image_opacity(self, value: float):
        self._image_opacity = float(value)
        self.update()

    @property
    def has_image(self) -> bool:
        """Whether a successfully decoded image is displayed."""
        return self._pixmap is not None and not self._failed

    def set_image(self, pixmap: QPixmap | None):
        """Show *pixmap*, cross-fading from the skeleton when visible."""
        if pixmap is None or pixmap.isNull():
            self.set_failed()
            return

        stop_pulse(self)
        self._pixmap = pixmap
        self._failed = False
        self._fade.stop()

        if self.isVisible():
            self._image_opacity = 0.0
            self._fade.start()
        else:
            self._image_opacity = 1.0
        self.update()

    def set_failed(self):
        """Stop loading and show a subdued unavailable-image placeholder."""
        stop_pulse(self)
        self._fade.stop()
        self._pixmap = None
        self._failed = True
        self._image_opacity = 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.setClipPath(path)

        skeleton_alpha = 1.0
        if self._pixmap is not None:
            skeleton_alpha = 1.0 - self._image_opacity

        if skeleton_alpha > 0.0:
            color = skeleton_color(self.palette())
            color.setAlpha(int(self._pulse_alpha * skeleton_alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, self._radius, self._radius)

        if self._pixmap is not None:
            painter.setOpacity(self._image_opacity)
            painter.drawPixmap(0, 0, self._pixmap)

        if self._failed:
            self._paint_unavailable(painter, rect)

    def _paint_unavailable(self, painter: QPainter, rect: QRectF):
        """Draw a quiet dash so a failed thumbnail is not mistaken for loading."""
        color = QColor(self.palette().color(QPalette.ColorRole.PlaceholderText))
        color.setAlphaF(0.7)
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        centre = rect.center()
        painter.drawLine(
            centre.x() - 6.0, centre.y(), centre.x() + 6.0, centre.y()
        )
