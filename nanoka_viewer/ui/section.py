"""Game section widget for displaying characters grouped by game."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
)
from PySide6.QtCore import Qt, QEvent

from .card import CardWidget


class GameSection(QWidget):
    """Widget for displaying a section of characters for a single game."""

    def __init__(self, game_name, parent=None):
        """Initialize the game section widget."""
        super().__init__(parent)
        self._live_version = None
        self._latest_version = None

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

        # Container layout for version badges
        self.badges_layout = QHBoxLayout()
        self.badges_layout.setContentsMargins(8, 0, 0, 0)
        self.badges_layout.setSpacing(6)
        header_layout.addLayout(self.badges_layout)

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

    def set_versions(self, live_version, latest_version):
        """Set the live and beta version badges next to the title."""
        self._live_version = live_version
        self._latest_version = latest_version
        self._update_badges()

    def _update_badges(self):
        """Create/update badge widgets and apply style based on current theme."""
        # Clear existing badges
        while self.badges_layout.count():
            child = self.badges_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._live_version:
            return

        # Check if system theme is light or dark
        window_color = self.palette().color(self.backgroundRole())
        is_dark = window_color.value() < 128

        live_text = "#4CAF50" if is_dark else "#2E7D32"
        live_bg = "rgba(76, 175, 80, 0.15)" if is_dark else "rgba(46, 125, 50, 0.1)"
        live_border = "rgba(76, 175, 80, 0.3)" if is_dark else "rgba(46, 125, 50, 0.2)"

        beta_text = "#FF9800" if is_dark else "#D84315"
        beta_bg = "rgba(255, 152, 0, 0.15)" if is_dark else "rgba(216, 67, 21, 0.08)"
        beta_border = "rgba(255, 152, 0, 0.3)" if is_dark else "rgba(216, 67, 21, 0.2)"

        # Add Live badge
        live_badge = QLabel(f"Live v{self._live_version}")
        live_badge.setStyleSheet(f"""
            background-color: {live_bg};
            color: {live_text};
            border: 1px solid {live_border};
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: bold;
        """)
        self.badges_layout.addWidget(live_badge)

        # Add Beta badge
        if self._latest_version:
            display_version = self._latest_version.split("+")[0]
            beta_badge = QLabel(f"Beta v{display_version}")
            beta_badge.setStyleSheet(f"""
                background-color: {beta_bg};
                color: {beta_text};
                border: 1px solid {beta_border};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
            """)
            self.badges_layout.addWidget(beta_badge)

    def changeEvent(self, event):
        """Handle palette and theme changes."""
        if event.type() == QEvent.Type.PaletteChange:
            self._update_badges()
        super().changeEvent(event)
