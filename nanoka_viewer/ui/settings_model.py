"""QML-facing state for the settings popup.

The popup keeps every side effect in Python (persisting the settings, the
preload manager, cache metadata and the confirmation dialogs) and binds
``qml/settings/SettingsPanel.qml`` to this model.  The model owns only what
the panel displays, so the display rules stay testable without a QML engine:

* :class:`GameToggleModel` is one row per game in the "Toggle View" card.
* :class:`GameOrderModel` is the drag-reorderable "View Order" list.
* :class:`SettingsViewModel` holds the tab, the cache flags, the cache
  metadata and the preload button state.  User actions are re-emitted as
  signals (``cacheSettingChanged``, ``preloadRequested``, ``gameToggled``,
  ...) that the popup handles, mirroring how ``DetailsViewModel`` reports
  ``closeRequested`` and ``retryRequested``.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Property,
    Qt,
    Signal,
    Slot,
)

# Tabs, in TabBar order.
TAB_CACHE = 0
TAB_VIEW = 1

# Cache rows and preload kinds share these names.
CACHE_KINDS = ("details", "builds", "artwork")

# Section reset buttons.
SECTION_CACHING = "caching"
SECTION_TOGGLE = "toggle"
SECTION_ORDER = "order"
SECTION_EXPERIMENTAL = "experimental"


class GameToggleModel(QAbstractListModel):
    """One row per game in the Toggle View card."""

    GameIdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    EnabledRole = Qt.ItemDataRole.UserRole + 3
    CountRole = Qt.ItemDataRole.UserRole + 4
    CountTooltipRole = Qt.ItemDataRole.UserRole + 5

    _ROLE_NAMES = {
        GameIdRole: QByteArray(b"gameId"),
        NameRole: QByteArray(b"name"),
        EnabledRole: QByteArray(b"gameEnabled"),
        CountRole: QByteArray(b"countText"),
        CountTooltipRole: QByteArray(b"countTooltip"),
    }

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._rows: list[dict[int, object]] = []
        self._row_of: dict[str, int] = {}

    # -- QAbstractListModel ------------------------------------------------

    def roleNames(self):
        return dict(self._ROLE_NAMES)

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].get(role)

    # -- population --------------------------------------------------------

    def reset_rows(self, rows) -> None:
        """Replace every row; *rows* is ``(game_id, name, enabled)`` tuples."""
        self.beginResetModel()
        self._rows = [
            {
                self.GameIdRole: str(game),
                self.NameRole: str(name),
                self.EnabledRole: bool(enabled),
                self.CountRole: "",
                self.CountTooltipRole: "",
            }
            for game, name, enabled in rows
        ]
        self._row_of = {
            row[self.GameIdRole]: index for index, row in enumerate(self._rows)
        }
        self.endResetModel()

    def set_enabled(self, game: str, enabled: bool) -> None:
        row = self._row_of.get(game)
        if row is None or self._rows[row][self.EnabledRole] == bool(enabled):
            return
        self._rows[row][self.EnabledRole] = bool(enabled)
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [self.EnabledRole])

    def set_all_enabled(self, enabled: bool) -> None:
        """Toggle every row in one ``dataChanged`` burst."""
        changed = False
        for row in self._rows:
            if row[self.EnabledRole] != bool(enabled):
                row[self.EnabledRole] = bool(enabled)
                changed = True
        if changed and self._rows:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._rows) - 1, 0),
                [self.EnabledRole],
            )

    def set_counts(self, counts: dict[str, tuple[str, str]]) -> None:
        """Apply ``game -> (text, tooltip)`` character counts."""
        if not self._rows:
            return
        for game, (text, tooltip) in counts.items():
            row = self._row_of.get(game)
            if row is None:
                continue
            self._rows[row][self.CountRole] = text
            self._rows[row][self.CountTooltipRole] = tooltip
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(len(self._rows) - 1, 0),
            [self.CountRole, self.CountTooltipRole],
        )

    # -- lookups -----------------------------------------------------------

    def games(self) -> list[str]:
        """Return the game ids in display order."""
        return [str(row[self.GameIdRole]) for row in self._rows]

    def is_enabled(self, game: str) -> bool:
        row = self._row_of.get(game)
        return False if row is None else bool(self._rows[row][self.EnabledRole])

    def enabled_games(self) -> dict[str, bool]:
        """Return ``game -> enabled`` for every row."""
        return {
            str(row[self.GameIdRole]): bool(row[self.EnabledRole])
            for row in self._rows
        }

    def count_text(self, game: str) -> str:
        row = self._row_of.get(game)
        return "" if row is None else str(self._rows[row][self.CountRole])

    def count_tooltip(self, game: str) -> str:
        row = self._row_of.get(game)
        return "" if row is None else str(self._rows[row][self.CountTooltipRole])


class GameOrderModel(QAbstractListModel):
    """The enabled games, in the order their sections are shown."""

    GameIdRole = Qt.ItemDataRole.UserRole + 1
    GameNameRole = Qt.ItemDataRole.UserRole + 2

    _ROLE_NAMES = {
        GameIdRole: QByteArray(b"gameId"),
        GameNameRole: QByteArray(b"gameName"),
    }

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._games: list[str] = []
        self._names: dict[str, str] = {}

    # -- QAbstractListModel ------------------------------------------------

    def roleNames(self):
        return dict(self._ROLE_NAMES)

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._games)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._games):
            return None
        game = self._games[index.row()]
        if role == self.GameIdRole:
            return game
        if role == self.GameNameRole:
            return self._names.get(game, game)
        return None

    # -- population --------------------------------------------------------

    def reset_games(self, games, names: dict[str, str] | None = None) -> None:
        """Replace the list; *names* maps game ids to display names."""
        self.beginResetModel()
        self._games = [str(game) for game in games]
        if names:
            self._names = dict(names)
        self.endResetModel()

    def move(self, source: int, destination: int) -> bool:
        """Move the row at *source* so it ends up at *destination*."""
        count = len(self._games)
        if source == destination:
            return False
        if not 0 <= source < count or not 0 <= destination < count:
            return False
        # ``beginMoveRows`` wants the index *before which* the row lands in
        # the pre-move list, which is one past ``destination`` when moving
        # downwards.
        target = destination if destination < source else destination + 1
        self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), target)
        game = self._games.pop(source)
        self._games.insert(destination, game)
        self.endMoveRows()
        return True

    # -- lookups -----------------------------------------------------------

    def games(self) -> list[str]:
        return list(self._games)


class SettingsViewModel(QObject):
    """Everything ``SettingsPanel.qml`` binds to."""

    tabChanged = Signal()
    cacheChanged = Signal()
    cacheMetaChanged = Signal()
    statusChanged = Signal()
    clearButtonChanged = Signal()
    buttonsChanged = Signal()
    experimentalChanged = Signal()

    # Actions the popup performs; the model never saves or loads anything.
    cacheSettingChanged = Signal(str, bool)
    experimentalSettingChanged = Signal(bool)
    preloadRequested = Signal(str)
    clearCacheRequested = Signal()
    resetRequested = Signal(str)
    gameToggled = Signal(str, bool)
    orderMoved = Signal(int, int)
    closeRequested = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._tab = TAB_CACHE
        self._cache = {kind: True for kind in CACHE_KINDS}
        self._cache_enabled = True
        self._sr_centroid = True
        self._sizes = {kind: "" for kind in CACHE_KINDS}
        self._last_cached = ""
        self._status = ""
        self._clear_enabled = True
        self._clear_text = "Clear cache"
        self._clear_tooltip = ""
        self._button_text = {kind: "Preload" for kind in CACHE_KINDS}
        self._button_enabled = {kind: True for kind in CACHE_KINDS}
        self._button_tooltip = {kind: "" for kind in CACHE_KINDS}
        self._games = GameToggleModel(self)
        self._order = GameOrderModel(self)

    # -- tab ---------------------------------------------------------------

    def _get_tab(self) -> int:
        return self._tab

    @Slot(int)
    def setTab(self, index: int):
        index = TAB_VIEW if int(index) == TAB_VIEW else TAB_CACHE
        if index == self._tab:
            return
        self._tab = index
        self.tabChanged.emit()

    tabIndex = Property(int, _get_tab, setTab, notify=tabChanged)

    # -- cache flags -------------------------------------------------------

    def _get_cache_details(self) -> bool:
        return self._cache["details"]

    def _get_cache_builds(self) -> bool:
        return self._cache["builds"]

    def _get_cache_artwork(self) -> bool:
        return self._cache["artwork"]

    def cache_flag(self, kind: str) -> bool:
        return self._cache.get(kind, True)

    def cache_flags(self) -> dict[str, bool]:
        return dict(self._cache)

    def _set_cache_flag(self, kind: str, checked: bool) -> bool:
        if kind not in self._cache or self._cache[kind] == bool(checked):
            return False
        self._cache[kind] = bool(checked)
        return True

    @Slot(str, bool)
    def setCache(self, kind: str, checked: bool):
        """Called by a row's checkbox: store and ask the popup to persist."""
        if not self._set_cache_flag(kind, checked):
            return
        self.cacheChanged.emit()
        self.cacheSettingChanged.emit(kind, bool(checked))

    def set_cache_flags(
        self, details: bool, builds: bool, artwork: bool
    ) -> None:
        """Apply all three flags at once, without emitting an action."""
        changed = False
        for kind, value in (
            ("details", details),
            ("builds", builds),
            ("artwork", artwork),
        ):
            changed = self._set_cache_flag(kind, value) or changed
        if changed:
            self.cacheChanged.emit()

    cacheDetails = Property(
        bool, _get_cache_details, notify=cacheChanged
    )
    cacheBuilds = Property(bool, _get_cache_builds, notify=cacheChanged)
    cacheArtwork = Property(bool, _get_cache_artwork, notify=cacheChanged)

    def _get_cache_enabled(self) -> bool:
        return self._cache_enabled

    def set_cache_enabled(self, enabled: bool) -> None:
        if self._cache_enabled == bool(enabled):
            return
        self._cache_enabled = bool(enabled)
        self.cacheChanged.emit()

    cacheEnabled = Property(
        bool, _get_cache_enabled, notify=cacheChanged
    )

    # -- experimental ------------------------------------------------------

    def _get_sr_centroid(self) -> bool:
        return self._sr_centroid

    def set_experimental(self, sr_centroid: bool) -> None:
        """Apply the stored experimental flags without emitting an action."""
        if self._sr_centroid == bool(sr_centroid):
            return
        self._sr_centroid = bool(sr_centroid)
        self.experimentalChanged.emit()

    @Slot(bool)
    def setSrCentroid(self, checked: bool):
        """Called by the Smart artwork centering checkbox."""
        if self._sr_centroid == bool(checked):
            return
        self._sr_centroid = bool(checked)
        self.experimentalChanged.emit()
        self.experimentalSettingChanged.emit(bool(checked))

    srCentroid = Property(
        bool, _get_sr_centroid, notify=experimentalChanged
    )

    # -- cache metadata ----------------------------------------------------

    def _get_details_size(self) -> str:
        return self._sizes["details"]

    def _get_builds_size(self) -> str:
        return self._sizes["builds"]

    def _get_artwork_size(self) -> str:
        return self._sizes["artwork"]

    def _get_last_cached(self) -> str:
        return self._last_cached

    def set_cache_meta(
        self,
        *,
        details: str,
        builds: str,
        artwork: str,
        last_cached: str,
    ) -> None:
        """Apply the sizes and the "Last cached" line in one burst."""
        if (
            self._sizes["details"] == details
            and self._sizes["builds"] == builds
            and self._sizes["artwork"] == artwork
            and self._last_cached == last_cached
        ):
            return
        self._sizes = {"details": details, "builds": builds, "artwork": artwork}
        self._last_cached = last_cached
        self.cacheMetaChanged.emit()

    detailsSize = Property(str, _get_details_size, notify=cacheMetaChanged)
    buildsSize = Property(str, _get_builds_size, notify=cacheMetaChanged)
    artworkSize = Property(str, _get_artwork_size, notify=cacheMetaChanged)
    buildsLast = Property(str, _get_last_cached, notify=cacheMetaChanged)

    # -- preload buttons ---------------------------------------------------

    def button_text(self, kind: str) -> str:
        return self._button_text.get(kind, "Preload")

    def button_enabled(self, kind: str) -> bool:
        return self._button_enabled.get(kind, True)

    def set_button_state(
        self, kind: str, text: str, enabled: bool, tooltip: str = ""
    ) -> None:
        """Apply one row's button label, enabled state and tooltip."""
        if kind not in self._button_text:
            return
        if (
            self._button_text[kind] == text
            and self._button_enabled[kind] == bool(enabled)
            and self._button_tooltip[kind] == tooltip
        ):
            return
        self._button_text[kind] = text
        self._button_enabled[kind] = bool(enabled)
        self._button_tooltip[kind] = tooltip
        self.buttonsChanged.emit()

    def _get_details_button_text(self) -> str:
        return self._button_text["details"]

    def _get_builds_button_text(self) -> str:
        return self._button_text["builds"]

    def _get_artwork_button_text(self) -> str:
        return self._button_text["artwork"]

    def _get_details_button_enabled(self) -> bool:
        return self._button_enabled["details"]

    def _get_builds_button_enabled(self) -> bool:
        return self._button_enabled["builds"]

    def _get_artwork_button_enabled(self) -> bool:
        return self._button_enabled["artwork"]

    def _get_details_button_tooltip(self) -> str:
        return self._button_tooltip["details"]

    def _get_builds_button_tooltip(self) -> str:
        return self._button_tooltip["builds"]

    def _get_artwork_button_tooltip(self) -> str:
        return self._button_tooltip["artwork"]

    detailsButtonText = Property(
        str, _get_details_button_text, notify=buttonsChanged
    )
    buildsButtonText = Property(
        str, _get_builds_button_text, notify=buttonsChanged
    )
    artworkButtonText = Property(
        str, _get_artwork_button_text, notify=buttonsChanged
    )
    detailsButtonEnabled = Property(
        bool, _get_details_button_enabled, notify=buttonsChanged
    )
    buildsButtonEnabled = Property(
        bool, _get_builds_button_enabled, notify=buttonsChanged
    )
    artworkButtonEnabled = Property(
        bool, _get_artwork_button_enabled, notify=buttonsChanged
    )
    detailsButtonTooltip = Property(
        str, _get_details_button_tooltip, notify=buttonsChanged
    )
    buildsButtonTooltip = Property(
        str, _get_builds_button_tooltip, notify=buttonsChanged
    )
    artworkButtonTooltip = Property(
        str, _get_artwork_button_tooltip, notify=buttonsChanged
    )

    @Slot(str)
    def preload(self, kind: str):
        """A row's Preload/Cancel button was clicked."""
        self.preloadRequested.emit(kind)

    # -- status and clear button ------------------------------------------

    def _get_status(self) -> str:
        return self._status

    def set_status(self, text: str) -> None:
        if self._status == text:
            return
        self._status = text
        self.statusChanged.emit()

    cacheStatus = Property(str, _get_status, notify=statusChanged)

    def _get_clear_enabled(self) -> bool:
        return self._clear_enabled

    def _get_clear_text(self) -> str:
        return self._clear_text

    def _get_clear_tooltip(self) -> str:
        return self._clear_tooltip

    def set_clear_button(
        self, enabled: bool, text: str = "Clear cache", tooltip: str = ""
    ) -> None:
        if (
            self._clear_enabled == bool(enabled)
            and self._clear_text == text
            and self._clear_tooltip == tooltip
        ):
            return
        self._clear_enabled = bool(enabled)
        self._clear_text = text
        self._clear_tooltip = tooltip
        self.clearButtonChanged.emit()

    clearCacheEnabled = Property(
        bool, _get_clear_enabled, notify=clearButtonChanged
    )
    clearCacheText = Property(
        str, _get_clear_text, notify=clearButtonChanged
    )
    clearCacheTooltip = Property(
        str, _get_clear_tooltip, notify=clearButtonChanged
    )

    @Slot()
    def clearCache(self):
        self.clearCacheRequested.emit()

    # -- section resets ----------------------------------------------------

    @Slot(str)
    def resetSection(self, section: str):
        self.resetRequested.emit(section)

    # -- games -------------------------------------------------------------

    def _get_games(self) -> QObject:
        return self._games

    def _get_order(self) -> QObject:
        return self._order

    games = Property(QObject, _get_games, constant=True)
    order = Property(QObject, _get_order, constant=True)

    @Slot(str, bool)
    def setGameEnabled(self, game: str, enabled: bool):
        """Called by a toggle row: store, then let the popup persist."""
        if self._games.is_enabled(game) == bool(enabled):
            return
        self._games.set_enabled(game, enabled)
        self.gameToggled.emit(game, bool(enabled))

    @Slot(int, int)
    def moveGame(self, source: int, destination: int):
        """Called when a View Order row is dropped."""
        if self._order.move(source, destination):
            self.orderMoved.emit(source, destination)

    @Slot()
    def requestClose(self):
        self.closeRequested.emit()
