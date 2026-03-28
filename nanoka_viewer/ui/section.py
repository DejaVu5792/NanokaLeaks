"""Game section widget for displaying characters grouped by game."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
)
from PySide6.QtCore import Qt

from .card import CardWidget


class GameSection(QWidget):
    """Widget for displaying a section of characters for a single game."""

    def __init__(self, game_name, parent=None):
        """Initialize the game section widget."""
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 8, 0, 8)
        main_layout.setSpacing(4)

        header = QWidget()
        header.setObjectName("gameHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)

        title_label = QLabel(game_name)
        title_label.setStyleSheet("font-weight: 600; font-size: 15px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet(
            "font-size: 12px; color: palette(placeholderText);"
        )
        header_layout.addWidget(self.status_label)

        main_layout.addWidget(header)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFixedHeight(230)

        self.cards_container = QWidget()
        self.cards_layout = QHBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(4, 0, 4, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(scroll_area)

    def clear_cards(self):
        """Remove all cards from the section."""
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def add_card(self, game, char_id, char_data, is_new=False):
        """Add a character card to the section."""
        card = CardWidget(game, char_id, char_data, is_new)
        self.cards_layout.addWidget(card)

    def set_status(self, text):
        """Set the status text for the section."""
        self.status_label.setText(text)

    def set_progress(self, loaded, total):
        """Set the progress text for the section."""
        if loaded < total:
            self.status_label.setText(f"{loaded}/{total} loaded")
        else:
            self.status_label.setText(f"{total} total")
