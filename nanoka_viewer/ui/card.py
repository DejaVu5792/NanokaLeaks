"""Character card widget for displaying character information."""

import webbrowser

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt

from .image_loader import request_image
from ..api import (
    get_character_url,
    get_rarity,
    get_element,
    get_name,
    get_character_image,
    get_element_image,
    get_specialty_image,
)


class CardWidget(QWidget):
    """Widget for displaying a single character card."""

    def _get_specialty_name(self, game, char_data):
        """Get the specialty/path/weapon name for a character."""
        if game == "zzz":
            type_map = {
                1: "Attack",
                2: "Defense",
                3: "Anomaly",
                4: "Support",
                5: "Star",
            }
            return type_map.get(char_data.get("type", 1), "Attack")
        elif game == "hsr":
            return char_data.get("baseType", "Unknown")
        elif game == "gi":
            return char_data.get("weapon", "Unknown")
        return "Unknown"

    def __init__(self, game, char_id, char_data, is_new=False, parent=None):
        """Initialize the character card widget."""
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedSize(180, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        name = get_name(game, char_data, char_id)
        rarity = get_rarity(game, char_data)
        element = get_element(game, char_data)
        url = get_character_url(game, char_id, char_data)

        char_img_url = get_character_image(game, char_data, char_id)
        element_img_url = get_element_image(game, char_data)
        specialty_img_url = get_specialty_image(game, char_data)

        rarity_colors = {"S": "#FF6B6B", "5": "#FFD700", "4": "#9370DB", "A": "#FF6B6B"}
        rarity_color = rarity_colors.get(str(rarity), "palette(text)")

        rarity_label = QLabel(f"{rarity}\u2605")
        rarity_label.setStyleSheet(
            f"color: {rarity_color}; font-weight: bold; font-size: 11px;"
        )
        rarity_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(rarity_label)

        self.char_img_label = QLabel()
        self.char_img_label.setFixedSize(80, 80)
        self.char_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.char_img_label.setToolTip(name)
        self.char_img_label.setText("...")
        self.char_img_label.setStyleSheet("color: palette(placeholderText);")
        layout.addWidget(self.char_img_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        icons_widget = QWidget()
        icons_layout = QHBoxLayout(icons_widget)
        icons_layout.setContentsMargins(0, 0, 0, 0)
        icons_layout.setSpacing(8)
        icons_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.element_label = QLabel()
        self.element_label.setFixedSize(18, 18)
        self.element_label.setToolTip(element if element else "Unknown Element")
        self.element_label.setText(element[:1] if element else "?")
        self.element_label.setStyleSheet(
            "color: palette(placeholderText); font-size: 9px;"
        )
        icons_layout.addWidget(self.element_label)

        specialty_type = self._get_specialty_name(game, char_data)
        self.specialty_label = QLabel()
        self.specialty_label.setFixedSize(18, 18)
        self.specialty_label.setToolTip(specialty_type)
        self.specialty_label.setText("?")
        self.specialty_label.setStyleSheet(
            "color: palette(placeholderText); font-size: 9px;"
        )
        icons_layout.addWidget(self.specialty_label)

        layout.addWidget(icons_widget)

        display_name = name[:14] + ("..." if len(name) > 14 else "")
        name_label = QLabel(display_name)
        name_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(name_label)

        view_btn = QPushButton("View")
        view_btn.setObjectName("viewBtn")
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.clicked.connect(lambda checked=False, u=url: webbrowser.open(u))
        layout.addWidget(view_btn)

        layout.addStretch()

        # Add NEW badge overlay if character is new (top-left corner)
        if is_new:
            new_label = QLabel("NEW", self)
            new_label.setStyleSheet("""
                background-color: palette(highlight);
                color: palette(highlighted-text);
                border-radius: 3px;
                padding: 1px 3px;
                font-weight: bold;
                font-size: 8px;
            """)
            new_label.adjustSize()
            new_label.move(4, 4)
            new_label.raise_()

        # Request images asynchronously
        request_image(char_img_url, self._on_char_image_loaded, (80, 80))
        request_image(element_img_url, self._on_element_image_loaded, (18, 18))
        request_image(specialty_img_url, self._on_specialty_image_loaded, (18, 18))

    def _on_char_image_loaded(self, pixmap):
        """Update character image when loaded."""
        self.char_img_label.setText("")
        self.char_img_label.setPixmap(pixmap)

    def _on_element_image_loaded(self, pixmap):
        """Update element image when loaded."""
        self.element_label.setText("")
        self.element_label.setPixmap(pixmap)

    def _on_specialty_image_loaded(self, pixmap):
        """Update specialty image when loaded."""
        self.specialty_label.setText("")
        self.specialty_label.setPixmap(pixmap)
