"""Bulk cache preloading for character details, builds, and artwork.

The details popup already caches everything it touches.  This module lets the
settings dialog deliberately warm those caches for every character instead of
waiting for the user to open each character once.

Three kinds of preload are supported:

``details``
    Character detail text (overview, stats, skills, and extras).
``builds``
    The per-version build metadata files used for recommended builds.  These
    change with every live game release, so they are kept separate.
``artwork``
    The large character artwork images shown in the details sidebar.

The work is sequential and synchronous.  The UI runs it on a background
thread, which keeps the network polite and makes cancellation land between
characters rather than in the middle of a write.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from .cache_info import record_build_cache_snapshot
from .characters import fetch_characters
from .constants import GAMES
from .details import (
    DetailUnavailable,
    load_character_art,
    load_character_build,
    load_character_detail,
)

logger = logging.getLogger(__name__)

PRELOAD_DETAILS = "details"
PRELOAD_BUILDS = "builds"
PRELOAD_ARTWORK = "artwork"
PRELOAD_KINDS = (PRELOAD_DETAILS, PRELOAD_BUILDS, PRELOAD_ARTWORK)


@dataclass(frozen=True)
class PreloadProgress:
    """One progress update emitted while a preload is running."""

    kind: str
    completed: int = 0
    total: int = 0
    game: str = ""
    name: str = ""
    failed: int = 0
    skipped: int = 0
    cancelled: bool = False


@dataclass
class PreloadSummary:
    """Final result of a preload run."""

    kind: str
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    failed_games: int = 0
    cancelled: bool = False


ProgressCallback = Callable[[PreloadProgress], None]
StopCallback = Callable[[], bool]


def _character_ids(game: str) -> list[str]:
    """Return every character id the UI actually shows for *game*."""
    ids = [str(char_id) for char_id in fetch_characters(game)]
    if game == "gi":
        # Keep the preload in sync with get_all_characters_with_new_status(),
        # which hides the Manekina/Manekin variants from the card list.
        ids = [
            char_id
            for char_id in ids
            if not char_id.startswith("10000118-")
            and not char_id.startswith("10000117-")
        ]
    return ids


def _collect_jobs() -> tuple[list[tuple[str, str]], int]:
    """Collect ``(game, character_id)`` pairs and the failed-game count."""
    jobs: list[tuple[str, str]] = []
    failed_games = 0
    for game in GAMES:
        try:
            ids = _character_ids(game)
        except Exception as exc:  # noqa: BLE001 - one game must not block the rest
            logger.warning("Could not list characters for %s: %s", game, exc)
            failed_games += 1
            continue
        jobs.extend((game, char_id) for char_id in ids)
        logger.info("Preload found %d characters for %s", len(ids), game)

    if not jobs and failed_games:
        raise RuntimeError(
            "Could not load the character list for any game. Check your connection."
        )
    return jobs, failed_games


def _emit(
    callback: ProgressCallback | None,
    progress: PreloadProgress,
) -> None:
    if callback is not None:
        try:
            callback(progress)
        except Exception:  # noqa: BLE001 - a listener must not abort the preload
            logger.exception("Preload progress callback failed")


def _store_details(game: str, char_id: str) -> tuple[int, int, str]:
    """Cache character detail text.  Returns ``(failed, skipped, name)``."""
    try:
        detail = load_character_detail(game, char_id, remember=False)
    except DetailUnavailable:
        return 0, 1, char_id
    except Exception:  # noqa: BLE001 - keep going through the rest of the list
        logger.exception("Preload could not cache detail %s/%s", game, char_id)
        return 1, 0, char_id
    return 0, 0, detail.name


def _store_builds(game: str, char_id: str) -> tuple[int, int, str]:
    """Cache recommended-build metadata.  Returns ``(failed, skipped, name)``."""
    try:
        detail = load_character_detail(game, char_id, remember=False)
    except DetailUnavailable:
        return 0, 1, char_id
    except Exception:  # noqa: BLE001
        logger.exception("Preload could not resolve build data for %s/%s", game, char_id)
        return 1, 0, char_id

    if detail.build_context is None:
        # GI and NTE have no recommended-build payload; other games may not
        # have published one for a brand-new character yet.
        return 0, 1, detail.name

    try:
        load_character_build(detail)
    except Exception:  # noqa: BLE001 - keep going through the rest of the list
        logger.exception("Preload could not cache build %s/%s", game, char_id)
        return 1, 0, detail.name
    return 0, 0, detail.name


def _store_artwork(game: str, char_id: str) -> tuple[int, int, str]:
    """Cache the details artwork.  Returns ``(failed, skipped, name)``."""
    try:
        detail = load_character_detail(game, char_id, remember=False)
    except DetailUnavailable:
        return 0, 1, char_id
    except Exception:  # noqa: BLE001
        logger.exception("Preload could not resolve artwork for %s/%s", game, char_id)
        return 1, 0, char_id

    if not detail.art_url:
        return 0, 1, detail.name

    try:
        data = load_character_art(detail.art_url, remember=False)
    except Exception:  # noqa: BLE001
        logger.exception("Preload could not cache artwork for %s/%s", game, char_id)
        return 1, 0, detail.name
    if data is None:
        return 1, 0, detail.name
    return 0, 0, detail.name


def preload_characters(
    kind: str,
    on_progress: ProgressCallback | None = None,
    should_stop: StopCallback | None = None,
) -> PreloadSummary:
    """Warm the detail or artwork cache for every character.

    *should_stop* is polled before each character, so cancellation is
    immediate from the UI's point of view and never interrupts a write.
    """
    if kind not in PRELOAD_KINDS:
        raise ValueError(f"Unknown preload kind: {kind!r}")

    stop = should_stop or (lambda: False)
    summary = PreloadSummary(kind=kind)
    jobs, summary.failed_games = _collect_jobs()
    summary.total = len(jobs)
    _emit(
        on_progress,
        PreloadProgress(
            kind=kind,
            completed=0,
            total=summary.total,
        ),
    )

    for index, (game, char_id) in enumerate(jobs, start=1):
        if stop():
            summary.cancelled = True
            break

        if kind == PRELOAD_DETAILS:
            failed, skipped, name = _store_details(game, char_id)
        elif kind == PRELOAD_BUILDS:
            failed, skipped, name = _store_builds(game, char_id)
        else:
            failed, skipped, name = _store_artwork(game, char_id)
        summary.failed += failed
        summary.skipped += skipped
        summary.completed = index

        _emit(
            on_progress,
            PreloadProgress(
                kind=kind,
                completed=index,
                total=summary.total,
                game=game,
                name=name,
                failed=summary.failed,
                skipped=summary.skipped,
            ),
        )

    cached = summary.completed - summary.failed - summary.skipped
    if kind == PRELOAD_BUILDS and cached > 0 and not summary.cancelled:
        # Record every game's live/latest version, even the ones with no build
        # payload, so the settings info icon can explain the cache's age.  A
        # cancelled run keeps the per-game entries written with each metadata
        # file instead of claiming an untouched game was cached.
        record_build_cache_snapshot()

    logger.info(
        "Preload %s finished: %d/%d completed, %d failed, %d skipped%s",
        kind,
        summary.completed,
        summary.total,
        summary.failed,
        summary.skipped,
        " (cancelled)" if summary.cancelled else "",
    )
    return summary
