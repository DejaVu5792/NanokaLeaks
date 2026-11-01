"""QML-facing view models for the main window.

The main view is rendered by QML (``nanoka_viewer/qml``).  Everything the
delegates display is precomputed here so the QML stays declarative and the
display rules stay unit-testable without a QML engine:

* :class:`CharacterModel` is one game's flat list of characters; every card
  delegate binds to one row of it.
* :class:`Section` is one game row: its name, loading status, version badges
  and the :class:`CharacterModel` behind its horizontal card list.
* :class:`SectionsModel` is the ordered list of :class:`Section` objects the
  root ``ListView`` renders.

Sections keep their Python identity across reorders: only the order of the
model changes, so cards, status text and badges survive a Games-tab reorder
without a reload.
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
)

from ..api import (
    GAMES,
    get_character_image,
    get_character_url,
    get_element,
    get_element_image,
    get_name,
    get_rarity,
    get_specialty,
    get_specialty_image,
)

# The card is a fixed-width column, so long names are cut to one line.
NAME_LIMIT = 14

# Star colours per rarity, matching the widget implementation.
RARITY_COLORS = {
    "S": "#FF6B6B",
    "5": "#FFD700",
    "4": "#9370DB",
    "A": "#FF6B6B",
}


def display_name(name: str) -> str:
    """Return *name* shortened to the card's one-line budget."""
    if len(name) <= NAME_LIMIT:
        return name
    return name[:NAME_LIMIT] + "..."


class CharacterModel(QAbstractListModel):
    """Flat list of one game's characters, consumed by the card delegates."""

    CharIdRole = Qt.ItemDataRole.UserRole + 1
    FullNameRole = Qt.ItemDataRole.UserRole + 2
    DisplayNameRole = Qt.ItemDataRole.UserRole + 3
    RarityRole = Qt.ItemDataRole.UserRole + 4
    RarityColorRole = Qt.ItemDataRole.UserRole + 5
    ElementRole = Qt.ItemDataRole.UserRole + 6
    ElementTextRole = Qt.ItemDataRole.UserRole + 7
    ElementImageRole = Qt.ItemDataRole.UserRole + 8
    SpecialtyRole = Qt.ItemDataRole.UserRole + 9
    SpecialtyImageRole = Qt.ItemDataRole.UserRole + 10
    ImageRole = Qt.ItemDataRole.UserRole + 11
    UrlRole = Qt.ItemDataRole.UserRole + 12
    IsNewRole = Qt.ItemDataRole.UserRole + 13

    _ROLE_NAMES = {
        CharIdRole: QByteArray(b"charId"),
        FullNameRole: QByteArray(b"fullName"),
        DisplayNameRole: QByteArray(b"displayName"),
        RarityRole: QByteArray(b"rarity"),
        RarityColorRole: QByteArray(b"rarityColor"),
        ElementRole: QByteArray(b"element"),
        ElementTextRole: QByteArray(b"elementText"),
        ElementImageRole: QByteArray(b"elementImage"),
        SpecialtyRole: QByteArray(b"specialty"),
        SpecialtyImageRole: QByteArray(b"specialtyImage"),
        ImageRole: QByteArray(b"image"),
        UrlRole: QByteArray(b"url"),
        IsNewRole: QByteArray(b"isNew"),
    }

    def __init__(self, game: str, parent: QObject | None = None):
        super().__init__(parent)
        self._game = game
        self._rows: list[dict[int, object]] = []
        self._char_data: dict[str, dict] = {}

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

    def append_many(self, rows) -> None:
        """Append ``(char_id, char_data, is_new)`` tuples as one insertion.

        Batches arrive ten at a time from the loader; a single
        ``rowsInserted`` keeps the QML delegate churn (and the image
        re-evaluation it triggers) proportional to the batch, not the card.
        """
        rows = list(rows)
        if not rows:
            return
        start = len(self._rows)
        prepared = [self._make_row(*row) for row in rows]
        self.beginInsertRows(QModelIndex(), start, start + len(prepared) - 1)
        for (char_id, char_data, _is_new), row in zip(rows, prepared):
            self._char_data[char_id] = char_data
            self._rows.append(row)
        self.endInsertRows()

    def clear(self) -> None:
        """Drop every card (a reload rebuilds them from scratch)."""
        if not self._rows and not self._char_data:
            return
        self.beginResetModel()
        self._rows.clear()
        self._char_data.clear()
        self.endResetModel()

    # -- lookups -----------------------------------------------------------

    def char_data(self, char_id: str) -> dict | None:
        """Return the raw API payload for *char_id*, if it is loaded."""
        return self._char_data.get(char_id)

    def char_ids(self) -> list[str]:
        """Return the loaded character ids in display order."""
        return [row[self.CharIdRole] for row in self._rows]

    def _make_row(self, char_id, char_data, is_new) -> dict[int, object]:
        name = get_name(self._game, char_data, char_id)
        rarity = get_rarity(self._game, char_data)
        element = get_element(self._game, char_data)
        return {
            self.CharIdRole: char_id,
            self.FullNameRole: name,
            self.DisplayNameRole: display_name(name),
            self.RarityRole: f"{rarity}\u2605",
            self.RarityColorRole: RARITY_COLORS.get(str(rarity), ""),
            self.ElementRole: element or "Unknown Element",
            self.ElementTextRole: element[:1] if element else "?",
            self.ElementImageRole: get_element_image(self._game, char_data),
            self.SpecialtyRole: get_specialty(self._game, char_data),
            self.SpecialtyImageRole: get_specialty_image(self._game, char_data),
            self.ImageRole: get_character_image(self._game, char_data, char_id),
            self.UrlRole: get_character_url(self._game, char_id, char_data),
            self.IsNewRole: bool(is_new),
        }


