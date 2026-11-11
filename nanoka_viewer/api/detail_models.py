"""Normalized data structures shared by the detail loader and normalizers.

Keeping these in their own module lets the five game normalizers build the
same objects without importing the network/cache layer (which would be a
circular import).  :mod:`nanoka_viewer.api.details` re-exports every name here
so existing imports and pickled caches keep working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class DetailUnavailable(Exception):
    """Raised when nanoka has no detail page for a character yet."""


@dataclass
class BuildSection:
    """A group of compact recommended-build lines."""

    title: str
    items: list[str] = field(default_factory=list)


@dataclass
class SkillDetail:
    """A single skill with its max-level description and multipliers."""

    name: str
    type_name: str
    description: str
    multipliers: list[tuple[str, str]] = field(default_factory=list)
    level: int = 1


@dataclass
class ContentEntry:
    """A named passive, trace, constellation, or similar overview entry."""

    name: str
    text: str
    # Set for rule terms so a link in the text can navigate to this entry.
    term_id: str = ""


@dataclass
class ExtraSection:
    """A collapsed overview section such as passives or mindscapes."""

    title: str
    entries: list[ContentEntry] = field(default_factory=list)


@dataclass
class BuildContext:
    """Transient data needed to load a recommended build later."""

    game: str
    version: str
    raw: dict[str, Any] = field(repr=False, compare=False)


@dataclass
class CharacterDetail:
    """Normalized character detail data for the native popup."""

    game: str
    char_id: str
    name: str
    subtitle: str
    overview: str
    level_label: str
    badges: list[str] = field(default_factory=list)
    stats: list[tuple[str, str]] = field(default_factory=list)
    build: list[BuildSection] = field(default_factory=list)
    skills: list[SkillDetail] = field(default_factory=list)
    extras: list[ExtraSection] = field(default_factory=list)
    terms: list[ContentEntry] = field(default_factory=list)
    art_url: str = ""
    source_url: str = ""
    build_context: BuildContext | None = field(
        default=None, repr=False, compare=False
    )
