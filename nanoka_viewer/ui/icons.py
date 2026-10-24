"""Small helpers for icon-only buttons."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon


def apply_icon_or_text(button, theme_names, fallback_text, size=16):
    """Set a themed icon on *button*, falling back to a text glyph."""
    for name in theme_names:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            button.setIcon(icon)
            button.setIconSize(QSize(size, size))
            return
    button.setText(fallback_text)
