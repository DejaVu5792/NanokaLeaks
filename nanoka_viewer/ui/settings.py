"""In-window settings popup.

The popup keeps the thin widget shell Qt needs to cover the central widget
(:class:`~nanoka_viewer.ui.popup_host.PopupHost`) and renders the backdrop,
panel and content from ``qml/settings/SettingsOverlay.qml``.  All behaviour
that outlives a repaint -- persisting the settings, the preload manager, cache
metadata and the confirmation dialogs -- stays here; the QML tree only binds
to :class:`~nanoka_viewer.ui.settings_model.SettingsViewModel`.
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from ..api import (
    GAMES,
    cache_sizes,
    cached_character_count,
    clear_cache,
    read_build_cache_info,
)
from ..api.preload import (
    PRELOAD_ARTWORK,
    PRELOAD_BUILDS,
    PRELOAD_STATUS_LABELS,
    PreloadProgress,
    PreloadSummary,
)
from ..settings import (
    DEFAULT_SETTINGS,
    load_settings,
    normalize_game_ids,
    normalize_game_order,
    save_settings,
)
from .image_loader import clear_image_cache
from .popup_host import PopupHost, popup_host_for, reusable_popup
from .preload import get_preload_manager
from .settings_model import (
    CACHE_KINDS,
    SECTION_CACHING,
    SECTION_EXPERIMENTAL,
    SECTION_FILTERS,
    SECTION_ORDER,
    SECTION_TOGGLE,
    TAB_CACHE,
    SettingsViewModel,
)

logger = logging.getLogger(__name__)


class SettingsPopup(PopupHost):
    """Lightbox-style settings overlay."""

    overlay_object_name = "settingsOverlay"
    source = "settings/SettingsOverlay.qml"
    log_name = "settings popup"
    logger = logging.getLogger(__name__)

    games_changed = Signal()
    filters_changed = Signal(bool)
    filter_selection_changed = Signal(bool)

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
        self._loading_games = False

        self._model = SettingsViewModel(self)

        self._qml = self._create_view({"settings": self._model})
        # The model must not outlive the engine that binds to it: as a child of
        # the view it is destroyed right after the engine, so no binding is
        # ever evaluated against a dangling context property.
        self._model.setParent(self._qml)

        self._model.closeRequested.connect(self._request_close)
        self._model.cacheSettingChanged.connect(
            self._on_cache_setting_changed
        )
        self._model.experimentalSettingChanged.connect(
            self._on_experimental_setting_changed
        )
        self._model.filtersSettingChanged.connect(
            self._on_filters_setting_changed
        )
        self._model.filterSelectionSettingChanged.connect(
            self._on_filter_selection_setting_changed
        )
        self._model.preloadRequested.connect(self._on_cache_clicked)
        self._model.clearCacheRequested.connect(self._clear_cache)
        self._model.resetRequested.connect(self._on_reset_requested)
        self._model.gameToggled.connect(self._on_game_toggled)
        self._model.orderMoved.connect(self._on_game_order_changed)

        manager = get_preload_manager()
        manager.progress.connect(self._on_preload_progress)
        manager.finished.connect(self._on_preload_finished)
        manager.failed.connect(self._on_preload_failed)

    def open_popup(self):
        settings = dict(load_settings())
        self._model.set_cache_flags(
            details=bool(settings.get("cache_character_details", True)),
            builds=bool(settings.get("cache_character_builds", True)),
            artwork=bool(settings.get("cache_character_artwork", True)),
        )
        self._load_game_settings(settings)
        self._refresh_game_counts()
        self._load_experimental(settings)
        self._load_filters(settings)
        self._model.setTab(TAB_CACHE)
        self._model.set_status("")
        self._reset_clear_button()
        self._sync_preload_state()
        self._update_cache_meta()
        self.show_overlay()

    def _save_and_apply(self):
        # Merge into the stored settings: saving the Cache tab must not wipe
        # the Games tab's enabled list or order.
        settings = dict(load_settings())
        flags = self._model.cache_flags()
        settings.update(
            {
                "cache_character_details": flags["details"],
                "cache_character_builds": flags["builds"],
                "cache_character_artwork": flags["artwork"],
            }
        )
        save_settings(settings)

    def _on_cache_setting_changed(self, _kind: str, _checked: bool):
        self._save_and_apply()

    # -- Experimental tab --------------------------------------------------

    def _load_experimental(self, settings: dict):
        self._model.set_experimental(
            bool(settings.get("sr_centroid_centering", True))
        )

    def _on_experimental_setting_changed(self, _checked: bool):
        self._save_experimental()

    def _save_experimental(self):
        settings = dict(load_settings())
        settings["sr_centroid_centering"] = self._model.srCentroid
        save_settings(settings)

    # -- View tab: filter bars ---------------------------------------------

    def _load_filters(self, settings: dict):
        self._model.set_filters_enabled(
            bool(settings.get("element_weapon_filters", True))
        )
        self._model.set_single_filter_selection(
            bool(settings.get("single_filter_selection", True))
        )

    def _on_filters_setting_changed(self, checked: bool):
        self._save_filters()
        self.filters_changed.emit(bool(checked))

    def _on_filter_selection_setting_changed(self, checked: bool):
        self._save_filters()
        self.filter_selection_changed.emit(bool(checked))

    def _save_filters(self):
        settings = dict(load_settings())
        settings["element_weapon_filters"] = self._model.filtersEnabled
        settings["single_filter_selection"] = (
            self._model.singleFilterSelection
        )
        save_settings(settings)

    # -- Games tab ---------------------------------------------------------

    @staticmethod
    def _game_order_from(settings: dict) -> list[str]:
        """Return the full, sanitized game order for the settings dict."""
        return normalize_game_order(settings.get("game_order"))

    @staticmethod
    def _disabled_games_from(settings: dict) -> set[str]:
        return set(normalize_game_ids(settings.get("disabled_games")))

    def _load_game_settings(self, settings: dict):
        """Populate the toggle rows and the order list without saving."""
        self._loading_games = True
        try:
            order = self._game_order_from(settings)
            disabled = self._disabled_games_from(settings)
            self._model.games.reset_rows(
                (game, info["name"], game not in disabled)
                for game, info in GAMES.items()
            )
            self._populate_order_list(order, disabled)
        finally:
            self._loading_games = False

    def _populate_order_list(self, order: list[str], disabled: set[str]):
        self._model.order.reset_games(
            [game for game in order if game not in disabled],
            {game: info["name"] for game, info in GAMES.items()},
        )

    def visible_game_order(self) -> list[str]:
        """Return the game ids currently shown in the View Order list."""
        return self._model.order.games()

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

    def _on_game_order_changed(self, _source: int = -1, _target: int = -1):
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

    def _refresh_game_counts(self):
        """Update the cached character counts shown on the toggle rows."""
        counts: dict[str, tuple[str, str]] = {}
        for game in GAMES:
            count = cached_character_count(game)
            if count is None:
                counts[game] = (
                    "\u2014",
                    "No cached characters for this game yet",
                )
            else:
                counts[game] = (
                    f"{count:,} characters",
                    f"{count:,} characters cached for this game",
                )
        self._model.games.set_counts(counts)

    def _on_reset_requested(self, section: str):
        if section == SECTION_CACHING:
            self._reset_cache_section()
        elif section == SECTION_TOGGLE:
            self._reset_toggle_section()
        elif section == SECTION_ORDER:
            self._reset_order_section()
        elif section == SECTION_FILTERS:
            self._reset_filters_section()
        elif section == SECTION_EXPERIMENTAL:
            self._reset_experimental_section()

    def _reset_cache_section(self):
        self._model.set_cache_flags(
            details=bool(DEFAULT_SETTINGS["cache_character_details"]),
            builds=bool(DEFAULT_SETTINGS["cache_character_builds"]),
            artwork=bool(DEFAULT_SETTINGS["cache_character_artwork"]),
        )
        self._save_and_apply()
        self._sync_preload_state()

    def _reset_toggle_section(self):
        settings = dict(load_settings())
        order = self._game_order_from(settings)
        self._loading_games = True
        try:
            self._model.games.set_all_enabled(True)
            self._populate_order_list(order, set())
        finally:
            self._loading_games = False
        settings["game_order"] = order
        settings["disabled_games"] = []
        save_settings(settings)
        self.games_changed.emit()

    def _reset_order_section(self):
        settings = dict(load_settings())
        disabled = self._disabled_games_from(settings)
        order = list(GAMES)
        self._loading_games = True
        try:
            self._populate_order_list(order, disabled)
        finally:
            self._loading_games = False
        settings["game_order"] = order
        settings["disabled_games"] = [game for game in order if game in disabled]
        save_settings(settings)
        self.games_changed.emit()

    def _reset_filters_section(self):
        self._model.set_filters_enabled(
            bool(DEFAULT_SETTINGS["element_weapon_filters"])
        )
        self._model.set_single_filter_selection(
            bool(DEFAULT_SETTINGS["single_filter_selection"])
        )
        self._save_filters()
        self.filters_changed.emit(self._model.filtersEnabled)
        self.filter_selection_changed.emit(
            self._model.singleFilterSelection
        )

    def _reset_experimental_section(self):
        self._model.set_experimental(
            bool(DEFAULT_SETTINGS["sr_centroid_centering"])
        )
        self._save_experimental()

    # -- Preload -----------------------------------------------------------

    def _on_cache_clicked(self, kind: str):
        manager = get_preload_manager()
        if manager.running:
            if manager.kind == kind:
                manager.cancel()
                self._model.set_button_state(kind, "Stopping...", False)
            return

        if kind == PRELOAD_ARTWORK and not self._confirm_artwork_download():
            return

        # An explicit Preload click is a promise that the data will be used
        # later, so make sure the matching setting is on before starting.
        if not self._model.cache_flag(kind):
            self._model.setCache(kind, True)
        else:
            self._save_and_apply()

        if not manager.start(kind):
            return
        self._model.set_status("Preparing preload...")
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

        for kind in CACHE_KINDS:
            if running and active_kind == kind:
                self._model.set_button_state(
                    kind, "Cancel", True, "Stop after the current character"
                )
            elif running:
                self._model.set_button_state(
                    kind, "Preload", False, "Another preload is already running"
                )
            else:
                self._model.set_button_state(kind, "Preload", True, "")

        self._model.set_cache_enabled(not running)
        self._model.set_clear_button(
            not running,
            self._model.clearCacheText,
            "Stop the running preload before clearing it." if running else "",
        )

        if running:
            progress = manager.last_progress
            if progress is not None and progress.total:
                self._show_progress(progress)
            else:
                self._model.set_status("Preparing preload...")
        elif manager.last_summary is not None:
            self._show_summary(manager.last_summary)
        elif manager.last_error:
            self._model.set_status(f"Preload failed: {manager.last_error}")

    def _show_progress(self, progress: PreloadProgress):
        label = PRELOAD_STATUS_LABELS.get(progress.kind, progress.kind)
        name = progress.name
        if len(name) > 28:
            name = name[:27].rstrip() + "..."
        text = f"Preloading {label} {progress.completed}/{progress.total}"
        if name:
            text += f" - {name}"
        self._model.set_status(text)

    def _show_summary(self, summary: PreloadSummary):
        label = PRELOAD_STATUS_LABELS.get(summary.kind, summary.kind)
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
        self._model.set_status(text)

    def _on_preload_progress(self, progress: PreloadProgress):
        self._show_progress(progress)

    def _on_preload_finished(self, summary: PreloadSummary):
        self._update_cache_meta()
        self._refresh_game_counts()
        self._sync_preload_state()

    def _on_preload_failed(self, message: str):
        self._update_cache_meta()
        self._refresh_game_counts()
        self._model.set_status(f"Preload failed: {message}")
        self._sync_preload_state()

    def _clear_cache(self):
        manager = get_preload_manager()
        if manager.running:
            self._model.set_status(
                "Stop the running preload before clearing it."
            )
            return
        if not self._confirm_clear_cache():
            return

        clear_cache()
        clear_image_cache()
        manager.last_summary = None
        manager.last_progress = None
        manager.last_error = ""
        self._update_cache_meta()
        self._refresh_game_counts()
        self._model.set_status("Cache cleared.")
        self._model.set_clear_button(False, "Cleared", "")
        QTimer.singleShot(1500, self._reset_clear_button)

    def _reset_clear_button(self):
        self._model.set_clear_button(True, "Clear cache", "")

    def _update_cache_meta(self):
        sizes = cache_sizes()
        info = read_build_cache_info()
        last_cached = float(info.get("last_cached") or 0.0)
        if last_cached > 0:
            last_text = f"Last cached: {self._format_time(last_cached)}"
        else:
            last_text = "Last cached: never"
        self._model.set_cache_meta(
            details=self._format_kb(sizes.get("details", 0)),
            builds=self._format_kb(sizes.get("builds", 0)),
            artwork=self._format_kb(sizes.get("artwork", 0)),
            last_cached=last_text,
        )

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
    host = popup_host_for(parent)

    _settings_popup = reusable_popup(_settings_popup, host)
    if _settings_popup is None:
        _settings_popup = SettingsPopup(host)

    _settings_popup.open_popup()
    return _settings_popup


_settings_popup = None
