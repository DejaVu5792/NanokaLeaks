"""Shared helpers for the headless Qt test-suite.

The suite runs against the ``offscreen`` QPA plugin so it works on CI and on
Wayland without opening windows or touching the user's desktop:

    .venv/bin/python -m unittest discover -s tests -t .
"""

from __future__ import annotations

import os
from contextlib import contextmanager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtCore import QEvent, QEventLoop, QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import nanoka_viewer.ui.details as details
from nanoka_viewer.api.details import CharacterDetail
from nanoka_viewer.ui.styles import STYLESHEET

# Catppuccin Mocha-ish palette as reported by KDE on the reporter's machine.
# Note that ``Light`` is *darker* than ``Button`` here, which is why using it
# for hover states made the View button look pressed.
CATPPUCCIN_ROLES = {
    "Window": "#181825",
    "WindowText": "#cdd6f4",
    "Base": "#1e1e2e",
    "AlternateBase": "#181825",
    "Text": "#cdd6f4",
    "Button": "#313244",
    "ButtonText": "#cdd6f4",
    "BrightText": "#4b4b4b",
    "Highlight": "#cba6f7",
    "HighlightedText": "#11111b",
    "Mid": "#41435a",
    "Midlight": "#252633",
    "Light": "#191922",
    "Dark": "#626488",
    "Shadow": "#191919",
    "Link": "#cba6f7",
}

SAMPLE_DETAIL = CharacterDetail(
    game="hsr",
    char_id="1",
    name="Test Character",
    subtitle="5-star \u00b7 Harmony",
    overview="A test character used by the rendering regression tests.",
    level_label="Lv. 80",
    badges=["5-star"],
    stats=[("HP", "1000"), ("ATK", "500")],
    build=[],
)

DETAILS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app() -> QApplication:
    """Return the shared QApplication instance."""
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(["nanoka-tests"])
    instance.setStyle("Fusion")
    return instance


def apply_catppuccin_palette(application: QApplication):
    """Apply the reporter's palette so rendering assertions are meaningful."""
    palette = QPalette()
    for role_name, color in CATPPUCCIN_ROLES.items():
        palette.setColor(getattr(QPalette.ColorRole, role_name), QColor(color))
    # PlaceholderText is alpha-blended in the real theme; keep it opaque here so
    # pixel probes can compare it directly.
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#f0f0f0"))
    application.setPalette(palette)


def flush(rounds: int = 8):
    """Process pending events a few times (threads, queued signals, layouts)."""
    application = app()
    for _ in range(rounds):
        application.processEvents()


def wait(milliseconds: int = 80):
    """Spin the event loop for *milliseconds*."""
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def reset_popup():
    """Drop the module-level details popup between tests."""
    popup = details._popup
    details._popup = None
    if popup is None:
        return
    try:
        popup.close_popup()
    except RuntimeError:
        return
    popup.deleteLater()
    flush()


def add_native_anchor(host: QWidget) -> QWidget:
    """Reproduce the QtWebEngine anchor that makes Wayland subsurfaces native."""
    anchor = QWidget(host)
    anchor.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
    anchor.setFixedSize(1, 1)
    anchor.winId()
    anchor.hide()
    return anchor


def make_details_host(
    button_text: str = "View", with_native_anchor: bool = False
):
    """Create the smallest realistic main-window structure with a View button.

    Returns ``(window, central_widget, scroll_area, view_button, anchor)``.
    """
    window = QMainWindow()
    window.setStyleSheet(STYLESHEET)
    window.resize(900, 700)

    central = QWidget()
    central.setObjectName("centralWidget")
    window.setCentralWidget(central)

    layout = QVBoxLayout(central)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    content_layout = QVBoxLayout(content)
    button = QPushButton(button_text)
    button.setObjectName("viewBtn")
    button.setFixedSize(120, 28)
    content_layout.addWidget(button)
    content_layout.addStretch(1)
    scroll.setWidget(content)
    layout.addWidget(scroll)

    anchor = add_native_anchor(central) if with_native_anchor else None

    window.show()
    window.activateWindow()
    window.raise_()
    flush()
    return window, central, scroll, button, anchor


