"""Character detail loading and normalization with in-memory caching.

The main character list is cached by :mod:`nanoka_viewer.api.characters`.
Character details and build metadata are cached in memory by (game, version,
char_id) so subsequent opens of viewed characters are near-instant and do not
hit the network.  Shift+Reload clears all caches including this in-memory
detail cache.

This module owns fetching, caching and cache probes.  The game-specific
normalizers live in :mod:`nanoka_viewer.api.detail_games`, the shared
dataclasses in :mod:`nanoka_viewer.api.detail_models`, and the text helpers in
:mod:`nanoka_viewer.api.detail_text`.
"""

from __future__ import annotations

import hashlib
import logging
import pickle
import random
import threading
import time
from pathlib import Path
from typing import Any

import requests

from .cache_info import (
    build_cache_last_cached,
    clear_build_cache_info,
    record_build_cache_write,
)
from .cache_io import directory_size_bytes, write_bytes_atomic
from .characters import cached_versions
from .constants import BASE_URL, CACHE_DIR
from .detail_games import gi as _gi
from .detail_games import ww as _ww
from .detail_games import zzz as _zzz
from .detail_games.hsr import build as _hsr_build
from .detail_games.ww import build as _ww_build
from .detail_games.zzz import build as _zzz_build
from .detail_models import (
    BuildContext,
    BuildSection,
    CharacterDetail,
    ContentEntry,
    DetailUnavailable,
    ExtraSection,
    SkillDetail,
)
from .detail_normalize import normalize as _normalize
from .detail_text import art_url as _art_url
from .detail_text import format_markup, plain_text  # noqa: F401 - re-exported
from .http import session as _session
from .manifest import cached_latest_version, get_latest_version
from .models import get_character_url
from ..settings import get_setting

DETAIL_CACHE_DIR = CACHE_DIR / "details"
DETAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

METADATA_CACHE_DIR = CACHE_DIR / "details_metadata"
METADATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

DETAIL_ART_CACHE_DIR = CACHE_DIR / "details_art"
DETAIL_ART_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory caches.  These are always used for the current session; the settings
# below decide whether the same data is also persisted to disk.
_detail_cache: dict[tuple[str, str, str], CharacterDetail] = {}
_metadata_cache: dict[tuple[str, str, str], Any] = {}
_art_cache: dict[str, bytes] = {}

logger = logging.getLogger(__name__)

_DETAIL_TIMEOUT = 25

# Bulk preloads share these caches from several threads.
_METADATA_LOCK = threading.Lock()

# Retry only transient failures.  A 404 (not-yet-published character) must
# reach the caller immediately so it can be reported as unavailable.
_MAX_ATTEMPTS = 4
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_BACKOFF_BASE = 0.5
_BACKOFF_CAP = 8.0


def clear_detail_cache():
    """Clear in-memory and disk cached character details, metadata, and artwork."""
    global _detail_cache, _metadata_cache, _art_cache
    _detail_cache.clear()
    _metadata_cache.clear()
    _art_cache.clear()

    for directory in (DETAIL_CACHE_DIR, METADATA_CACHE_DIR, DETAIL_ART_CACHE_DIR):
        try:
            if directory.exists():
                for item in directory.iterdir():
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        import shutil

                        shutil.rmtree(item)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not clear cache directory %s: %s", directory, exc)

    clear_build_cache_info()
    logger.info("Character detail, metadata, and artwork cache cleared")


def cache_sizes() -> dict[str, int]:
    """Return the on-disk size in bytes of each cache shown in settings."""
    return {
        "details": directory_size_bytes(DETAIL_CACHE_DIR),
        "builds": directory_size_bytes(METADATA_CACHE_DIR),
        "artwork": directory_size_bytes(DETAIL_ART_CACHE_DIR),
    }


# ---------------------------------------------------------------------------
# Network helpers


def _retry_delay(attempt: int, response: requests.Response | None = None) -> float:
    """Return an exponential backoff delay, honouring ``Retry-After``."""
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, min(60.0, float(retry_after)))
            except (TypeError, ValueError):
                pass
    delay = min(_BACKOFF_CAP, _BACKOFF_BASE * (2**attempt))
    return delay + random.uniform(0.0, 0.25)


