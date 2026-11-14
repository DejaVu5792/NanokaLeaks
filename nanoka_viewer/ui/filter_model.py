"""Per-game element and weapon filters for the card strips.

Each game header shows one filter bar: a switch between the element and
weapon/specialty catalogs, a select-all toggle and one icon per category.
This module owns the catalog and the row filtering so the QML stays
declarative and the rules stay testable without a QML engine:

* :class:`FilterModel` is the QML list of categories for the active mode.
* :class:`CharacterFilterProxy` hides cards whose category is disabled.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    Property,
    QSortFilterProxyModel,
    Qt,
    Signal,
    Slot,
)

from ..api import get_element_image, get_specialty_image
from ..api.game_data import (
    GI_ELEMENTS,
    GI_WEAPONS,
    HSR_ELEMENTS,
    HSR_PATHS,
    NTE_ELEMENTS,
    WW_ELEMENTS,
    WW_WEAPONS,
    ZZZ_ELEMENTS,
    ZZZ_SPECIALTIES,
)

MODE_ELEMENT = "element"
MODE_WEAPON = "weapon"
MODES = (MODE_ELEMENT, MODE_WEAPON)

# Placeholders such as NTE's missing weapon are not useful filter entries.
IGNORED_KEYS = frozenset({"", "None", "Unknown"})

# Genshin's Traveler avatars report no element, which the card helper maps to
# its "Physical" fallback.  Physical is not a Genshin element, so it must not
# become a filter entry.  The same avatars report a placeholder crossbow, which
# no playable Genshin character uses.
EXCLUDED_CATEGORIES = {
    "gi": frozenset({"Physical", "Crossbow"}),
}


def _category(key: str, icon: str) -> dict[str, str]:
    return {"key": key, "label": key, "icon": icon}


def element_catalog(game: str) -> list[dict[str, str]]:
    """Return one entry per element, in display order."""
    if game == "hsr":
        return [
            _category(name, get_element_image(game, {"damageType": name}))
            for name in HSR_ELEMENTS
        ]
    if game == "gi":
        return [
            _category(name, get_element_image(game, {"element": name}))
            for name in GI_ELEMENTS
        ]
    if game == "ww":
        return [
            _category(name, get_element_image(game, {"element": code}))
            for code, name in WW_ELEMENTS.items()
        ]
    if game == "nte":
        return [
            _category(
                name,
                get_element_image(
                    game, {"element": name, "element_icon": icon}
                ),
            )
            for name, icon in NTE_ELEMENTS.items()
        ]
    if game == "zzz":
        return [
            _category(name, get_element_image(game, {"element": code}))
            for code, name in ZZZ_ELEMENTS.items()
        ]
    return []


def weapon_catalog(game: str) -> list[dict[str, str]]:
    """Return one entry per weapon/specialty, in display order."""
    if game == "hsr":
        return [
            _category(name, get_specialty_image(game, {"baseType": base}))
            for base, name in HSR_PATHS.items()
        ]
    if game == "gi":
        return [
            _category(name, get_specialty_image(game, {"weapon": raw}))
            for raw, name in GI_WEAPONS.items()
        ]
    if game == "ww":
        return [
            _category(name, get_specialty_image(game, {"weapon": code}))
            for code, name in WW_WEAPONS.items()
        ]
    if game == "zzz":
        return [
            _category(name, get_specialty_image(game, {"type": code}))
            for code, name in ZZZ_SPECIALTIES.items()
        ]
    # NTE currently has no second category; the model keeps the bar usable
    # with elements only.
    return []


def build_filter_catalog(game: str) -> dict[str, list[dict[str, str]]]:
    """Return ``{"element": [...], "weapon": [...]}`` for *game*."""
    return {
        MODE_ELEMENT: element_catalog(game),
        MODE_WEAPON: weapon_catalog(game),
    }


class FilterModel(QAbstractListModel):
    """The categories of one game, shown for the active filter mode."""

    KeyRole = Qt.ItemDataRole.UserRole + 1
    LabelRole = Qt.ItemDataRole.UserRole + 2
    IconRole = Qt.ItemDataRole.UserRole + 3
    EnabledRole = Qt.ItemDataRole.UserRole + 4

    _ROLE_NAMES = {
        KeyRole: QByteArray(b"key"),
        LabelRole: QByteArray(b"label"),
        IconRole: QByteArray(b"icon"),
        EnabledRole: QByteArray(b"enabled"),
    }

    # Any change that alters which cards are visible.
    stateChanged = Signal()
    modeChanged = Signal()
    selectionModeChanged = Signal()

    def __init__(self, game: str, parent=None):
        super().__init__(parent)
        self._game = game
        catalog = build_filter_catalog(game)
        self._categories = {
            MODE_ELEMENT: list(catalog[MODE_ELEMENT]),
            MODE_WEAPON: list(catalog[MODE_WEAPON]),
        }
        self._enabled = {
            mode: {item["key"]: True for item in items}
            for mode, items in self._categories.items()
        }
        self._mode = (
            MODE_ELEMENT
            if self._categories[MODE_ELEMENT]
            else MODE_WEAPON
        )
        self._single_selection = True

    # -- QAbstractListModel ------------------------------------------------

    def roleNames(self):
        return dict(self._ROLE_NAMES)

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._categories[self._mode])

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        rows = self._categories[self._mode]
        if not 0 <= index.row() < len(rows):
            return None
        row = rows[index.row()]
        if role == self.KeyRole:
            return row["key"]
        if role == self.LabelRole:
            return row["label"]
        if role == self.IconRole:
            return row["icon"]
        if role == self.EnabledRole:
            return self._enabled[self._mode][row["key"]]
        return None

    # -- QML-facing state --------------------------------------------------

    def _get_mode(self) -> str:
        return self._mode

    mode = Property(str, _get_mode, notify=modeChanged)

    def _get_weapon_available(self) -> bool:
        return bool(self._categories[MODE_WEAPON])

    weaponAvailable = Property(
        bool, _get_weapon_available, notify=stateChanged
    )

    def _get_all_enabled(self) -> bool:
        values = self._enabled[self._mode]
        return all(values.values()) if values else True

    allEnabled = Property(bool, _get_all_enabled, notify=stateChanged)

    def _get_single_selection(self) -> bool:
        return self._single_selection

    def set_single_selection(self, enabled: bool) -> None:
        """Allow only one active filter, or several when disabled."""
        enabled = bool(enabled)
        if enabled == self._single_selection:
            return
        self._single_selection = enabled
        self.selectionModeChanged.emit()

    singleSelection = Property(
        bool, _get_single_selection, notify=selectionModeChanged
    )

    # -- lookups -----------------------------------------------------------

    def enabled_keys(self) -> set[str]:
        """Return the enabled category keys of the active mode."""
        return {
            key
            for key, enabled in self._enabled[self._mode].items()
            if enabled
        }

    def keys(self, mode: str | None = None) -> list[str]:
        """Return the category keys of *mode* (default: active mode)."""
        return [
            item["key"]
            for item in self._categories[self._mode if mode is None else mode]
        ]

    # -- actions -----------------------------------------------------------

    @Slot(str)
    def setMode(self, mode: str):
        """Switch catalogs, selecting every filter in the new mode."""
        if mode not in MODES or mode == self._mode:
            return
        if not self._categories[mode]:
            return
        self.beginResetModel()
        self._mode = mode
        for key in self._enabled[mode]:
            self._enabled[mode][key] = True
        self.endResetModel()
        self.modeChanged.emit()
        self.stateChanged.emit()

    @Slot(str)
    def toggle(self, key: str):
        """Toggle one category of the active mode.

        Clicking an icon while everything is selected isolates that category:
        the first click narrows the strip to the clicked filter instead of
        merely clearing it.
        """
        values = self._enabled[self._mode]
        if key not in values:
            return
        if self._single_selection:
            if values[key] and sum(values.values()) == 1:
                # Clicking the active filter clears it: show everything again.
                for other in values:
                    values[other] = True
            else:
                for other in values:
                    values[other] = other == key
            self._emit_enabled_changed()
            return
        if len(values) > 1 and all(values.values()):
            for other in values:
                values[other] = other == key
            self._emit_enabled_changed()
            return
        values[key] = not values[key]
        for row, item in enumerate(self._categories[self._mode]):
            if item["key"] != key:
                continue
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [self.EnabledRole])
            break
        self.stateChanged.emit()

    def _emit_enabled_changed(self) -> None:
        """Report that every enabled flag may have changed."""
        rows = self._categories[self._mode]
        if rows:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(rows) - 1, 0),
                [self.EnabledRole],
            )
        self.stateChanged.emit()

    @Slot(bool)
    def setAllEnabled(self, enabled: bool):
        """Enable or disable every category of the active mode at once."""
        values = self._enabled[self._mode]
        if not values:
            return
        enabled = bool(enabled)
        if all(value == enabled for value in values.values()):
            return
        for key in values:
            values[key] = enabled
        rows = self._categories[self._mode]
        if rows:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(rows) - 1, 0),
                [self.EnabledRole],
            )
        self.stateChanged.emit()

    @Slot()
    def toggleAll(self):
        """Select-all toggle: partial selection enables everything first."""
        self.setAllEnabled(not self._get_all_enabled())

    def add_categories(self, mode: str, categories):
        """Merge categories the loaded data reported but the catalog lacked.

        New entries start enabled; existing enabled/disabled choices survive.
        """
        if mode not in MODES:
            return
        known = {item["key"] for item in self._categories[mode]}
        excluded = EXCLUDED_CATEGORIES.get(self._game, frozenset())
        additions = []
        for item in categories:
            key = str(item.get("key", ""))
            icon = str(item.get("icon", ""))
            if (
                key in known
                or key in IGNORED_KEYS
                or key in excluded
                or not icon
            ):
                continue
            known.add(key)
            additions.append(_category(key, icon))
        if not additions:
            return
        if mode == self._mode:
            self.beginResetModel()
            self._categories[mode].extend(additions)
            for item in additions:
                self._enabled[mode][item["key"]] = True
            self.endResetModel()
        else:
            self._categories[mode].extend(additions)
            for item in additions:
                self._enabled[mode][item["key"]] = True
        self.stateChanged.emit()


class CharacterFilterProxy(QSortFilterProxyModel):
    """The card list after the active game filter is applied."""

    def __init__(
        self,
        source,
        filters: FilterModel,
        *,
        element_role: int,
        weapon_role: int,
        parent=None,
    ):
        super().__init__(parent)
        self._filters = filters
        self._element_role = element_role
        self._weapon_role = weapon_role
        self._enabled = True
        self.setSourceModel(source)
        filters.stateChanged.connect(self._refresh)

    def _refresh(self) -> None:
        """Re-evaluate every row after the enabled categories changed."""
        self.beginFilterChange()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def setFilteringEnabled(self, enabled: bool) -> None:
        """Show every card when the feature is turned off."""
        enabled = bool(enabled)
        if self._enabled == enabled:
            return
        self._enabled = enabled
        self._refresh()

    def filteringEnabled(self) -> bool:
        return self._enabled

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._enabled or self._filters.rowCount() == 0:
            return True
        source = self.sourceModel()
        index = source.index(source_row, 0, source_parent)
        role = (
            self._element_role
            if self._filters.mode == MODE_ELEMENT
            else self._weapon_role
        )
        category = source.data(index, role)
        if category not in self._filters.keys():
            # Excluded or unknown categories have no toggle of their own;
            # keep their cards visible instead of hiding them behind a
            # filter the user cannot re-enable.
            return True
        return category in self._filters.enabled_keys()
