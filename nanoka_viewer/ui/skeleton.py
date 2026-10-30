"""Reusable placeholder widgets for loading states.

The main card grid is QML now (its placeholders live in
``nanoka_viewer/qml/CharacterCard.qml``), and the details popup's skeletons
live in ``nanoka_viewer/qml/details``; these widgets are what the settings
popup still uses:

* :class:`SkeletonBlock` paints a rounded block using the widget's palette, so
  it follows the system theme without a second stylesheet.
* :class:`SkeletonPulse` animates the *alpha the skeletons paint with*.  It
  deliberately does not use ``QGraphicsOpacityEffect``: an effect rerenders a
  whole widget subtree through a pixmap, which interacts badly with fractional
  display scaling and can make content look compressed or misaligned.

Pulses are parented to the widget they animate, so deleting a skeleton also
stops its animation.
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
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QSizePolicy, QWidget

PULSE_DURATION_MS = 1800
PULSE_LOW_OPACITY = 0.55
PULSE_HIGH_OPACITY = 0.95


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
    if isinstance(widget, SkeletonBlock):
        targets.append(widget)
    targets.extend(widget.findChildren(SkeletonBlock))
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