def _request_with_retries(
    url: str, headers: dict[str, str] | None = None
) -> requests.Response:
    """GET *url*, retrying transient failures with exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = _session.get(
                url, timeout=_DETAIL_TIMEOUT, headers=headers
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = exc
            if attempt + 1 >= _MAX_ATTEMPTS:
                raise
            delay = _retry_delay(attempt)
            logger.warning(
                "Retrying %s in %.1fs after %s (attempt %d/%d)",
                url,
                delay,
                exc,
                attempt + 1,
                _MAX_ATTEMPTS,
            )
            time.sleep(delay)
            continue

        if response.status_code in _RETRYABLE_STATUS:
            if attempt + 1 >= _MAX_ATTEMPTS:
                response.raise_for_status()
            delay = _retry_delay(attempt, response)
            logger.warning(
                "Retrying %s in %.1fs after HTTP %s (attempt %d/%d)",
                url,
                delay,
                response.status_code,
                attempt + 1,
                _MAX_ATTEMPTS,
            )
            response.close()
            time.sleep(delay)
            continue

        return response

    if last_error is not None:
        raise last_error
    raise requests.RequestException(f"Could not fetch {url}")


def _get_json(url: str) -> Any:
    response = _request_with_retries(url)
    response.raise_for_status()
    return response.json()


def _get_json_with_etag(
    url: str, headers: dict[str, str] | None = None
) -> tuple[Any, str | None]:
    """GET JSON and return its payload together with the response ETag."""
    response = _request_with_retries(url, headers=headers)
    response.raise_for_status()
    return response.json(), response.headers.get("ETag")


def _get_bytes(url: str) -> bytes | None:
    if not url:
        return None
    try:
        response = _request_with_retries(url)
        response.raise_for_status()
        return response.content
    except Exception as exc:  # noqa: BLE001 - art is optional
        logger.warning("Could not fetch character art %s: %s", url, exc)
        return None


def _art_disk_path(url: str) -> Path:
    digest = hashlib.md5(url.encode()).hexdigest()
    return DETAIL_ART_CACHE_DIR / f"{digest}.bin"


def load_character_art(url: str, *, remember: bool = True) -> bytes | None:
    """Fetch character art separately so text never waits for the image.

    Artwork is cached in memory for the current session unless *remember* is
    false.  Bulk preloads turn that off so they do not pin every character's
    artwork in RAM.  Disk caching is controlled by the
    ``cache_character_artwork`` setting.
    """
    if not url:
        return None

    caching = get_setting("cache_character_artwork")
    cache_file = _art_disk_path(url)

    if remember and url in _art_cache:
        return _art_cache[url]

    if caching and cache_file.exists():
        try:
            data = cache_file.read_bytes()
            if remember:
                _art_cache[url] = data
            return data
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read cached artwork %s: %s", cache_file, exc)

    data = _get_bytes(url)
    if data is not None:
        if remember:
            _art_cache[url] = data
        if caching:
            try:
                write_bytes_atomic(cache_file, data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not write cached artwork %s: %s", cache_file, exc)
    return data


def _latest_version(game: str) -> str:
    """Resolve the current latest version without using a detail cache."""
    try:
        manifest = _get_json(f"{BASE_URL}/manifest.json")
        return str(manifest[game]["latest"])
    except Exception as exc:  # noqa: BLE001 - fall back to the app's manifest
        logger.warning("Could not fetch a fresh manifest: %s", exc)
        return str(get_latest_version(game))


def _metadata_disk_path(cache_key: tuple[str, str, str]) -> Path:
    game, version, resource_name = cache_key
    digest = hashlib.sha256(f"{game}:{version}:{resource_name}".encode()).hexdigest()
    return METADATA_CACHE_DIR / f"{digest}.pkl"


def _metadata_etag_path(cache_key: tuple[str, str, str]) -> Path:
    return _metadata_disk_path(cache_key).with_suffix(".etag")


def _read_metadata_etag(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _write_metadata_etag(path: Path, etag: str | None) -> None:
    try:
        if etag:
            write_bytes_atomic(path, etag.encode("utf-8"))
        else:
            path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not write cache ETag %s: %s", path, exc)


def _load_metadata_pickle(path: Path) -> Any | None:
    try:
        with path.open("rb") as handle:
            return pickle.load(handle)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read cached metadata %s: %s", path, exc)
        try:
            path.unlink()
        except OSError:
            pass
        return None


def _save_metadata(
    disk_path: Path, etag_path: Path, data: Any, etag: str | None
) -> None:
    write_bytes_atomic(disk_path, pickle.dumps(data))
    _write_metadata_etag(etag_path, etag)


def reset_build_cache() -> None:
    """Drop build tables from memory so a refresh revalidates every table."""
    _metadata_cache.clear()


def _fetch_metadata_file(
    game: str,
    version: str,
    resource_name: str,
    url: str,
    *,
    refresh: bool = False,
    record: bool = True,
) -> Any:
    cache_key = (game, version, resource_name)
    # Build tables change with each live version, so they keep their own
    # setting (and their own last-cached metadata) separate from detail text.
    # Serialise the cache check + fetch so concurrent build preloads do not
    # download the same shared table more than once.
    with _METADATA_LOCK:
        caching = get_setting("cache_character_builds")
        disk_path = _metadata_disk_path(cache_key)
        etag_path = _metadata_etag_path(cache_key)

        if not refresh and cache_key in _metadata_cache:
            return _metadata_cache[cache_key]

        if refresh and caching and disk_path.exists():
            etag = _read_metadata_etag(etag_path)
            if etag:
                try:
                    response = _request_with_retries(
                        url, headers={"If-None-Match": etag}
                    )
                    if response.status_code == 304:
                        response.close()
                        data = _load_metadata_pickle(disk_path)
                        if data is not None:
                            _metadata_cache[cache_key] = data
                            return data
                    else:
                        response.raise_for_status()
                        data = response.json()
                        new_etag = response.headers.get("ETag")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Could not revalidate build metadata %s: %s", url, exc
                    )
                else:
                    if data is not None:
                        _metadata_cache[cache_key] = data
                        try:
                            _save_metadata(
                                disk_path, etag_path, data, new_etag
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(
                                "Could not write cached metadata %s: %s",
                                disk_path,
                                exc,
                            )
                        else:
                            if record:
                                record_build_cache_write()
                        return data

        if not refresh and caching and disk_path.exists():
            data = _load_metadata_pickle(disk_path)
            if data is not None:
                _metadata_cache[cache_key] = data
                if record and build_cache_last_cached() <= 0:
                    # Backfill metadata for caches written before the
                    # last-cached record existed.
                    try:
                        record_build_cache_write(
                            timestamp=disk_path.stat().st_mtime
                        )
                    except OSError:
                        pass
                return data

        try:
            data, etag = _get_json_with_etag(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch detail metadata %s: %s", url, exc)
            return None

        _metadata_cache[cache_key] = data
        if caching:
            try:
                _save_metadata(disk_path, etag_path, data, etag)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not write cached metadata %s: %s", disk_path, exc)
            else:
                if record:
                    record_build_cache_write()
        return data


def _build_metadata_specs(game: str, version: str) -> list[tuple[str, str]]:
    """Return the shared build-table resources for *game*/*version*."""
    if game == "hsr":
        return [
            ("relicset", f"{BASE_URL}/hsr/{version}/relicset.json"),
            ("lightcone", f"{BASE_URL}/hsr/{version}/lightcone.json"),
            ("character", f"{BASE_URL}/hsr/{version}/character.json"),
        ]
    if game == "ww":
        return [("weapon", f"{BASE_URL}/ww/{version}/weapon.json")]
    if game == "zzz":
        return [("item", f"{BASE_URL}/zzz/{version}/en/item.json")]
    return []


def _fetch_metadata(game: str, version: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Fetch only the small metadata files needed for a recommended build."""
    specs = dict(_build_metadata_specs(game, version))
    if game == "hsr" and any(
        raw.get(key) for key in ("relics", "lightcones", "teams")
    ):
        return {
            "relicset": _fetch_metadata_file(game, version, "relicset", specs["relicset"]),
            "lightcone": _fetch_metadata_file(game, version, "lightcone", specs["lightcone"]),
            "characters": _fetch_metadata_file(game, version, "character", specs["character"]),
        }
    if game == "ww" and (raw.get("recommend") or {}).get("weapon"):
        return {
            "weapon": _fetch_metadata_file(
                game, version, "weapon", specs["weapon"]
            )
        }
    if game == "zzz" and raw.get("fairy_recommend"):
        return {
            "item": _fetch_metadata_file(game, version, "item", specs["item"])
        }
    return {}


def _fetch_detail_text_metadata(
    game: str, version: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Fetch shared text tables the detail normalizer needs.

    Genshin, Wuthering Waves and ZZZ keep rule-term names and descriptions in
    a per-version table rather than inside each character payload.  NTE embeds
    them in the payload itself, so it needs no extra request.
    """
    if game == "gi":
        term_ids = _gi.linked_term_ids(raw)
        resource, filename = "hyperlink", "hyperlink.json"
    elif game == "ww":
        term_ids = _ww.linked_term_ids(raw)
        resource, filename = "hyperlink", "hyperlink.json"
    elif game == "zzz":
        term_ids = _zzz.linked_term_ids(raw)
        resource, filename = "noun", "noun.json"
    else:
        return {}
    if not term_ids:
        return {}
    table = _fetch_metadata_file(
        game,
        version,
        resource,
        f"{BASE_URL}/{game}/{version}/en/{filename}",
        record=False,
    )
    return {"terms": table or {}}


def prefetch_build_metadata(
    game: str, version: str, *, refresh: bool = False
) -> tuple[int, int]:
    """Warm a game version's shared build tables without scanning characters.

    Recommended builds all read from the same per-version tables, so a bulk
    preload only needs these few files.  With *refresh* the tables are
    revalidated with their stored ETags, so unchanged tables cost a 304
    instead of a full download.  Returns ``(fetched, expected)``; GI and NTE
    have no build tables.
    """
    specs = _build_metadata_specs(game, version)
    fetched = 0
    for resource_name, url in specs:
        if (
            _fetch_metadata_file(
                game, version, resource_name, url, refresh=refresh
            )
            is not None
        ):
            fetched += 1
    return fetched, len(specs)


def _detail_disk_path(cache_key: tuple[str, str, str]) -> Path:
    game, version, char_id = cache_key
    digest = hashlib.sha256(f"{game}:{version}:{char_id}".encode()).hexdigest()
    return DETAIL_CACHE_DIR / f"{digest}.pkl"


def _detail_url(game: str, version: str, char_id: str) -> str:
    return f"{BASE_URL}/{game}/{version}/en/character/{char_id}.json"


def _read_cached_detail(
    cache_key: tuple[str, str, str], *, remember: bool
) -> CharacterDetail | None:
    """Load one detail payload from disk, dropping it when it is corrupt.

    The returned object is treated as immutable after construction: the UI
    model and the build loader only read it, so warm cache hits hand out the
    cached instance instead of deep-copying the whole raw payload.
    """
    disk_path = _detail_disk_path(cache_key)
    if not disk_path.exists():
        return None
    try:
        with disk_path.open("rb") as handle:
            detail = pickle.load(handle)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read cached detail %s: %s", disk_path, exc)
        try:
            disk_path.unlink()
        except OSError:
            pass
        return None
    if remember:
        _detail_cache[cache_key] = detail
    return detail


def _cached_detail_other_version(
    game: str, char_id: str, skip_version: str = "", *, remember: bool = False
) -> CharacterDetail | None:
    """Return a detail cached under another game version, newest first.

    Offline, the manifest may already name a version we never downloaded while
    the text for the previous version is still on disk.  Showing that is better
    than an error screen; the payload keeps its own build context, so the
    recommended build stays consistent with the detail text.
    """
    if not get_setting("cache_character_details"):
        return None
    for version in cached_versions(game):
        if version == skip_version:
            continue
        detail = _read_cached_detail(
            (game, version, str(char_id)), remember=remember
        )
        if detail is not None:
            logger.warning(
                "Using cached detail for %s %s from version %s "
                "after a connection failure",
                game,
                char_id,
                version,
            )
            return detail
    return None


def load_character_detail(
    game: str, char_id: str, *, remember: bool = True
) -> CharacterDetail:
    """Fetch and normalize a character's detail page without build data.

    The cached manifest version is used first, so text appears immediately.
    If that version has gone stale, the fresh manifest is fetched once and the
    detail request is retried.  Results are cached in memory by (game, version,
    char_id) unless *remember* is false; bulk preloads use that to write the
    disk cache without keeping every raw payload in memory.

    When the network is unavailable, a payload cached for an older version of
    the same game is served instead of failing.
    """
    try:
        version = str(get_latest_version(game))
    except Exception as exc:  # noqa: BLE001 - a fresh manifest may still work
        logger.warning("Could not read the cached manifest: %s", exc)
        try:
            version = _latest_version(game)
        except Exception as fresh_exc:  # noqa: BLE001
            cached = _cached_detail_other_version(game, char_id, remember=remember)
            if cached is not None:
                return cached
            if isinstance(fresh_exc, requests.RequestException):
                raise DetailUnavailable(
                    "Could not reach nanoka.cc. Check your connection."
                ) from fresh_exc
            raise

    cache_key = (game, version, str(char_id))
    caching = get_setting("cache_character_details")

    if remember and cache_key in _detail_cache:
        logger.debug("Using cached character detail for %s %s (version %s)", game, char_id, version)
        return _detail_cache[cache_key]

    if caching:
        detail = _read_cached_detail(cache_key, remember=remember)
        if detail is not None:
            return detail

    try:
        raw = _get_json(_detail_url(game, version, char_id))
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        fresh_version = _latest_version(game)
        if fresh_version == version:
            raise DetailUnavailable(
                "Details are not available for this character yet."
            ) from exc
        version = fresh_version
        cache_key = (game, version, str(char_id))
        caching = get_setting("cache_character_details")

        if remember and cache_key in _detail_cache:
            return _detail_cache[cache_key]

        if caching:
            detail = _read_cached_detail(cache_key, remember=remember)
            if detail is not None:
                return detail
        try:
            raw = _get_json(_detail_url(game, version, char_id))
        except requests.HTTPError as retry_exc:
            if retry_exc.response is not None and retry_exc.response.status_code == 404:
                raise DetailUnavailable(
                    "Details are not available for this character yet."
                ) from retry_exc
            raise
        except requests.RequestException as retry_exc:
            cached = _cached_detail_other_version(
                game, char_id, version, remember=remember
            )
            if cached is not None:
                return cached
            raise DetailUnavailable(
                "Could not reach nanoka.cc. Check your connection."
            ) from retry_exc
    except requests.RequestException as exc:
        cached = _cached_detail_other_version(
            game, char_id, version, remember=remember
        )
        if cached is not None:
            return cached
        raise DetailUnavailable(
            "Could not reach nanoka.cc. Check your connection."
        ) from exc

    detail = _normalize(
        game,
        char_id,
        raw,
        _fetch_detail_text_metadata(game, version, raw),
        with_build=False,
    )
    detail.art_url = _art_url(game, char_id, raw)
    detail.source_url = get_character_url(game, char_id, raw)

    has_build = (
        (
            game == "hsr"
            and any(raw.get(key) for key in ("relics", "lightcones", "teams"))
        )
        or (game == "ww" and bool((raw.get("recommend") or {}).get("weapon")))
        or (game == "zzz" and bool(raw.get("fairy_recommend")))
    )
    if has_build:
        detail.build_context = BuildContext(game, version, raw)

    if caching:
        disk_path = _detail_disk_path(cache_key)
        try:
            write_bytes_atomic(disk_path, pickle.dumps(detail))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not write cached detail %s: %s", disk_path, exc)
    if remember:
        _detail_cache[cache_key] = detail
    return detail


def load_character_build(detail: CharacterDetail) -> list[BuildSection]:
    """Fetch only the metadata needed for a character's recommended build.

    This is intentionally separate from :func:`load_character_detail` so the
    core text and art can render while build metadata is still downloading.
    """
    context = detail.build_context
    if context is None:
        return []

    metadata = _fetch_metadata(context.game, context.version, context.raw)
    if context.game == "hsr":
        return _hsr_build(context.raw, metadata)
    if context.game == "ww":
        return _ww_build(context.raw, metadata)
    if context.game == "zzz":
        return _zzz_build(context.raw, metadata)
    return []


# ---------------------------------------------------------------------------
# Cache probes (never touch the network)
#
# The details popup uses these to decide whether the loader will be answered
# from a warm cache.  They mirror the settings checks and disk layouts of the
# matching loaders, so a probe hit means the loader can render without a
# skeleton screen.


def has_cached_detail(game: str, char_id: str) -> bool:
    """Return whether the detail text can be served from cache."""
    version = cached_latest_version(game)
    if version is None:
        return False
    cache_key = (game, version, str(char_id))
    if cache_key in _detail_cache:
        return True
    return bool(
        get_setting("cache_character_details")
        and _detail_disk_path(cache_key).exists()
    )


def _required_build_resources(context: BuildContext) -> tuple[str, ...]:
    raw = context.raw
    if context.game == "hsr":
        if any(raw.get(key) for key in ("relics", "lightcones", "teams")):
            return ("relicset", "lightcone", "character")
        return ()
    if context.game == "ww":
        return ("weapon",) if (raw.get("recommend") or {}).get("weapon") else ()
    if context.game == "zzz":
        return ("item",) if raw.get("fairy_recommend") else ()
    return ()


def has_cached_build(detail: CharacterDetail) -> bool:
    """Return whether the recommended build can be served from cache.

    A detail without a build section has nothing to wait for, so it counts as
    cached.
    """
    context = detail.build_context
    if context is None:
        return True

    resources = _required_build_resources(context)
    if not resources:
        return True

    caching = get_setting("cache_character_builds")
    for resource in resources:
        cache_key = (context.game, context.version, resource)
        if cache_key in _metadata_cache:
            continue
        if caching and _metadata_disk_path(cache_key).exists():
            continue
        return False
    return True


def has_cached_art(url: str) -> bool:
    """Return whether character artwork can be served from cache."""
    if not url:
        return False
    if url in _art_cache:
        return True
    return bool(
        get_setting("cache_character_artwork") and _art_disk_path(url).exists()
    )


def _art_url(game: str, char_id: str, raw: dict[str, Any]) -> str:
    if game == "hsr":
        return f"{BASE_URL}/assets/hsr/avatardrawcard/{char_id}.webp"
    if game == "gi":
        icon = str(raw.get("icon", ""))
        if icon.startswith("UI_AvatarIcon_"):
            suffix = icon.removeprefix("UI_AvatarIcon_")
            return f"{BASE_URL}/assets/gi/UI_Gacha_AvatarImg_{suffix}.webp"
        return f"{BASE_URL}/assets/gi/{icon}.webp"
    if game == "ww":
        background = str(raw.get("background") or raw.get("background_stand") or raw.get("icon") or "")
        path = background.replace("/Game/Aki/UI/", "").split(".")[0]
        path = path.removeprefix("/")
        return f"{BASE_URL}/assets/ww/{path}.webp"
    if game == "zzz":
        return f"{BASE_URL}/assets/zzz/{raw.get('icon', '')}.webp"
    if game == "nte":
        icon = str(raw.get("icon_gacha") or raw.get("icon") or "")
        if not icon.startswith("/"):
            icon = "/" + icon
        return f"{BASE_URL}/assets/nte{icon}.webp"
    return ""
