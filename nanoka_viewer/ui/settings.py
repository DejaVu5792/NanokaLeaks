"""In-window settings popup."""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..api import clear_cache
from ..settings import load_settings, save_settings
from .image_loader import clear_image_cache

logger = logging.getLogger(__name__)


class SettingsPopup(QWidget):
    """Lightbox-style settings overlay."""

    def __init__(self, host):
        super().__init__(host)
        self._host = host
        self._input_guard_installed = False

        self.setObjectName("settingsOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

        self.panel = QFrame(self)
        self.panel.setObjectName("settingsPanel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("settingsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 12, 10)
        header_layout.setSpacing(10)

        title = QLabel("Settings")
        title.setObjectName("settingsTitle")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_popup)
        header_layout.addWidget(close_btn)

        panel_layout.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.setSpacing(14)

        cache_label = QLabel("Caching")
        cache_label.setObjectName("settingsSectionTitle")
        body_layout.addWidget(cache_label)

        self.cache_details = QCheckBox("Cache character details")
        self.cache_artwork = QCheckBox("Cache character details artwork")
        self.cache_builds = QCheckBox("Cache character builds")
        for checkbox in (self.cache_details, self.cache_artwork, self.cache_builds):
            checkbox.toggled.connect(self._save_and_apply)
            body_layout.addWidget(checkbox)

        body_layout.addSpacing(8)

        self.clear_cache_btn = QPushButton("Clear cache")
        self.clear_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        body_layout.addWidget(self.clear_cache_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        body_layout.addStretch(1)
        panel_layout.addWidget(body, 1)

        self._esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc_shortcut.activated.connect(self.close_popup)

        self._host.installEventFilter(self)

    def open_popup(self):
        settings = load_settings()
        self.cache_details.setChecked(bool(settings.get("cache_character_details", True)))
        self.cache_artwork.setChecked(bool(settings.get("cache_character_artwork", True)))
        self.cache_builds.setChecked(bool(settings.get("cache_character_builds", True)))
        self._update_geometry()
        self.show()
        self.raise_()
        self.panel.raise_()
        if self.windowHandle() is not None:
            self.windowHandle().raise_()
        self.setFocus()
        self.bring_to_front()

    def bring_to_front(self):
        if not self.isVisible():
            return
        self.raise_()
        self.panel.raise_()
        handle = self.windowHandle()
        if handle is not None:
            handle.raise_()

    def close_popup(self):
        self.hide()
        self._host.setFocus()
        self._host.activateWindow()

    def _save_and_apply(self):
        settings = {
            "cache_character_details": self.cache_details.isChecked(),
            "cache_character_artwork": self.cache_artwork.isChecked(),
            "cache_character_builds": self.cache_builds.isChecked(),
        }
        save_settings(settings)

    def _clear_cache(self):
        clear_cache()
        clear_image_cache()
        self.clear_cache_btn.setEnabled(False)
        self.clear_cache_btn.setText("Cleared")
        QTimer.singleShot(1500, self._reset_clear_button)

    def _reset_clear_button(self):
        self.clear_cache_btn.setEnabled(True)
        self.clear_cache_btn.setText("Clear cache")

    def _update_geometry(self):
        rect = self._host.rect()
        self.setGeometry(rect)

        width = min(
            460,
            max(320, int(rect.width() * 0.42)),
            max(280, rect.width() - 32),
        )
        height = min(
            360,
            max(260, int(rect.height() * 0.45)),
            max(220, rect.height() - 32),
        )
        self.panel.setGeometry(
            (rect.width() - width) // 2,
            (rect.height() - height) // 2,
            width,
            height,
        )
        self.raise_()
        self.panel.raise_()
        if self.windowHandle() is not None:
            self.windowHandle().raise_()
        self.update()
        self.panel.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        super().paintEvent(event)

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.WindowStateChange,
        ):
            self._update_geometry()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.close_popup()
        super().mousePressEvent(event)


def open_settings(parent):
    """Show the shared settings popup."""
    global _settings_popup
    if parent is None:
        return None
    if isinstance(parent, QMainWindow):
        host = parent.centralWidget() or parent
    else:
        host = parent

    if _settings_popup is not None and _settings_popup._host is not host:
        _settings_popup.close_popup()
        _settings_popup = None
    if _settings_popup is None:
        _settings_popup = SettingsPopup(host)

    _settings_popup.open_popup()
    return _settings_popup


_settings_popup = None