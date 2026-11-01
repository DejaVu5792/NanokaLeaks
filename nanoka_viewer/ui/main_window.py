"""Main application window for Nanoka Viewer.

The window is still a ``QMainWindow`` (title, icon, minimum size, close-time
thread handling), but its central widget is a ``QQuickWidget`` rendering the
QML tree in ``nanoka_viewer/qml``.  Python keeps the state machine: it exposes
the header's text/enabled flags as Qt properties, the game rows through
:class:`~nanoka_viewer.ui.view_model.SectionsModel`, and the few user actions
as slots the delegates invoke.
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    Property,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from ..api import GAMES, fetch_manifest
from ..api.preload import PRELOAD_ARTWORK, PRELOAD_BUILDS, PRELOAD_DETAILS
from ..settings import get_enabled_games
from .details import open_details
from .external import open_external_url
from .loader import LoadThread
from .preload import get_preload_manager
from .qml_host import create_qml_widget
from .settings import open_settings
from .styles import STYLESHEET
from .view_model import SectionsModel

logger = logging.getLogger(__name__)

# Loader threads that outlived their window (see NanokaViewer.closeEvent).
_DETACHED_THREADS = set()

PALETTE_CHANGE_EVENT = QEvent.Type.PaletteChange

_CACHE_LABELS = {
    PRELOAD_DETAILS: "details",
    PRELOAD_BUILDS: "build tables",
    PRELOAD_ARTWORK: "artwork",
}

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

    # Header state lives in Python so the load state machine stays testable
    # without a QML engine; the QML labels/buttons bind to these properties.
    statusTextChanged = Signal()
    cacheTextChanged = Signal()
    reloadTextChanged = Signal()
    reloadEnabledChanged = Signal()

    statusText = Property(
        str, lambda self: self._status_text, notify=statusTextChanged
    )
    cacheText = Property(
        str, lambda self: self._cache_text, notify=cacheTextChanged
    )
    reloadText = Property(
        str, lambda self: self._reload_text, notify=reloadTextChanged
    )
    reloadEnabled = Property(
        bool, lambda self: self._reload_enabled, notify=reloadEnabledChanged
    )

    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        logger.info("Initializing NanokaViewer...")
        init_start = time.time()

        self.setWindowTitle("Nanoka Viewer")
        self.setMinimumSize(800, 600)
        self.resize(950, 750)
        self._updating_theme = False
        # Kept for the widget-based popups (details/settings), which are
        # children of the QQuickWidget and still styled by this sheet.
        self.setStyleSheet(STYLESHEET)

        self._status_text = "Ready"
        self._cache_text = ""
        self._reload_text = "Reload"
        self._reload_enabled = True

        self.sections_model = SectionsModel(self)

        self._qml = create_qml_widget(
            self,
            context_properties={
                "viewer": self,
                "sections": self.sections_model,
            },
        )
        self._qml.setObjectName("qmlView")
        self.setCentralWidget(self._qml)

        self._loading_chars = {}
        self._loading_index = {}
        self._load_generation = 0
        self._load_threads = []
        self._pending_sections = set()
        self._fetch_finished = False
        self._load_in_progress = False
        self._reload_pending = False
        self._settings_popup = None
        self._sync_sections(self._desired_games())

        self.load_thread = None

        self._cache_label_timer = QTimer(self)
        self._cache_label_timer.setSingleShot(True)
        self._cache_label_timer.timeout.connect(lambda: self._set_cache(""))

        self.preload_manager = get_preload_manager()
        self.preload_manager.progress.connect(self._on_preload_progress)
        self.preload_manager.finished.connect(self._on_preload_finished)

        init_elapsed = time.time() - init_start
        logger.info(f"GUI initialized in {init_elapsed:.3f}s")
        self.load_data()

    # -- QML-facing state --------------------------------------------------

    def qml_root(self):
        """Return the root QML item, or ``None`` before the tree is loaded."""
        return self._qml.rootObject()

    def _set_status(self, text: str) -> None:
        if text == self._status_text:
            return
        self._status_text = text
        self.statusTextChanged.emit()

    def _set_cache(self, text: str) -> None:
        if text == self._cache_text:
            return
        self._cache_text = text
        self.cacheTextChanged.emit()

    def _set_reload(self, *, text: str | None = None, enabled: bool | None = None):
        if text is not None and text != self._reload_text:
            self._reload_text = text
            self.reloadTextChanged.emit()
        if enabled is not None and enabled != self._reload_enabled:
            self._reload_enabled = enabled
            self.reloadEnabledChanged.emit()

    @Slot()
    def reload(self):
        """Header Reload button."""
        self.load_data()

    @Slot()
    def openSettings(self):
        """Header Settings button."""
        self._open_settings()

    @Slot(str, str)
    def openDetails(self, game: str, char_id: str):
        """A card's View button: open the details popup for that character."""
        section = self.sections_model.section(game)
        if section is None:
            logger.debug("No live section for %s; ignoring details request", game)
            return
        char_data = section.characters.char_data(char_id)
        open_details(game, char_id, char_data, self, source=None)

    @Slot(str)
    def openExternal(self, url: str):
        """A card's external-link button."""
        open_external_url(url)

    @Property(str, constant=True)
    def externalIconName(self) -> str:
        """First installed theme icon for the external-link button, or ""."""
        for name in (
            "external-link-symbolic",
            "external-link",
            "document-open-remote",
        ):
            if QIcon.hasThemeIcon(name):
                return name
        return ""

    # -- background cache --------------------------------------------------

    def _on_preload_progress(self, progress):
        """Show background cache progress in the header."""
        self._cache_label_timer.stop()
        if progress.total:
            label = _CACHE_LABELS.get(progress.kind, progress.kind)
            self._set_cache(f"Preloading {label} {progress.completed}/{progress.total}")
        else:
            self._set_cache("Preparing preload...")

    def _on_preload_finished(self, summary):
        label = _CACHE_LABELS.get(summary.kind, summary.kind)
        if summary.cancelled:
            text = f"Preload stopped at {summary.completed}/{summary.total}"
        else:
            text = f"Preloaded {summary.completed}/{summary.total} {label}"
            if summary.failed:
                text += f", {summary.failed} failed"
            if summary.failed_games:
                text += f", {summary.failed_games} game(s) unavailable"
        self._set_cache(text)
        self._cache_label_timer.start(6000)

    # -- loading -----------------------------------------------------------

    def load_data(self):
        """Start loading character data.

        Every load gets a generation token.  Results from a superseded load
        (the user pressed Reload while a previous load was still running) are
        ignored instead of being appended to the freshly cleared sections.
        """
        if self._load_in_progress:
            self._set_reload(enabled=False)
            logger.info("Reload ignored: a load is already in progress")
            return
        self._load_in_progress = True
        self._load_generation += 1
        generation = self._load_generation
        logger.info("Starting data load (generation %d)...", generation)

        games = self._desired_games()
        self._sync_sections(games)

        self._set_reload(text="Loading...", enabled=False)
        self._set_status("Loading...")
        self._fetch_finished = False
        self._loading_chars.clear()
        self._loading_index.clear()
        self._pending_sections = set(games)

        for section in self.sections_model.sections():
            section.characters.clear()
            section.set_status("Loading...")

        if not games:
            self._fetch_finished = True
            self._set_status("No games enabled")
            self._finish_loading_ui(no_games=True)
            return

        thread = LoadThread(self, games)
        thread.game_loaded.connect(
            lambda game, chars, gen=generation: self.on_game_loaded(
                game, chars, gen
            )
        )
        thread.load_finished.connect(
            lambda gen=generation: self.on_load_finished(gen)
        )
        thread.finished.connect(
            lambda t=thread: self._on_load_thread_finished(t)
        )
        self.load_thread = thread
        self._load_threads.append(thread)
        thread.start()

    def _on_load_thread_finished(self, thread):
        """Release a finished loader thread without dropping it mid-flight."""
        try:
            self._load_threads.remove(thread)
            if self.load_thread is thread:
                self.load_thread = None
        except (ValueError, RuntimeError):
            pass
        thread.deleteLater()

    def _open_settings(self):
        """Open the settings popup."""
        popup = open_settings(self)
        if popup is not None and popup is not self._settings_popup:
            popup.games_changed.connect(self.apply_game_settings)
            self._settings_popup = popup

    # -- game sections -----------------------------------------------------

    @staticmethod
    def _desired_games() -> list[str]:
        """Return enabled game ids in the configured display order."""
        return [game for game in get_enabled_games() if game in GAMES]

    def _sync_sections(self, order: list[str]) -> bool:
        """Match the visible sections to *order*; report set changes.

        Order-only changes keep the existing sections (and their cards), so a
        Games-tab reorder never reloads anything.
        """
        changed = self.sections_model.sync(order)
        for game in list(self._loading_chars):
            if game not in order:
                self._loading_chars.pop(game, None)
                self._loading_index.pop(game, None)
        self._pending_sections.intersection_update(order)
        return changed

    def apply_game_settings(self):
        """Apply Games-tab changes to the live view immediately."""
        order = self._desired_games()
        changed = self._sync_sections(order)

        if self._load_in_progress:
            if changed:
                # Re-run the load once the in-flight one finishes; this picks
                # up newly enabled games and drops stale disabled results.
                self._reload_pending = True
            if self._fetch_finished and not self._pending_sections:
                self._finish_loading_ui(no_games=not order)
            elif not order:
                self._set_status("No games enabled")
            return

        if not order:
            self._set_status("No games enabled")
            self._set_reload(text="Reload", enabled=True)
            return

        if changed:
            # The disabled sections are already gone; a fresh load guarantees
            # that newly enabled games are fetched and nothing stale is kept.
            self.load_data()

    def on_game_loaded(self, game, chars, generation=None):
        """Handle when a game's character data is loaded."""
        if generation is not None and generation != self._load_generation:
            logger.debug("Ignoring stale load for %s (generation %s)", game, generation)
            return

        section = self.sections_model.section(game)
        if section is None:
            return

        if not chars:
            section.set_status("Failed to load characters")
            self._mark_section_done(game)
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
        self._load_next_batch(game, chars, self._load_generation)

    def on_load_finished(self, generation=None):
        """Handle when all network data has been fetched."""
        if generation is not None and generation != self._load_generation:
            return
        self._fetch_finished = True
        logger.info("Network load finished; finishing card layout")
        # Cards may still be added in batches.  "Loaded" is only shown once
        # every section has built all of its cards.
        if not self._pending_sections:
            self._finish_loading_ui()

    def _mark_section_done(self, game):
        self._pending_sections.discard(game)
        if self._fetch_finished and not self._pending_sections:
            self._finish_loading_ui()

    def _finish_loading_ui(self, no_games: bool = False):
        self._load_in_progress = False
        self._set_reload(text="Reload", enabled=True)
        if no_games or not self._desired_games():
            self._set_status("No games enabled")
        else:
            self._set_status(f"Loaded at {datetime.now().strftime('%H:%M:%S')}")
        logger.info("Load finished")

        if self._reload_pending:
            self._reload_pending = False
            if self._desired_games():
                QTimer.singleShot(0, self.load_data)

    def _load_next_batch(self, game, chars, generation):
        """Load the next batch of character cards."""
        if generation != self._load_generation:
            return
        if game not in self._loading_index:
            return

        # Load cards in batches so the event loop stays responsive.
        batch_size = 10
        start_idx = self._loading_index[game]
        end_idx = min(start_idx + batch_size, len(chars))

        # Add cards for this batch
        batch_chars = chars[start_idx:end_idx]
        section = self.sections_model.section(game)
        if section is None:
            # The game was disabled while its cards were streaming in.
            self._loading_chars.pop(game, None)
            self._loading_index.pop(game, None)
            return
        section.characters.append_many(batch_chars)

        # Update progress
        self._loading_index[game] = end_idx
        # Update status less frequently to reduce overhead
        if end_idx % 20 == 0 or end_idx == len(chars):
            section.set_status(f"Loading {end_idx}/{len(chars)}")

        # Continue loading if there are more cards with a minimal delay
        if end_idx < len(chars):
            # Use a very short delay to yield control back to the event loop
            QTimer.singleShot(
                0, lambda: self._load_next_batch(game, chars, generation)
            )
        else:
            # Loading complete
            section.set_status(f"{len(chars)} total")
            self._loading_chars.pop(game, None)
            self._loading_index.pop(game, None)
            logger.info(f"Finished loading all {len(chars)} characters for {game}")
            self._mark_section_done(game)

    def closeEvent(self, event):
        """Stop accepting loader results and avoid deleting a live thread.

        A network fetch cannot be interrupted once it is in flight, so a
        thread that is still running is detached from the window; the module
        keeps a reference until it finishes instead of letting Qt destroy a
        running QThread.
        """
        self._load_in_progress = False
        self._load_generation += 1
        for thread in list(self._load_threads):
            try:
                if thread.isRunning():
                    thread.wait(1000)
                if thread.isRunning():
                    thread.setParent(None)
                    _DETACHED_THREADS.add(thread)
                    thread.finished.connect(
                        lambda t=thread: _DETACHED_THREADS.discard(t)
                    )
            except RuntimeError:
                pass
        # Release the QML tree while the Python context objects are still
        # alive.  Otherwise item teardown re-evaluates bindings against a
        # half-destroyed window and logs "Cannot read property ... of null".
        self._qml.setSource(QUrl())
        super().closeEvent(event)

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

        from PySide6.QtCore import QtMsgType, qInstallMessageHandler, qVersion

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


def _app_icon() -> QIcon:
    """Return the app icon bundled next to the executable or in the source tree."""
    candidates = (
        Path(QCoreApplication.applicationDirPath()) / "nanokaleaks.png",
        Path(__file__).resolve().parent.parent / "assets" / "nanokaleaks.png",
    )
    for candidate in candidates:
        if candidate.is_file():
            return QIcon(str(candidate))
    return QIcon()


def _run_app(argv):
    """Create and run the QApplication."""
    import os

    app = QApplication(argv if argv else sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("NanokaLeaks")
    # Match the installed desktop entry and give KWin the icon through
    # xdg_toplevel_icon_v1, which Wayland compositors use for titlebars.
    app.setDesktopFileName("nanokaleaks")
    icon = _app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    if os.environ.get("NANOKA_TRACE_MOUSE"):
        _install_mouse_trace(app)

    window = NanokaViewer()
    window.show()
    return app.exec()


if __name__ == "__main__":
    main()
