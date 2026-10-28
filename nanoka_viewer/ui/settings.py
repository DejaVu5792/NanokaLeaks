"""In-window settings popup."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..api import GAMES, cache_sizes, clear_cache, read_build_cache_info
from ..api.preload import (
    PRELOAD_ARTWORK,
    PRELOAD_BUILDS,
    PRELOAD_DETAILS,
    PreloadProgress,
    PreloadSummary,
)
from ..settings import load_settings, save_settings
from .image_loader import clear_image_cache
from .overlay import OverlayPopup, is_alive
from .preload import get_preload_manager

logger = logging.getLogger(__name__)

_PRELOAD_LABELS = {
    PRELOAD_DETAILS: "detail pages",
    PRELOAD_BUILDS: "build tables",
    PRELOAD_ARTWORK: "artwork images",
}


class _GameOrderList(QListWidget):
    """Vertical list whose rows can be reordered by dragging."""

    order_changed = Signal()

    def dropEvent(self, event):
        super().dropEvent(event)
        self.order_changed.emit()


class SettingsPopup(OverlayPopup):
    """Lightbox-style settings overlay."""

    overlay_object_name = "settingsOverlay"
    panel_object_name = "settingsPanel"
    log_name = "settings popup"
    logger = logging.getLogger(__name__)

    games_changed = Signal()

    width_ratio = 0.46
    min_width = 360
    max_width = 520
    hard_min_width = 300
    height_ratio = 0.74
    min_height = 420
    max_height = 640
    hard_min_height = 280
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
        close_btn.setObjectName("settingsCloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_popup)
        header_layout.addWidget(close_btn)

        panel_layout.addWidget(header)

        self._loading_games = False
        self.game_checkboxes: dict[str, QCheckBox] = {}

        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._build_cache_tab(), "Cache")
        self.tabs.addTab(self._build_games_tab(), "Games")
        self.tabs.setCurrentIndex(0)
        panel_layout.addWidget(self.tabs, 1)

        manager = get_preload_manager()
        manager.progress.connect(self._on_preload_progress)
        manager.finished.connect(self._on_preload_finished)
        manager.failed.connect(self._on_preload_failed)

    @staticmethod
    def _scroll_page(page: QWidget) -> QScrollArea:
        """Wrap a tab page so the popup stays usable on small screens."""
        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    @staticmethod
    def _make_form_card() -> tuple[QFrame, QVBoxLayout]:
        """Create a Kirigami FormCard-like container for grouped settings."""
        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 4, 14, 4)
        card_layout.setSpacing(0)
        return card, card_layout

    @staticmethod
    def _make_row_separator() -> QFrame:
        separator = QFrame()
        separator.setObjectName("settingsRowSeparator")
        separator.setFixedHeight(1)
        return separator

    def _build_cache_tab(self) -> QWidget:
        body = QWidget()
        body.setObjectName("settingsPage")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 18, 20, 20)
        body_layout.setSpacing(8)

        cache_label = QLabel("Caching")
        cache_label.setObjectName("settingsSectionTitle")
        body_layout.addWidget(cache_label)

        card, card_layout = self._make_form_card()
        (
            self.cache_details,
            self.cache_details_btn,
            self.details_size,
            _,
        ) = self._add_cache_row(
            card_layout,
            "Cache character details",
            "Caches the detail text: overview, stats, skills, and extras.",
            PRELOAD_DETAILS,
        )
        (
            self.cache_builds,
            self.cache_builds_btn,
            self.builds_size,
            self.builds_last,
        ) = self._add_cache_row(
            card_layout,
            "Cache character builds",
            "Always refreshes the per-version build tables used by recommended "
            "builds; unchanged tables are revalidated with ETags.",
            PRELOAD_BUILDS,
            show_last_cached=True,
        )
        (
            self.cache_artwork,
            self.cache_artwork_btn,
            self.artwork_size,
            _,
        ) = self._add_cache_row(
            card_layout,
            "Cache character details artwork",
            "Details artwork is a large download and uses much more disk "
            "space than the text caches.",
            PRELOAD_ARTWORK,
        )
        body_layout.addWidget(card)

        self.cache_status = QLabel("")
        self.cache_status.setObjectName("settingsHint")
        self.cache_status.setWordWrap(True)
        body_layout.addWidget(self.cache_status)

        body_layout.addSpacing(4)

        self.clear_cache_btn = QPushButton("Clear cache")
        self.clear_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        body_layout.addWidget(
            self.clear_cache_btn, alignment=Qt.AlignmentFlag.AlignLeft
        )

        body_layout.addStretch(1)
        return self._scroll_page(body)

    def _build_games_tab(self) -> QWidget:
        body = QWidget()
        body.setObjectName("settingsPage")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 18, 20, 20)
        body_layout.setSpacing(8)

        toggle_label = QLabel("Toggle View")
        toggle_label.setObjectName("settingsSectionTitle")
        body_layout.addWidget(toggle_label)

        toggle_card, toggle_layout = self._make_form_card()
        for index, (game, info) in enumerate(GAMES.items()):
            if index:
                toggle_layout.addWidget(self._make_row_separator())
            checkbox = QCheckBox(info["name"])
            checkbox.setObjectName("settingsCheckBox")
            checkbox.setToolTip(
                "Unchecking hides this game and stops the viewer from loading "
                "its characters, details, builds, and artwork."
            )
            checkbox.toggled.connect(
                lambda checked, game=game: self._on_game_toggled(game, checked)
            )
            toggle_layout.addWidget(checkbox)
            self.game_checkboxes[game] = checkbox
        body_layout.addWidget(toggle_card)

        body_layout.addSpacing(8)

        order_label = QLabel("View Order")
        order_label.setObjectName("settingsSectionTitle")
        body_layout.addWidget(order_label)

        order_hint = QLabel("Drag the enabled games to reorder their sections.")
        order_hint.setObjectName("settingsHint")
        order_hint.setWordWrap(True)
        body_layout.addWidget(order_hint)

        order_card, order_layout = self._make_form_card()
        order_layout.setContentsMargins(4, 4, 4, 4)
        self.game_order_list = _GameOrderList()
        self.game_order_list.setObjectName("gameOrderList")
        self.game_order_list.setFrameShape(QFrame.Shape.NoFrame)
        self.game_order_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.game_order_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.game_order_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.game_order_list.setDropIndicatorShown(True)
        self.game_order_list.setMinimumHeight(140)
        self.game_order_list.order_changed.connect(self._on_game_order_changed)
        order_layout.addWidget(self.game_order_list, 1)
        body_layout.addWidget(order_card, 1)
        return self._scroll_page(body)

    def _add_cache_row(
        self,
        body_layout: QVBoxLayout,
        title: str,
        tooltip: str,
        kind: str,
        *,
        show_last_cached: bool = False,
    ):
        checkbox = QCheckBox(title)
        checkbox.setToolTip(tooltip)
        checkbox.toggled.connect(self._save_and_apply)

        button = self._make_cache_button()
        button.clicked.connect(lambda: self._on_cache_clicked(kind))

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)
        top_layout.addWidget(checkbox, 1)
        top_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignRight)

        meta = QWidget()
        meta_layout = QHBoxLayout(meta)
        meta_layout.setContentsMargins(24, 0, 0, 0)
        meta_layout.setSpacing(6)

        last_label = None
        if show_last_cached:
            last_label = QLabel("Last cached: never")
            last_label.setObjectName("settingsHint")
            meta_layout.addWidget(last_label)

        meta_layout.addStretch(1)

        size_label = QLabel("")
        size_label.setObjectName("settingsHint")
        meta_layout.addWidget(size_label)

        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 4, 0, 4)
        row_layout.setSpacing(2)
        row_layout.addWidget(top)
        row_layout.addWidget(meta)
        if body_layout.count():
            body_layout.addWidget(self._make_row_separator())
        body_layout.addWidget(row)

        return checkbox, button, size_label, last_label

    def _make_cache_button(self) -> QPushButton:
        button = QPushButton("Preload")
        button.setObjectName("cacheBtn")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedWidth(84)
        return button

    def open_popup(self):
        settings = dict(load_settings())
        self.cache_details.setChecked(
            bool(settings.get("cache_character_details", True))
        )
        self.cache_builds.setChecked(bool(settings.get("cache_character_builds", True)))
        self.cache_artwork.setChecked(
            bool(settings.get("cache_character_artwork", True))
        )
        self._load_game_settings(settings)
        self.tabs.setCurrentIndex(0)
        self._sync_preload_state()
        self._update_cache_meta()
        self.show_overlay()

    def _save_and_apply(self):
        # Merge into the stored settings: saving the Cache tab must not wipe
        # the Games tab's enabled list or order.
        settings = dict(load_settings())
        settings.update(
            {
                "cache_character_details": self.cache_details.isChecked(),
                "cache_character_builds": self.cache_builds.isChecked(),
                "cache_character_artwork": self.cache_artwork.isChecked(),
            }
        )
        save_settings(settings)

    # -- Games tab ---------------------------------------------------------

    @staticmethod
    def _game_order_from(settings: dict) -> list[str]:
        """Return the full, sanitized game order for the settings dict."""
        order: list[str] = []
        raw = settings.get("game_order")
        if isinstance(raw, (list, tuple)):
            for value in raw:
                game = str(value)
                if game in GAMES and game not in order:
                    order.append(game)
        for game in GAMES:
            if game not in order:
                order.append(game)
        return order

    @staticmethod
    def _disabled_games_from(settings: dict) -> set[str]:
        raw = settings.get("disabled_games")
        if not isinstance(raw, (list, tuple)):
            return set()
        return {str(value) for value in raw if str(value) in GAMES}

    def _load_game_settings(self, settings: dict):
        """Populate checkboxes and the order list without emitting changes."""
        self._loading_games = True
        try:
            order = self._game_order_from(settings)
            disabled = self._disabled_games_from(settings)
            for game, checkbox in self.game_checkboxes.items():
                checkbox.setChecked(game not in disabled)
            self._populate_order_list(order, disabled)
        finally:
            self._loading_games = False

    def _populate_order_list(self, order: list[str], disabled: set[str]):
        self.game_order_list.blockSignals(True)
        try:
            self.game_order_list.clear()
            for game in order:
                if game in disabled:
                    continue
                item = QListWidgetItem(f"\u22ee\u22ee  {GAMES[game]['name']}")
                item.setData(Qt.ItemDataRole.UserRole, game)
                item.setToolTip("Drag to change the section order")
                self.game_order_list.addItem(item)
        finally:
            self.game_order_list.blockSignals(False)

    def visible_game_order(self) -> list[str]:
        """Return the game ids currently shown in the View Order list."""
        return [
            str(self.game_order_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.game_order_list.count())
        ]

    def _on_game_toggled(self, game: str, checked: bool):
        if self._loading_games:
            return
        settings = dict(load_settings())
        order = self._game_order_from(settings)
        disabled = self._disabled_games_from(settings)
        if checked:
            disabled.discard(game)
        else:
            disabled.add(game)
        settings["game_order"] = order
        settings["disabled_games"] = [
            game_id for game_id in order if game_id in disabled
        ]
        save_settings(settings)
        self._populate_order_list(order, disabled)
        self.games_changed.emit()

    def _on_game_order_changed(self):
        if self._loading_games:
            return
        visible = self.visible_game_order()
        settings = dict(load_settings())
        order = self._game_order_from(settings)
        disabled = self._disabled_games_from(settings)

        # Replace only the enabled slots so disabled games keep their stored
        # position for when the user enables them again.
        new_order: list[str] = []
        cursor = 0
        for game in order:
            if game in disabled:
                new_order.append(game)
                continue
            if cursor < len(visible):
                new_order.append(visible[cursor])
                cursor += 1
            else:
                new_order.append(game)

        settings["game_order"] = new_order
        settings["disabled_games"] = [
            game_id for game_id in new_order if game_id in disabled
        ]
        save_settings(settings)
        self.games_changed.emit()

    def _checkbox_for(self, kind: str) -> QCheckBox:
        return {
            PRELOAD_DETAILS: self.cache_details,
            PRELOAD_BUILDS: self.cache_builds,
            PRELOAD_ARTWORK: self.cache_artwork,
        }[kind]

    def _button_for(self, kind: str) -> QPushButton:
        return {
            PRELOAD_DETAILS: self.cache_details_btn,
            PRELOAD_BUILDS: self.cache_builds_btn,
            PRELOAD_ARTWORK: self.cache_artwork_btn,
        }[kind]

    def _on_cache_clicked(self, kind: str):
        manager = get_preload_manager()
        if manager.running:
            if manager.kind == kind:
                manager.cancel()
                self._button_for(kind).setText("Stopping...")
                self._button_for(kind).setEnabled(False)
            return

        if kind == PRELOAD_ARTWORK and not self._confirm_artwork_download():
            return

        # An explicit Preload click is a promise that the data will be used
        # later, so make sure the matching setting is on before starting.
        checkbox = self._checkbox_for(kind)
        if not checkbox.isChecked():
            checkbox.setChecked(True)
        else:
            self._save_and_apply()

        if not manager.start(kind):
            return
        self.cache_status.setText("Preparing preload...")
        self._sync_preload_state()

    def _confirm_artwork_download(self) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Preload character artwork?")
        box.setText("Character artwork is a large download.")
        box.setInformativeText(
            "Preloading the details artwork for every character can use hundreds "
            "of megabytes of disk space and take a while.\n\n"
            "Do you still want to continue?"
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _confirm_clear_cache(self) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Clear cache?")
        box.setText("Clear all cached data?")
        box.setInformativeText(
            "This removes character details, builds, artwork, and card images. "
            "It cannot be undone."
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _sync_preload_state(self):
        manager = get_preload_manager()
        running = manager.running
        active_kind = manager.kind if running else ""

        for kind in (PRELOAD_DETAILS, PRELOAD_BUILDS, PRELOAD_ARTWORK):
            button = self._button_for(kind)
            if running and active_kind == kind:
                button.setText("Cancel")
                button.setToolTip("Stop after the current character")
                button.setEnabled(True)
            elif running:
                button.setText("Preload")
                button.setToolTip("Another preload is already running")
                button.setEnabled(False)
            else:
                button.setText("Preload")
                button.setToolTip("")
                button.setEnabled(True)

        self.cache_details.setEnabled(not running)
        self.cache_builds.setEnabled(not running)
        self.cache_artwork.setEnabled(not running)
        self.clear_cache_btn.setEnabled(not running)
        self.clear_cache_btn.setToolTip(
            "Stop the running preload before clearing it." if running else ""
        )

        if running:
            progress = manager.last_progress
            if progress is not None and progress.total:
                self._show_progress(progress)
            else:
                self.cache_status.setText("Preparing preload...")
        elif manager.last_summary is not None:
            self._show_summary(manager.last_summary)
        elif manager.last_error:
            self.cache_status.setText(f"Preload failed: {manager.last_error}")

    def _show_progress(self, progress: PreloadProgress):
        label = _PRELOAD_LABELS.get(progress.kind, progress.kind)
        name = progress.name
        if len(name) > 28:
            name = name[:27].rstrip() + "..."
        text = f"Preloading {label} {progress.completed}/{progress.total}"
        if name:
            text += f" - {name}"
        self.cache_status.setText(text)

    def _show_summary(self, summary: PreloadSummary):
        label = _PRELOAD_LABELS.get(summary.kind, summary.kind)
        cached = max(0, summary.completed - summary.failed - summary.skipped)
        if summary.cancelled:
            text = f"Stopped. Preloaded {cached} {label}."
        else:
            text = f"Preloaded {cached} {label}."
        if summary.failed:
            text += f" {summary.failed} failed."
        if summary.skipped:
            if summary.kind == PRELOAD_BUILDS:
                text += f" {summary.skipped} without build tables."
            else:
                text += f" {summary.skipped} unavailable."
        if summary.failed_games:
            text += f" {summary.failed_games} game(s) unavailable."
        self.cache_status.setText(text)

    def _on_preload_progress(self, progress: PreloadProgress):
        self._show_progress(progress)

    def _on_preload_finished(self, summary: PreloadSummary):
        self._update_cache_meta()
        self._sync_preload_state()

    def _on_preload_failed(self, message: str):
        self._update_cache_meta()
        self.cache_status.setText(f"Preload failed: {message}")
        self._sync_preload_state()

    def _clear_cache(self):
        manager = get_preload_manager()
        if manager.running:
            self.cache_status.setText("Stop the running preload before clearing it.")
            return
        if not self._confirm_clear_cache():
            return

        clear_cache()
        clear_image_cache()
        manager.last_summary = None
        manager.last_progress = None
        manager.last_error = ""
        self._update_cache_meta()
        self.cache_status.setText("Cache cleared.")
        self.clear_cache_btn.setEnabled(False)
        self.clear_cache_btn.setText("Cleared")
        QTimer.singleShot(1500, self._reset_clear_button)

    def _reset_clear_button(self):
        self.clear_cache_btn.setEnabled(True)
        self.clear_cache_btn.setText("Clear cache")
        self.clear_cache_btn.setToolTip("")

    def _update_cache_meta(self):
        sizes = cache_sizes()
        self.details_size.setText(self._format_kb(sizes.get("details", 0)))
        self.builds_size.setText(self._format_kb(sizes.get("builds", 0)))
        self.artwork_size.setText(self._format_kb(sizes.get("artwork", 0)))

        info = read_build_cache_info()
        last_cached = float(info.get("last_cached") or 0.0)
        if last_cached > 0:
            self.builds_last.setText(f"Last cached: {self._format_time(last_cached)}")
        else:
            self.builds_last.setText("Last cached: never")

    @staticmethod
    def _format_kb(size_bytes: int) -> str:
        size_bytes = max(0, int(size_bytes))
        if size_bytes == 0:
            return "0 kB"
        return f"{(size_bytes + 1023) // 1024:,} kB"

    @staticmethod
    def _format_time(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


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
