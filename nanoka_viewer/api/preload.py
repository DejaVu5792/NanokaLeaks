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

The work runs on a small daemon worker pool.  The pool is deliberately
bounded: testing showed that a handful of parallel requests is much faster
than sequential fetches, while too many connections regress.  The details HTTP
layer adds exponential backoff for transient failures.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable

from .cache_info import record_build_cache_write
from .characters import fetch_characters
from .constants import GAMES
from .details import (
    DetailUnavailable,
    load_character_art,
    load_character_detail,
    prefetch_build_metadata,
    reset_build_cache,
)
from .manifest import get_latest_version

logger = logging.getLogger(__name__)

PRELOAD_DETAILS = "details"
PRELOAD_BUILDS = "builds"
PRELOAD_ARTWORK = "artwork"
PRELOAD_KINDS = (PRELOAD_DETAILS, PRELOAD_BUILDS, PRELOAD_ARTWORK)

# The static host is happy with a handful of parallel requests, but 16 workers
# measurably regressed in testing.  Artwork uses fewer workers because each
# response is much larger.
PRELOAD_MAX_WORKERS = 8
PRELOAD_ARTWORK_WORKERS = 4


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


def _worker_count(kind: str) -> int:
    return PRELOAD_ARTWORK_WORKERS if kind == PRELOAD_ARTWORK else PRELOAD_MAX_WORKERS


def _store_job(kind: str, game: str, char_id: str) -> tuple[int, int, str]:
    if kind == PRELOAD_DETAILS:
        return _store_details(game, char_id)
    return _store_artwork(game, char_id)


def _run_jobs(
    kind: str,
    jobs: list[tuple[str, str]],
    worker_count: int,
    on_result: Callable[[tuple[str, str], tuple[int, int, str]], None],
    should_stop: StopCallback,
) -> bool:
    """Run *jobs* on daemon workers and return whether cancellation was hit.

    Workers are daemons so quitting the app never waits for an in-flight
    preload.  The main loop owns all summary/progress updates, which keeps
    callbacks on one thread.
    """
    if not jobs:
        return False

    work: queue.Queue[tuple[str, str]] = queue.Queue()
    for job in jobs:
        work.put(job)
    results: queue.Queue[tuple[tuple[str, str], tuple[int, int, str]]] = queue.Queue()
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            try:
                job = work.get_nowait()
            except queue.Empty:
                return
            game, char_id = job
            try:
                result = _store_job(kind, game, char_id)
            except Exception:  # noqa: BLE001 - one job must not kill the pool
                logger.exception("Preload worker failed for %s/%s", game, char_id)
                result = (1, 0, char_id)
            results.put((job, result))

    threads = [
        threading.Thread(
            target=worker,
            name=f"nanoka-preload-{kind}-{index}",
            daemon=True,
        )
        for index in range(max(1, min(worker_count, len(jobs))))
    ]
    for thread in threads:
        thread.start()

    cancelled = False
    completed = 0
    while True:
        if not cancelled and should_stop():
            cancelled = True
            stop.set()

        try:
            job, result = results.get(timeout=0.1)
        except queue.Empty:
            if not any(thread.is_alive() for thread in threads):
                break
            continue

        completed += 1
        on_result(job, result)
        if completed >= len(jobs):
            break

    stop.set()
    for thread in threads:
        thread.join(timeout=0.1)
    return cancelled


def _preload_builds(
    on_progress: ProgressCallback | None,
    should_stop: StopCallback,
) -> PreloadSummary:
    """Warm the shared build tables once per game version.

    Character builds all read the same per-version tables, so there is no need
    to fetch every character detail page just to discover them.
    """
    summary = PreloadSummary(kind=PRELOAD_BUILDS)
    games = list(GAMES)
    summary.total = len(games)
    _emit(
        on_progress,
        PreloadProgress(kind=PRELOAD_BUILDS, completed=0, total=summary.total),
    )

    # Build tables are volatile, so always revalidate instead of trusting the
    # in-memory copy.  Disk files and ETags stay in place so unchanged tables
    # can answer with a 304 rather than being downloaded again.
    reset_build_cache()

    any_current = False
    for index, game in enumerate(games, start=1):
        if should_stop():
            summary.cancelled = True
            break

        try:
            version = str(get_latest_version(game))
        except Exception:  # noqa: BLE001 - one game must not block the rest
            logger.exception("Preload could not read the latest version for %s", game)
            summary.failed += 1
        else:
            fetched, expected = prefetch_build_metadata(
                game, version, refresh=True
            )
            if expected == 0:
                # GI and NTE do not publish recommended-build tables.
                summary.skipped += 1
            elif fetched > 0:
                any_current = True
                if fetched < expected:
                    summary.failed += 1
            else:
                summary.failed += 1

        summary.completed = index
        _emit(
            on_progress,
            PreloadProgress(
                kind=PRELOAD_BUILDS,
                completed=index,
                total=summary.total,
                game=game,
                name=GAMES[game]["name"],
                failed=summary.failed,
                skipped=summary.skipped,
            ),
        )

    if any_current and not summary.cancelled:
        record_build_cache_write()
    return summary


def preload_characters(
    kind: str,
    on_progress: ProgressCallback | None = None,
    should_stop: StopCallback | None = None,
) -> PreloadSummary:
    """Warm the detail, build, or artwork cache for every character.

    *should_stop* is polled while jobs are in flight.  Workers stop taking new
    jobs and the already-running batch is allowed to finish, so a cancelled
    run never interrupts a cache write.
    """
    if kind not in PRELOAD_KINDS:
        raise ValueError(f"Unknown preload kind: {kind!r}")

    stop = should_stop or (lambda: False)
    if kind == PRELOAD_BUILDS:
        return _preload_builds(on_progress, stop)

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

    def on_result(
        job: tuple[str, str], result: tuple[int, int, str]
    ) -> None:
        game, _char_id = job
        failed, skipped, name = result
        summary.failed += failed
        summary.skipped += skipped
        summary.completed += 1
        _emit(
            on_progress,
            PreloadProgress(
                kind=kind,
                completed=summary.completed,
                total=summary.total,
                game=game,
                name=name,
                failed=summary.failed,
                skipped=summary.skipped,
            ),
        )

    summary.cancelled = _run_jobs(
        kind,
        jobs,
        _worker_count(kind),
        on_result,
        stop,
    )

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
