"""QML-facing state for the character details popup.

The popup keeps all of its loading behaviour in Python (worker threads, the
cache probes and the deferred-skeleton fallback timers), but it no longer
builds widgets: it fills this model and ``qml/details/DetailsPanel.qml`` binds
to it.  Keeping the state machine here means it stays testable without a QML
engine, exactly like the header state in ``main_window``.

Data is shaped for the QML tree rather than mirroring the API dataclasses:
stat pairs and build sections arrive pre-grouped into rows, because a QML
``Repeater`` inside a ``GridLayout`` can only contribute one item per entry.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from ..api.details import CharacterDetail

# Detail payload lifecycle.
STATE_IDLE = "idle"
STATE_LOADING = "loading"
STATE_READY = "ready"
STATE_ERROR = "error"

# Recommended-build card lifecycle.
BUILD_HIDDEN = "hidden"
BUILD_SKELETON = "skeleton"
BUILD_READY = "ready"

# Artwork column lifecycle.
ART_HIDDEN = "hidden"
ART_SKELETON = "skeleton"
ART_READY = "ready"
ART_UNAVAILABLE = "unavailable"

# Columns in the stats/build grids; rows are pre-grouped to match.
GRID_COLUMNS = 2


def _chunked(items: list, size: int) -> list[list]:
    """Split *items* into rows of at most *size* entries."""
    return [items[index : index + size] for index in range(0, len(items), size)]


class DetailsViewModel(QObject):
    """Everything the details panel renders, as QML-friendly properties."""

    stateChanged = Signal()
    contentChanged = Signal()
    buildChanged = Signal()
    artChanged = Signal()

    # Emitted by the QML buttons; the popup owns the actual behaviour.
    closeRequested = Signal()
    retryRequested = Signal()

    state = Property(str, lambda self: self._state, notify=stateChanged)
    errorMessage = Property(
        str, lambda self: self._error_message, notify=stateChanged
    )

    name = Property(str, lambda self: self._name, notify=contentChanged)
    badgesText = Property(
        str, lambda self: self._badges_text, notify=contentChanged
    )
    subtitle = Property(str, lambda self: self._subtitle, notify=contentChanged)
    overview = Property(str, lambda self: self._overview, notify=contentChanged)
    levelLabel = Property(
        str, lambda self: self._level_label, notify=contentChanged
    )
    hasOverview = Property(
        bool, lambda self: self._has_overview, notify=contentChanged
    )
    statRows = Property(
        "QVariantList", lambda self: self._stat_rows, notify=contentChanged
    )
    skills = Property(
        "QVariantList", lambda self: self._skills, notify=contentChanged
    )
    extras = Property(
        "QVariantList", lambda self: self._extras, notify=contentChanged
    )

    buildState = Property(
        str, lambda self: self._build_state, notify=buildChanged
    )
    buildRows = Property(
        "QVariantList", lambda self: self._build_rows, notify=buildChanged
    )

    artState = Property(str, lambda self: self._art_state, notify=artChanged)
    artSource = Property(str, lambda self: self._art_source, notify=artChanged)
    artFocusX = Property(
        float, lambda self: self._art_focus_x, notify=artChanged
    )
    artName = Property(str, lambda self: self._art_name, notify=artChanged)
    artMeta = Property(str, lambda self: self._art_meta, notify=artChanged)
    artMessage = Property(
        str, lambda self: self._art_message, notify=artChanged
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.reset()

    # -- payload -----------------------------------------------------------

    def reset(self):
        """Forget everything and go back to the idle state."""
        self._state = STATE_IDLE
        self._error_message = ""
        self._name = ""
        self._badges_text = ""
        self._subtitle = ""
        self._overview = ""
        self._level_label = ""
        self._has_overview = False
        self._stat_rows: list[list[dict]] = []
        self._skills: list[dict] = []
        self._extras: list[dict] = []
        self._build_state = BUILD_HIDDEN
        self._build_rows: list[list[dict]] = []
        self._art_state = ART_HIDDEN
        self._art_source = ""
        self._art_focus_x = 0.5
        self._art_name = ""
        self._art_meta = ""
        self._art_message = ""
        self.stateChanged.emit()
        self.contentChanged.emit()
        self.buildChanged.emit()
        self.artChanged.emit()

    def show_loading(self):
        """Show the loading screen: text skeleton plus the art placeholder."""
        self.reset()
        self._state = STATE_LOADING
        self._art_state = ART_SKELETON
        self.stateChanged.emit()
        self.artChanged.emit()

    def set_error(self, message: str):
        """Replace the content with the error card."""
        self.reset()
        self._state = STATE_ERROR
        self._error_message = message
        self._art_state = ART_UNAVAILABLE
        self._art_message = "Art unavailable"
        self.stateChanged.emit()
        self.artChanged.emit()

    def set_detail(self, detail: CharacterDetail):
        """Fill the content cards from a loaded *detail*."""
        badges = [badge for badge in detail.badges if badge]
        subtitle = " · ".join(
            part
            for part in detail.subtitle.split(" · ")
            if part and part not in detail.badges
        )

        self._state = STATE_READY
        self._error_message = ""
        self._name = detail.name
        self._badges_text = " · ".join(badges)
        self._subtitle = subtitle
        self._overview = detail.overview
        self._level_label = detail.level_label
        self._has_overview = bool(subtitle or detail.overview)
        self._stat_rows = _chunked(
            [{"label": label, "value": value} for label, value in detail.stats],
            GRID_COLUMNS,
        )
        self._skills = [
            {
                "title": f"{skill.name} · {skill.type_name} · Lv. {skill.level}",
                "description": skill.description,
                "multipliers": [
                    {"label": label, "value": value}
                    for label, value in skill.multipliers
                ],
            }
            for skill in detail.skills
        ]
        self._extras = [
            {
                "title": section.title,
                "entries": [
                    {"name": entry.name, "text": entry.text}
                    for entry in section.entries
                ],
            }
            for section in detail.extras
        ]

        # A payload that already carries its build needs no worker thread.
        self._build_rows = _chunked(
            [
                {"title": section.title, "items": list(section.items)}
                for section in detail.build
            ],
            GRID_COLUMNS,
        )
        self._build_state = BUILD_READY if self._build_rows else BUILD_HIDDEN

        self._art_name = detail.name
        self._art_meta = " · ".join(badges)
        if not detail.art_url:
            self._art_state = ART_UNAVAILABLE
            self._art_message = "Art unavailable"

        self.stateChanged.emit()
        self.contentChanged.emit()
        self.buildChanged.emit()
        self.artChanged.emit()

    # -- recommended build -------------------------------------------------

    def show_build_skeleton(self):
        """Reserve the build card's slot while its payload loads."""
        if self._build_state == BUILD_READY:
            return
        self._build_state = BUILD_SKELETON
        self.buildChanged.emit()

    def set_build(self, sections):
        """Render *sections*; an empty result removes the card entirely."""
        self._build_rows = _chunked(
            [
                {"title": section.title, "items": list(section.items)}
                for section in sections
            ],
            GRID_COLUMNS,
        )
        self._build_state = BUILD_READY if self._build_rows else BUILD_HIDDEN
        self.buildChanged.emit()

    def hide_build(self):
        """Drop the build card and its skeleton."""
        self._build_rows = []
        self._build_state = BUILD_HIDDEN
        self.buildChanged.emit()

    # -- artwork -----------------------------------------------------------

    def show_art_skeleton(self):
        """Show the full-column placeholder while the artwork loads."""
        if self._art_state in (ART_READY, ART_UNAVAILABLE):
            return
        self._art_state = ART_SKELETON
        self.artChanged.emit()

    def set_art(self, source: str, focus_x: float = 0.5):
        """Show the decoded artwork served by *source*.

        ``focus_x`` is the saliency centroid used as the horizontal crop
        centre (0.5 is the geometric centre).
        """
        self._art_source = source
        self._art_focus_x = min(1.0, max(0.0, float(focus_x)))
        self._art_state = ART_READY if source else ART_UNAVAILABLE
        self._art_message = "" if source else "Art unavailable"
        self.artChanged.emit()

    def set_art_unavailable(self, message: str = "Art unavailable"):
        """Drop the artwork and explain why the column is empty."""
        self._art_source = ""
        self._art_focus_x = 0.5
        self._art_state = ART_UNAVAILABLE
        self._art_message = message
        self.artChanged.emit()

    # -- actions -----------------------------------------------------------

    @Slot()
    def requestClose(self):  # noqa: N802 - QML calls this name
        """Ask the popup to close (QML Close button / retry flow)."""
        self.closeRequested.emit()

    @Slot()
    def requestRetry(self):  # noqa: N802 - QML calls this name
        """Ask the popup to reload the character (error card's Retry)."""
        self.retryRequested.emit()
