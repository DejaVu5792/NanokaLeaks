"""In-window settings popup."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
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
from .overlay import OverlayPopup, is_alive

logger = logging.getLogger(__name__)


class SettingsPopup(OverlayPopup):
    """Lightbox-style settings overlay."""

    overlay_object_name = "settingsOverlay"
    panel_object_name = "settingsPanel"
    log_name = "settings popup"
    logger = logging.getLogger(__name__)

    width_ratio = 0.42
    min_width = 320
    max_width = 460
    hard_min_width = 280
    height_ratio = 0.45
    min_height = 260
    max_height = 360
    hard_min_height = 220
    margin = 32

    def __init__(self, host):
        super().__init__(host)
        panel_layout = self.panel_layout

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

    def open_popup(self):
        settings = load_settings()
        self.cache_details.setChecked(
            bool(settings.get("cache_character_details", True))
        )
        self.cache_artwork.setChecked(
            bool(settings.get("cache_character_artwork", True))
        )
        self.cache_builds.setChecked(
            bool(settings.get("cache_character_builds", True))
        )
        self.show_overlay()

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


def open_settings(parent):
    """Show the shared settings popup."""
    global _settings_popup
    if parent is None:
        return None
    if isinstance(parent, QMainWindow):
        host = parent.centralWidget() or parent
    else:
        host = parent

    if _settings_popup is not None and not is_alive(_settings_popup):
        _settings_popup = None
    if _settings_popup is not None and _settings_popup._host is not host:
        _settings_popup.close_popup()
        _settings_popup = None
    if _settings_popup is None:
        _settings_popup = SettingsPopup(host)

    _settings_popup.open_popup()
    return _settings_popup


_settings_popup = None