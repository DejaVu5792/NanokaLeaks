"""Main application window for Nanoka Viewer."""

import sys
import time
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import QEvent, QTimer, Qt

from .styles import STYLESHEET
from .section import GameSection
from .loader import LoadThread
from ..api import get_name, GAMES

logger = logging.getLogger(__name__)

PALETTE_CHANGE_EVENT = QEvent.Type.PaletteChange


class NanokaViewer(QMainWindow):
    """Main application window for viewing Nanoka character data."""

    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        logger.info("Initializing NanokaViewer...")
        init_start = time.time()

        self.setWindowTitle("Nanoka Viewer")
        self.setMinimumSize(800, 600)
        self.resize(950, 750)
        self._updating_theme = False
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Nanoka Viewer")
        title.setStyleSheet("font-weight: 600; font-size: 22px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: palette(placeholderText);")
        header_layout.addWidget(self.status_label)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load_data)
        header_layout.addWidget(self.refresh_btn)

        root_layout.addWidget(header_widget)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(self.content_widget)
        root_layout.addWidget(scroll_area)

        self.game_sections = {}
        self._loading_chars = {}
        self._loading_index = {}
        games_list = list(GAMES.items())
        for i, (game, info) in enumerate(games_list):
            section = GameSection(info["name"])
            self.content_layout.addWidget(section)
            self.game_sections[game] = section

            if i < len(games_list) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFixedHeight(1)
                separator.setStyleSheet("background: palette(mid); border: none;")
                self.content_layout.addWidget(separator)

        self.load_thread = None

        init_elapsed = time.time() - init_start
        logger.info(f"GUI initialized in {init_elapsed:.3f}s")
        self.load_data()

    def load_data(self):
        """Start loading character data."""
        logger.info("Starting data load...")
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Loading...")

        for section in self.game_sections.values():
            section.clear_cards()
            section.set_status("Loading...")

        self.load_thread = LoadThread()
        self.load_thread.game_loaded.connect(self.on_game_loaded)
        self.load_thread.load_finished.connect(self.on_load_finished)
        self.load_thread.start()

    def on_game_loaded(self, game, chars):
        """Handle when a game's character data is loaded."""
        section = self.game_sections.get(game)
        if not section:
            return

        section.clear_cards()

        if not chars:
            section.set_status("Failed to load characters")
            return

        # Store characters for progressive loading
        self._loading_chars[game] = list(chars)
        self._loading_index[game] = 0

        # Start progressive loading
        section.set_status(f"Loading 0/{len(chars)}")
        self._load_next_batch(game, chars)

    def on_load_finished(self):
        """Handle when all data loading is complete."""
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Loaded at {datetime.now().strftime('%H:%M:%S')}")
        logger.info("Load finished")

    def _load_next_batch(self, game, chars):
        """Load the next batch of character cards."""
        # Load cards in batches. Since image loading is async, we can load more at once.
        batch_size = 10
        start_idx = self._loading_index[game]
        end_idx = min(start_idx + batch_size, len(chars))

        # Add cards for this batch
        batch_chars = chars[start_idx:end_idx]
        for char_id, char_data, is_new in batch_chars:
            self.game_sections[game].add_card(game, char_id, char_data, is_new)

        # Update progress
        self._loading_index[game] = end_idx
        # Update status less frequently to reduce overhead
        if end_idx % 20 == 0 or end_idx == len(chars):
            self.game_sections[game].set_status(f"Loading {end_idx}/{len(chars)}")

        # Continue loading if there are more cards with a minimal delay
        if end_idx < len(chars):
            # Use a very short delay to yield control back to the event loop
            QTimer.singleShot(
                5, lambda: self._load_next_batch(game, chars)
            )  # 5ms delay
        else:
            # Loading complete
            self.game_sections[game].set_status(f"{len(chars)} total")
            logger.info(f"Finished loading all {len(chars)} characters for {game}")

    def changeEvent(self, event):
        """Handle theme change events."""
        if event.type() == PALETTE_CHANGE_EVENT and not self._updating_theme:
            self._updating_theme = True
            self.setStyleSheet(STYLESHEET)
            self._updating_theme = False
        super().changeEvent(event)


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = NanokaViewer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