class QtTestCase(unittest.TestCase):
    """Base test case: one app, a realistic palette and stubbed loaders."""

    def setUp(self):
        self.application = app()
        self._old_palette = QPalette(self.application.palette())
        apply_catppuccin_palette(self.application)
        self._original_loaders = (
            details.load_character_detail,
            details.load_character_art,
            details.load_character_build,
            details.has_cached_detail,
            details.has_cached_build,
            details.has_cached_art,
        )
        details.load_character_detail = lambda game, char_id: SAMPLE_DETAIL
        details.load_character_art = lambda url: None
        details.load_character_build = lambda detail: []
        details.has_cached_detail = lambda game, char_id: False
        details.has_cached_build = lambda detail: False
        details.has_cached_art = lambda url: False
        reset_popup()

    def tearDown(self):
        reset_popup()
        (
            details.load_character_detail,
            details.load_character_art,
            details.load_character_build,
            details.has_cached_detail,
            details.has_cached_build,
            details.has_cached_art,
        ) = self._original_loaders
        self.application.setPalette(self._old_palette)
        flush(2)

    def get_popup(self):
        """Return the live shared details popup, or ``None``."""
        return details._popup

    def track_window(self, window):
        """Destroy *window* after the test without leaking it into the next one."""

        def cleanup():
            try:
                window.close()
                window.deleteLater()
            except RuntimeError:
                pass
            application = app()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            flush(2)

        self.addCleanup(cleanup)


def open_details_for(window, button):
    """Open the shared details popup the way ``CardWidget`` does."""
    details.open_details("hsr", "1", None, window, source=button)
    flush()
    return details._popup


_HSR_TEST_CHARS = {
    "hsr": {
        "1001": {
            "en": "Testchar",
            "rank": 5,
            "damageType": "Physical",
            "baseType": "Warrior",
            "icon": "TestIcon",
            "release": None,
        }
    }
}


@contextmanager
def real_viewer(with_card=True):
    """Boot the real ``NanokaViewer`` window with only the network stubbed.

    The whole widget tree (native anchor removal, card sections, the real
    ``view_btn`` -> ``open_details`` path) is the production code. Only the
    HTTP-backed loaders are replaced so the suite stays offline and fast.

    Yields ``(window, card)``. *card* is the real populated ``CardWidget``
    (or ``None`` when ``with_card`` is False).
    """
    import nanoka_viewer.ui.loader as loader
    import nanoka_viewer.ui.main_window as main_window
    import nanoka_viewer.ui.card as _card_module
    from nanoka_viewer.ui.card import CardWidget

    originals = (
        loader.get_all_characters_with_new_status,
        main_window.fetch_manifest,
        _card_module.request_image,
        details.load_character_detail,
        details.load_character_art,
        details.load_character_build,
        details.has_cached_detail,
        details.has_cached_build,
        details.has_cached_art,
    )

    # Stub only the network boundaries.
    loader.get_all_characters_with_new_status = lambda game: [
        (cid, data, False)
        for cid, data in _HSR_TEST_CHARS.get(game, {}).items()
    ]
    main_window.fetch_manifest = lambda: {
        game: {"live": "1.0", "latest": "1.0", "new": {}}
        for game in _HSR_TEST_CHARS
    }
    _card_module.request_image = lambda *a, **k: None
    details.load_character_detail = lambda game, char_id: CharacterDetail(
        game=game,
        char_id=char_id,
        name="Testchar",
        subtitle="5-star",
        overview="A test character.",
        level_label="Lv. 80",
    )
    details.load_character_art = lambda url: None
    details.load_character_build = lambda detail: []
    details.has_cached_detail = lambda game, char_id: False
    details.has_cached_build = lambda detail: False
    details.has_cached_art = lambda url: False

    reset_popup()
    window = main_window.NanokaViewer()
    window.show()
    window.activateWindow()
    flush()

    card = None
    if with_card:
        # Let the LoadThread populate the real card via the event loop.
        for _ in range(50):
            wait(20)
            cards = window.game_sections["hsr"].cards_container.findChildren(
                CardWidget
            )
            if cards:
                card = cards[0]
                break

    try:
        yield window, card
    finally:
        (
            loader.get_all_characters_with_new_status,
            main_window.fetch_manifest,
            _card_module.request_image,
            details.load_character_detail,
            details.load_character_art,
            details.load_character_build,
            details.has_cached_detail,
            details.has_cached_build,
            details.has_cached_art,
        ) = originals
        reset_popup()
        try:
            window.close()
            window.deleteLater()
        except RuntimeError:
            pass
        application = app()
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        flush(2)


def button_center_in(widget: QWidget, host: QWidget) -> QPoint:
    """Return the centre of *widget* mapped into *host*'s coordinates."""
    return widget.mapTo(host, widget.rect().center())
