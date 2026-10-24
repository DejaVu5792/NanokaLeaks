"""Icon button that distinguishes single and double clicks."""

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QApplication, QPushButton


class PulseButton(QPushButton):
    """Push button with separate single-click and double-click actions.

    The first click starts a short radar-like pulse and a timer. If no second
    click follows within the system double-click interval, *single_activated*
    is emitted. A second click within that window emits *activated* instead.
    """

    activated = Signal()
    single_activated = Signal()

    PULSE_MS = 450

    def __init__(self, parent=None):
        """Initialize the button and its click/pulse timers."""
        super().__init__(parent)
        self._click_count = 0
        self._pulse = None

        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.setInterval(QApplication.doubleClickInterval())
        self._reset_timer.timeout.connect(self._on_single_click)

        self._pulse_anim = QVariantAnimation(self)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setDuration(self.PULSE_MS)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pulse_anim.valueChanged.connect(self._on_pulse_value)

        self.clicked.connect(self._on_click)

    def _on_click(self):
        """Pulse on the first click, activate on the second click."""
        self._click_count += 1
        if self._click_count >= 2:
            self._reset_clicks()
            self.activated.emit()
            return

        self._pulse = 0.0
        self._pulse_anim.stop()
        self._pulse_anim.start()
        self._reset_timer.start()
        self.update()

    def _on_single_click(self):
        """Emit the single-click action once the double-click window expires."""
        self._reset_clicks()
        self.single_activated.emit()

    def _on_pulse_value(self, value):
        self._pulse = value
        self.update()

    def _reset_clicks(self):
        """Forget the pending click and remove the pulse."""
        self._reset_timer.stop()
        self._click_count = 0
        self._pulse_anim.stop()
        self._pulse = None
        self.update()

    def paintEvent(self, event):
        """Draw the button, then an expanding highlight ring while pulsing."""
        super().paintEvent(event)
        if self._pulse is None:
            return

        progress = self._pulse
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(self.palette().color(QPalette.ColorRole.Highlight))
        color.setAlphaF(max(0.0, 0.9 * (1.0 - progress)))

        inset = 1.0 + 6.0 * (1.0 - progress)
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)

        painter.setPen(QPen(color, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 4.0, 4.0)
