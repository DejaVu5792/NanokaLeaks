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
from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QCursor

from .styles import STYLESHEET
from .section import GameSection
from .loader import LoadThread
from .image_loader import clear_image_cache
from .settings import open_settings
from ..api import get_name, GAMES, clear_cache, fetch_manifest

logger = logging.getLogger(__name__)

PALETTE_CHANGE_EVENT = QEvent.Type.PaletteChange

_TRACED_MOUSE_EVENTS = frozenset(
    {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.MouseMove,
        QEvent.Type.Wheel,
        QEvent.Type.Enter,
        QEvent.Type.Leave,
        QEvent.Type.HoverEnter,
        QEvent.Type.HoverLeave,
        QEvent.Type.HoverMove,
    }
)


class _MouseTraceFilter(QObject):
    """Verbose widget-level mouse trace (enabled by NANOKA_TRACE_MOUSE=1).

    Qt's own ``qt.qpa.wayland.pointer`` logging is too noisy to keep on, but
    mouse routing problems (stale hover, a press landing on the widget
    underneath an overlay) need exactly that information.  This filter logs
    the receiver, its hover state and the current implicit grabber instead.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger("mouse.trace")

    def eventFilter(self, obj, event):
        if event.type() in _TRACED_MOUSE_EVENTS and isinstance(obj, QWidget):
            if event.type() == QEvent.Type.MouseMove:
                # Keep high-frequency motion readable: only log when the
                # receiver or its hover state actually changes.
                key = (obj, obj.underMouse())
                if key == getattr(self, "_last_move", None):
                    return False
                self._last_move = key
            self._logger.debug(
                "%-20s %-28s objectName=%r underMouse=%s down=%s "
                "grabber=%r cursor=%s",
                event.type().name,
                type(obj).__name__,
                obj.objectName(),
                obj.underMouse(),
                obj.isDown() if hasattr(obj, "isDown") else False,
                QWidget.mouseGrabber(),
                QCursor.pos(),
            )
        return False


def _install_mouse_trace(app):
    """Install the verbose mouse trace filter, keeping a reference alive."""
    if getattr(app, "_nanoka_mouse_trace", None) is not None:
        return
    app._nanoka_mouse_trace = _MouseTraceFilter(app)
    app.installEventFilter(app._nanoka_mouse_trace)
    logging.getLogger(__name__).debug(
        "Detailed widget-level mouse tracing enabled (NANOKA_TRACE_MOUSE)"
    )


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
        self.status_label.setStyleSheet("color: palette(placeholder-text);")
        header_layout.addWidget(self.status_label)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self._open_settings)
        header_layout.addWidget(self.settings_btn)

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

        # QtWebEngine makes its embedding window native on first use. If the
        # top-level window is already visible, Qt destroys and recreates it,
        # which looks like the application relaunching. Realize a hidden native
        # child up front so the window is already in that state.
        self._native_anchor = QWidget(central)
        self._native_anchor.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self._native_anchor.setFixedSize(1, 1)
        self._native_anchor.winId()
        self._native_anchor.hide()

        init_elapsed = time.time() - init_start
        logger.info(f"GUI initialized in {init_elapsed:.3f}s")
        self.load_data()

    def load_data(self):
        """Start loading character data."""
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

    def _open_settings(self):
        """Open the settings popup."""
        from .settings import open_settings

        open_settings(self)

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
        """Handle theme, activation, and window state change events."""
        if event.type() == PALETTE_CHANGE_EVENT and not self._updating_theme:
            self._updating_theme = True
            self.setStyleSheet(STYLESHEET)
            self._updating_theme = False
        elif event.type() == QEvent.Type.WindowStateChange:
            logger.debug("Window state changed: %s", self.windowState())
            # Forward state change to central widget so overlaid child popups update cleanly
            QApplication.sendEvent(self.centralWidget(), event)
        super().changeEvent(event)



def main(argv=None):
    """Main entry point for the application."""
    import argparse
    import cProfile
    import pstats
    from datetime import datetime

    parser = argparse.ArgumentParser(prog="NanokaLeaks", description="Nanoka Viewer")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose / debug logging output",
    )
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

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.verbose:
        import os
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType, qVersion

        qt_logger = logging.getLogger("qt")

        def _qt_message_handler(mode, context, message):
            loc = f" ({context.file}:{context.line})" if context.file else ""
            if mode == QtMsgType.QtDebugMsg:
                qt_logger.debug("%s%s", message, loc)
            elif mode == QtMsgType.QtInfoMsg:
                qt_logger.info("%s%s", message, loc)
            elif mode == QtMsgType.QtWarningMsg:
                qt_logger.warning("%s%s", message, loc)
            elif mode == QtMsgType.QtCriticalMsg:
                qt_logger.error("%s%s", message, loc)
            elif mode == QtMsgType.QtFatalMsg:
                qt_logger.critical("%s%s", message, loc)

        qInstallMessageHandler(_qt_message_handler)

        # Enable diagnostic rules for QPA, styles, and Wayland painting unless
        # overridden.  Pointer/frame noise stays off by default; use
        # NANOKA_TRACE_MOUSE=1 for a readable widget-level mouse trace instead.
        if "QT_LOGGING_RULES" not in os.environ:
            os.environ["QT_LOGGING_RULES"] = (
                "qt.qpa.wayland.pointer=false;qt.qpa.input*=false;qt.qpa.*.debug=true;"
                "qt.widgets.styling.debug=true;qt.gui.painting.debug=true"
            )

        logger.debug("Verbose logging active. Qt version: %s", qVersion())
        if os.environ.get("NANOKA_TRACE_MOUSE"):
            logger.debug("NANOKA_TRACE_MOUSE is set; widget mouse trace will follow")

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
    import os

    app = QApplication(argv if argv else sys.argv)
    app.setStyle("Fusion")
    if os.environ.get("NANOKA_TRACE_MOUSE"):
        _install_mouse_trace(app)

    window = NanokaViewer()
    window.show()
    return app.exec()


if __name__ == "__main__":
    main()
