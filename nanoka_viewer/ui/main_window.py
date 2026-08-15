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
from PySide6.QtCore import QEvent, QTimer, Qt, QObject

from .styles import STYLESHEET
from .section import GameSection
from .loader import LoadThread
from .image_loader import clear_image_cache
from ..api import get_name, GAMES, clear_cache, fetch_manifest

logger = logging.getLogger(__name__)

PALETTE_CHANGE_EVENT = QEvent.Type.PaletteChange


class ShiftEventFilter(QObject):
    """Event filter to capture Shift key events globally in the application."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Shift:
                if not event.isAutoRepeat():
                    self.window._shift_held = True
                    self.window._update_refresh_button_text()
        elif event.type() == QEvent.Type.KeyRelease:
            if event.key() == Qt.Key.Key_Shift:
                if not event.isAutoRepeat():
                    self.window._shift_held = False
                    self.window._update_refresh_button_text()
        elif event.type() in (QEvent.Type.WindowDeactivate, QEvent.Type.FocusOut):
            self.window._shift_held = False
            self.window._update_refresh_button_text()
        elif event.type() in (QEvent.Type.WindowActivate, QEvent.Type.FocusIn):
            self.window._shift_held = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.window._update_refresh_button_text()
        return super().eventFilter(obj, event)


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

        self.refresh_btn = QPushButton("Reload")
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

        self._shift_held = False

        # Install global event filter to capture Shift key events instantly
        self.shift_filter = ShiftEventFilter(self)
        QApplication.instance().installEventFilter(self.shift_filter)

        init_elapsed = time.time() - init_start
        logger.info(f"GUI initialized in {init_elapsed:.3f}s")
        self.load_data()

    def _update_refresh_button_text(self):
        """Update the refresh button text based on keyboard modifiers."""
        if not self.refresh_btn.isEnabled():
            return

        if self._shift_held:
            if self.refresh_btn.text() != "Clear Cache and Reload":
                self.refresh_btn.setText("Clear Cache and Reload")
                self.refresh_btn.setToolTip("Clears manifest, character data, and image cache")
        else:
            if self.refresh_btn.text() != "Reload":
                self.refresh_btn.setText("Reload")
                self.refresh_btn.setToolTip("")

    def load_data(self):
        """Start loading character data."""
        # Check if Shift is held to clear cache
        if self._shift_held or (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier):
            logger.info("Shift key held during reload, clearing all caches...")
            self.status_label.setText("Clearing cache...")
            clear_cache()
            clear_image_cache()

        logger.info("Starting data load...")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Reload")  # Reset text while loading
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

        # Update version badges in the game section header
        try:
            manifest = fetch_manifest()
            game_info = manifest.get(game, {})
            live_version = game_info.get("live")
            latest_version = game_info.get("latest")
            section.set_versions(live_version, latest_version)
        except Exception as e:
            logger.error(f"Error fetching version for {game}: {e}")

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



def main(argv=None):
    """Main entry point for the application."""
    import argparse
    import cProfile
    import pstats
    from datetime import datetime

    parser = argparse.ArgumentParser(prog="NanokaLeaks", description="Nanoka Viewer")
    parser.add_argument(
        "--profiler",
        action="store_true",
        help="Profile the application with cProfile and print the results",
    )
    parser.add_argument(
        "--profiler-output",
        metavar="FILE",
        help="Where to save the cProfile stats (default: nanoka_profile.prof)",
    )
    args, remaining = parser.parse_known_args(argv)

    if args.profiler:
        profile_output = args.profiler_output or "nanoka_profile.prof"
        logger.info(f"Profiling enabled, saving stats to {profile_output}")
        profiler = cProfile.Profile()
        profiler.enable()

        try:
            return _run_app(remaining)
        finally:
            profiler.disable()
            profiler.dump_stats(profile_output)
            stats = pstats.Stats(profiler)
            stats.sort_stats("cumulative")
            print("\n=== Profile results (top 40 by cumulative time) ===")
            stats.print_stats(40)
            logger.info(f"Profile stats saved to {profile_output}")
    else:
        return _run_app(remaining)


def _run_app(argv):
    """Create and run the QApplication."""
    app = QApplication(argv if argv else sys.argv)
    app.setStyle("Fusion")

    window = NanokaViewer()
    window.show()
    return app.exec()


if __name__ == "__main__":
    main()