class Section(QObject):
    """One game row: header state plus the character model of its cards."""

    statusChanged = Signal()
    versionsChanged = Signal()

    def __init__(self, game: str, name: str, parent: QObject | None = None):
        super().__init__(parent)
        self._game = game
        self._name = name
        self._status = "Loading..."
        self._live_version = ""
        self._latest_version = ""
        self._characters = CharacterModel(game, self)

    game = Property(str, lambda self: self._game, constant=True)
    name = Property(str, lambda self: self._name, constant=True)
    status = Property(str, lambda self: self._status, notify=statusChanged)
    liveVersion = Property(
        str, lambda self: self._live_version, notify=versionsChanged
    )
    latestVersion = Property(
        str, lambda self: self._latest_version, notify=versionsChanged
    )
    characters = Property(
        QObject, lambda self: self._characters, constant=True
    )

    def set_status(self, text: str) -> None:
        """Set the header status text ("Loading 20/90", "90 total", ...)."""
        if text == self._status:
            return
        self._status = text
        self.statusChanged.emit()

    def set_versions(self, live_version, latest_version) -> None:
        """Set the live/beta badges; empty values hide the badge."""
        live = live_version or ""
        latest = latest_version or ""
        if (live, latest) == (self._live_version, self._latest_version):
            return
        self._live_version = live
        self._latest_version = latest
        self.versionsChanged.emit()


class SectionsModel(QAbstractListModel):
    """The ordered list of :class:`Section` objects the root list renders."""

    SectionRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._sections: dict[str, Section] = {}
        self._order: list[str] = []

    # -- QAbstractListModel ------------------------------------------------

    def roleNames(self):
        return {self.SectionRole: QByteArray(b"section")}

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._order)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role != self.SectionRole or not index.isValid():
            return None
        row = index.row()
        if not 0 <= row < len(self._order):
            return None
        return self._sections[self._order[row]]

    # -- lookups -----------------------------------------------------------

    def section(self, game: str) -> Section | None:
        """Return the live section for *game*, or ``None`` if it is hidden."""
        return self._sections.get(game)

    def games(self) -> list[str]:
        """Return the visible game ids in display order."""
        return list(self._order)

    def sections(self) -> list[Section]:
        """Return the visible sections in display order."""
        return [self._sections[game] for game in self._order]

    # -- synchronisation ---------------------------------------------------

    def sync(self, games) -> bool:
        """Match the visible sections to *games*.

        Returns whether the *set* of games changed.  Reordering only moves
        existing sections, which must not trigger a reload; adding or
        removing a game does.
        """
        wanted = [game for game in games if game in GAMES]
        if wanted == self._order:
            return False

        previous = set(self._sections)
        removed = [
            section
            for game, section in self._sections.items()
            if game not in wanted
        ]

        self.beginResetModel()
        self._sections = {
            game: self._sections.get(game)
            or Section(game, GAMES[game]["name"], self)
            for game in wanted
        }
        self._order = wanted
        self.endResetModel()

        # The model no longer references removed sections; their C++ parents
        # would otherwise keep them (and their card models) alive forever.
        for section in removed:
            section.deleteLater()
        return set(wanted) != previous
