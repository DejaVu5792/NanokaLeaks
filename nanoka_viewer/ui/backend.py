"""QML backend bridge for the Nanoka Viewer."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import (
    Property, QObject, QTimer, Signal, Slot,
)

from ..api import (
    GAMES,
    fetch_manifest,
    get_character_image,
    get_character_url,
    get_element_image,
    get_name,
    get_rarity,
    get_specialty_image,
)
from ..api.details import (
    DetailUnavailable,
    load_character_detail,
)
from ..settings import get_enabled_games, load_settings, save_settings
from .loader import LoadThread
from .preload import get_preload_manager

logger = logging.getLogger(__name__)

_DETACHED_THREADS = set()


class GameSectionData(QObject):
    """Data for a single game section exposed to QML."""
    changed = Signal()

    def __init__(self, game_id: str, game_name: str, parent=None):
        super().__init__(parent)
        self._game_id = game_id
        self._game_name = game_name
        self._cards = []
        self._live_version = ""
        self._latest_version = ""
        self._status = "Loading..."

    @Property(str, notify=changed)
    def gameId(self): return self._game_id

    @Property(str, notify=changed)
    def gameName(self): return self._game_name

    @Property(list, notify=changed)
    def cards(self): return self._cards

    @Property(str, notify=changed)
    def liveVersion(self): return self._live_version

    @Property(str, notify=changed)
    def latestVersion(self): return self._latest_version

    @Property(str, notify=changed)
    def statusText(self): return self._status

    def set_cards(self, cards):
        self._cards = cards
        self.changed.emit()

    def set_versions(self, live, latest):
        self._live_version = live or ""
        self._latest_version = latest or ""
        self.changed.emit()

    def set_status(self, text):
        self._status = text
        self.changed.emit()

    def clear_cards(self):
        self._cards = []
        self._status = "Loading..."
        self.changed.emit()


class NanokaBackend(QObject):
    """Main backend object exposed to QML."""

    # Signals for property changes
    loadInProgressChanged = Signal()
    statusLabelChanged = Signal()
    cacheLabelChanged = Signal()
    gameSectionsChanged = Signal()
    detailLoadingChanged = Signal()
    detailHeaderChanged = Signal()
    detailOverviewChanged = Signal()
    detailStatsChanged = Signal()
    detailBuildChanged = Signal()
    detailSkillsChanged = Signal()
    detailExtrasChanged = Signal()
    detailArtUrlChanged = Signal()
    detailErrorChanged = Signal()
    detailSourceUrlChanged = Signal()
    cacheDetailsChanged = Signal()
    cacheBuildsChanged = Signal()
    cacheArtworkChanged = Signal()
    allGamesChanged = Signal()
    preloadRunningChanged = Signal()
    preloadStatusChanged = Signal()
    cacheSizesChanged = Signal()

    # Non-property signals
    openDetails = Signal(str, str, object)  # gameId, charId, charData
    closeDetails = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._load_in_progress = False
        self._status_label = "Ready"
        self._cache_label = ""
        self._game_sections: list[GameSectionData] = []
        self._game_section_map: dict[str, GameSectionData] = {}
        self._load_generation = 0
        self._load_threads = []
        self._pending_sections = set()
        self._fetch_finished = False
        self._reload_pending = False
        self._loading_chars: dict[str, list] = {}
        self._loading_index: dict[str, int] = {}

        # Details
        self._detail_loading = False
        self._detail_name = ""
        self._detail_subtitle = ""
        self._detail_level_label = ""
        self._detail_badges: list[str] = []
        self._detail_overview = ""
        self._detail_stats: list[dict] = []
        self._detail_build: list[dict] = []
        self._detail_skills: list[dict] = []
        self._detail_extras: list[dict] = []
        self._detail_art_url = ""
        self._detail_source_url = ""
        self._detail_error = ""
        self._current_detail_game = ""
        self._current_detail_char = ""

        # Cache settings
        settings = dict(load_settings())
        self._cache_details = bool(settings.get("cache_character_details", True))
        self._cache_builds = bool(settings.get("cache_character_builds", True))
        self._cache_artwork = bool(settings.get("cache_character_artwork", True))

        # Preload state
        self._preload_status = ""

        # Cache sizes
        self._cache_sizes: dict = {}

        # Cache label timer
        self._cache_label_timer = QTimer(self)
        self._cache_label_timer.setSingleShot(True)
        self._cache_label_timer.timeout.connect(lambda: self._set_cache_label(""))

        # Preload manager
        pm = get_preload_manager()
        pm.progress.connect(self._on_preload_progress)
        pm.finished.connect(self._on_preload_finished)
        pm.failed.connect(self._on_preload_failed)

        self._sync_sections(self._desired_games())

    # -- Properties --

    @Property(bool, notify=loadInProgressChanged)
    def loadInProgress(self): return self._load_in_progress

    @Property(str, notify=statusLabelChanged)
    def statusLabel(self): return self._status_label

    @Property(str, notify=cacheLabelChanged)
    def cacheLabel(self): return self._cache_label

    @Property(list, notify=gameSectionsChanged)
    def gameSections(self): return self._game_sections

    @Property(bool, notify=detailLoadingChanged)
    def detailLoading(self): return self._detail_loading

    @Property(str, notify=detailHeaderChanged)
    def detailName(self): return self._detail_name

    @Property(str, notify=detailHeaderChanged)
    def detailSubtitle(self): return self._detail_subtitle

    @Property(str, notify=detailHeaderChanged)
    def detailLevelLabel(self): return self._detail_level_label

    @Property(list, notify=detailHeaderChanged)
    def detailBadges(self): return self._detail_badges

    @Property(str, notify=detailOverviewChanged)
    def detailOverview(self): return self._detail_overview

    @Property(list, notify=detailStatsChanged)
    def detailStats(self): return self._detail_stats

    @Property(list, notify=detailBuildChanged)
    def detailBuild(self): return self._detail_build

    @Property(list, notify=detailSkillsChanged)
    def detailSkills(self): return self._detail_skills

    @Property(list, notify=detailExtrasChanged)
    def detailExtras(self): return self._detail_extras

    @Property(str, notify=detailArtUrlChanged)
    def detailArtUrl(self): return self._detail_art_url

    @Property(str, notify=detailSourceUrlChanged)
    def detailSourceUrl(self): return self._detail_source_url

    @Property(str, notify=detailErrorChanged)
    def detailError(self): return self._detail_error

    @Property(bool, notify=cacheDetailsChanged)
    def cacheDetails(self): return self._cache_details

    @cacheDetails.setter
    def cacheDetails(self, val):
        self._cache_details = bool(val)
        self._save_cache_settings()
        self.cacheDetailsChanged.emit()

    @Property(bool, notify=cacheBuildsChanged)
    def cacheBuilds(self): return self._cache_builds

    @cacheBuilds.setter
    def cacheBuilds(self, val):
        self._cache_builds = bool(val)
        self._save_cache_settings()
        self.cacheBuildsChanged.emit()

    @Property(bool, notify=cacheArtworkChanged)
    def cacheArtwork(self): return self._cache_artwork

    @cacheArtwork.setter
    def cacheArtwork(self, val):
        self._cache_artwork = bool(val)
        self._save_cache_settings()
        self.cacheArtworkChanged.emit()

    @Property(list, notify=allGamesChanged)
    def allGames(self):
        settings = dict(load_settings())
        disabled = set(settings.get("disabled_games") or [])
        return [
            {"id": gid, "name": info["name"], "enabled": gid not in disabled}
            for gid, info in GAMES.items()
        ]

    @Property(bool, notify=preloadRunningChanged)
    def preloadRunning(self):
        return get_preload_manager().running

    @Property(str, notify=preloadStatusChanged)
    def preloadStatus(self): return self._preload_status

    @Property("QVariantMap", notify=cacheSizesChanged)
    def cacheSizeInfo(self):
        """Return {details, builds, artwork, buildsLastCached} string map."""
        return self._cache_sizes

    # -- Slots (callable from QML) --

    @Slot()
    def loadData(self):
        """Start loading character data."""
        if self._load_in_progress:
            return
        self._load_in_progress = True
        self.loadInProgressChanged.emit()
        self._load_generation += 1
        generation = self._load_generation

        games = self._desired_games()
        self._sync_sections(games)

        self._set_status("Loading...")
        self._fetch_finished = False
        self._loading_chars.clear()
        self._loading_index.clear()
        self._pending_sections = set(games)

        for section in self._game_section_map.values():
            section.clear_cards()
            section.set_status("Loading...")

        if not games:
            self._fetch_finished = True
            self._set_status("No games enabled")
            self._finish_loading_ui(no_games=True)
            return

        thread = LoadThread(self, games)
        thread.game_loaded.connect(
            lambda game, chars, gen=generation: self._on_game_loaded(game, chars, gen)
        )
        thread.load_finished.connect(
            lambda gen=generation: self._on_load_finished(gen)
        )
        thread.finished.connect(lambda t=thread: self._on_load_thread_finished(t))
        self._load_threads.append(thread)
        thread.start()

    @Slot(str, str, "QVariant")
    def openCharacterDetails(self, game_id: str, char_id: str, char_data):
        """Open details for a character."""
        self.openDetails.emit(game_id, char_id, char_data)
        self.loadDetails(game_id, char_id)

    @Slot(str, str)
    def loadDetails(self, game_id: str, char_id: str):
        """Load character detail data (called from QML)."""
        from PySide6.QtCore import QThread, Signal as Sig

        self._current_detail_game = game_id
        self._current_detail_char = char_id

        self._detail_loading = True
        self._detail_name = ""
        self._detail_subtitle = ""
        self._detail_level_label = ""
        self._detail_badges = []
        self._detail_overview = ""
        self._detail_stats = []
        self._detail_build = []
        self._detail_skills = []
        self._detail_extras = []
        self._detail_art_url = ""
        self._detail_source_url = ""
        self._detail_error = ""
        self.detailLoadingChanged.emit()
        self.detailHeaderChanged.emit()
        self.detailOverviewChanged.emit()
        self.detailStatsChanged.emit()
        self.detailBuildChanged.emit()
        self.detailSkillsChanged.emit()
        self.detailExtrasChanged.emit()
        self.detailArtUrlChanged.emit()
        self.detailSourceUrlChanged.emit()
        self.detailErrorChanged.emit()

        class _Worker(QThread):
            loaded = Sig(object)
            failed = Sig(str)

            def __init__(self, game, cid):
                super().__init__()
                self._game = game
                self._cid = cid

            def run(self):
                try:
                    self.loaded.emit(load_character_detail(self._game, self._cid))
                except DetailUnavailable as e:
                    self.failed.emit(str(e))
                except Exception:
                    logger.exception("Failed to load details")
                    self.failed.emit("Could not load character details.")

        worker = _Worker(game_id, char_id)
        worker.loaded.connect(self._on_details_loaded)
        worker.failed.connect(self._on_details_failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @Slot()
    def retryDetails(self):
        """Retry loading the current character's details after a failure."""
        if self._current_detail_game and self._current_detail_char:
            self.loadDetails(self._current_detail_game, self._current_detail_char)

    def _on_details_loaded(self, detail):
        self._detail_loading = False
        self._detail_name = detail.name or ""
        self._detail_subtitle = detail.subtitle or ""
        self._detail_level_label = detail.level_label or ""
        self._detail_badges = list(detail.badges or [])
        self._detail_overview = detail.overview or ""
        self._detail_stats = [
            {"name": k, "value": str(v)} for k, v in (detail.stats or [])
        ]
        # Build sections: list of {title, items: [...]}
        self._detail_build = [
            {"title": s.title, "items": list(s.items)}
            for s in (detail.build or [])
        ]
        # Skills: list of {name, typeName, level, description, multipliers: [{label, value}]}
        self._detail_skills = [
            {
                "name": s.name,
                "typeName": s.type_name,
                "level": s.level,
                "description": s.description or "",
                "multipliers": [
                    {"label": lbl, "value": val}
                    for lbl, val in (s.multipliers or [])
                ],
            }
            for s in (detail.skills or [])
        ]
        # Extras: list of {title, entries: [{name, text}]}
        self._detail_extras = [
            {
                "title": ex.title,
                "entries": [
                    {"name": e.name, "text": e.text or ""}
                    for e in (ex.entries or [])
                ],
            }
            for ex in (detail.extras or [])
        ]
        self._detail_art_url = detail.art_url or ""
        self._detail_source_url = detail.source_url or ""
        self.detailLoadingChanged.emit()
        self.detailHeaderChanged.emit()
        self.detailOverviewChanged.emit()
        self.detailStatsChanged.emit()
        self.detailBuildChanged.emit()
        self.detailSkillsChanged.emit()
        self.detailExtrasChanged.emit()
        self.detailArtUrlChanged.emit()
        self.detailSourceUrlChanged.emit()

    def _on_details_failed(self, msg: str):
        self._detail_loading = False
        self._detail_error = msg
        self.detailLoadingChanged.emit()
        self.detailErrorChanged.emit()

    @Slot(str, bool)
    def setGameEnabled(self, game_id: str, enabled: bool):
        settings = dict(load_settings())
        disabled = set(settings.get("disabled_games") or [])
        if enabled:
            disabled.discard(game_id)
        else:
            disabled.add(game_id)
        settings["disabled_games"] = list(disabled)
        save_settings(settings)
        self.allGamesChanged.emit()
        self._sync_sections(self._desired_games())
        self.loadData()

    @Slot()
    def clearCache(self):
        from ..api import clear_cache
        from .image_loader import clear_image_cache
        manager = get_preload_manager()
        clear_cache()
        clear_image_cache()
        manager.last_summary = None
        manager.last_progress = None
        manager.last_error = ""
        self._preload_status = "Cache cleared."
        self.preloadStatusChanged.emit()
        self._refresh_cache_sizes()

    @Slot(str)
    def startPreload(self, kind: str):
        """Start a preload of the given kind (details/builds/artwork)."""
        manager = get_preload_manager()
        if not manager.start(kind):
            return
        self._preload_status = "Preparing preload..."
        self.preloadStatusChanged.emit()
        self.preloadRunningChanged.emit()

    @Slot()
    def stopPreload(self):
        """Cancel the running preload."""
        get_preload_manager().cancel()

    @Slot()
    def refreshCacheSizes(self):
        """Update cache size info (callable from QML)."""
        self._refresh_cache_sizes()

    # -- Internal --

    def _save_cache_settings(self):
        settings = dict(load_settings())
        settings.update({
            "cache_character_details": self._cache_details,
            "cache_character_builds": self._cache_builds,
            "cache_character_artwork": self._cache_artwork,
        })
        save_settings(settings)

    def _set_status(self, text: str):
        self._status_label = text
        self.statusLabelChanged.emit()

    def _set_cache_label(self, text: str):
        self._cache_label = text
        self.cacheLabelChanged.emit()

    @staticmethod
    def _desired_games() -> list[str]:
        return [game for game in get_enabled_games() if game in GAMES]

    def _sync_sections(self, order: list[str]):
        # Remove sections not in order
        for game in list(self._game_section_map):
            if game not in order:
                del self._game_section_map[game]
        # Add new sections
        for game in order:
            if game not in self._game_section_map:
                self._game_section_map[game] = GameSectionData(game, GAMES[game]["name"], self)
        # Rebuild ordered list
        self._game_sections = [self._game_section_map[g] for g in order if g in self._game_section_map]
        self.gameSectionsChanged.emit()

    def _on_game_loaded(self, game: str, chars: list, generation: int):
        if generation != self._load_generation:
            return
        section = self._game_section_map.get(game)
        if not section:
            return

        if not chars:
            section.set_status("Failed to load characters")
            self._mark_section_done(game)
            return

        # Fetch versions
        try:
            manifest = fetch_manifest()
            game_info = manifest.get(game, {})
            section.set_versions(game_info.get("live"), game_info.get("latest"))
        except Exception as e:
            logger.error("Error fetching version for %s: %s", game, e)

        # Convert chars to card data dicts
        card_list = []
        for char_id, char_data, is_new in chars:
            card_list.append({
                "gameId": game,
                "charId": char_id,
                "name": get_name(game, char_data, char_id),
                "rarity": str(get_rarity(game, char_data)),
                "imageUrl": get_character_image(game, char_data, char_id) or "",
                "elementImageUrl": get_element_image(game, char_data) or "",
                "specialtyImageUrl": get_specialty_image(game, char_data) or "",
                "url": get_character_url(game, char_id, char_data) or "",
                "isNew": is_new,
                "charData": char_data,
            })

        section.set_cards(card_list)
        section.set_status(f"{len(chars)} total")
        self._mark_section_done(game)

    def _on_load_finished(self, generation: int):
        if generation != self._load_generation:
            return
        self._fetch_finished = True
        if not self._pending_sections:
            self._finish_loading_ui()

    def _mark_section_done(self, game: str):
        self._pending_sections.discard(game)
        if self._fetch_finished and not self._pending_sections:
            self._finish_loading_ui()

    def _finish_loading_ui(self, no_games: bool = False):
        self._load_in_progress = False
        self.loadInProgressChanged.emit()
        if no_games or not self._desired_games():
            self._set_status("No games enabled")
        else:
            self._set_status(f"Loaded at {datetime.now().strftime('%H:%M:%S')}")

        if self._reload_pending:
            self._reload_pending = False
            if self._desired_games():
                QTimer.singleShot(0, self.loadData)

    def _on_load_thread_finished(self, thread):
        try:
            self._load_threads.remove(thread)
        except ValueError:
            pass
        thread.deleteLater()

    def _on_preload_progress(self, progress):
        self._cache_label_timer.stop()
        if progress.total:
            self._set_cache_label(f"Preloading {progress.kind} {progress.completed}/{progress.total}")
            name = getattr(progress, "name", "") or ""
            if len(name) > 28:
                name = name[:27].rstrip() + "…"
            status = f"Preloading {progress.kind} {progress.completed}/{progress.total}"
            if name:
                status += f" — {name}"
            self._preload_status = status
        else:
            self._set_cache_label("Preparing preload...")
            self._preload_status = "Preparing preload..."
        self.preloadStatusChanged.emit()

    def _on_preload_finished(self, summary):
        if summary.cancelled:
            text = f"Preload stopped at {summary.completed}/{summary.total}"
        else:
            text = f"Preloaded {summary.completed}/{summary.total} {summary.kind}"
            if summary.failed:
                text += f", {summary.failed} failed"
            failed_games = getattr(summary, "failed_games", 0)
            if failed_games:
                text += f", {failed_games} game(s) unavailable"
        self._set_cache_label(text)
        self._preload_status = text
        self.preloadStatusChanged.emit()
        self.preloadRunningChanged.emit()
        self._cache_label_timer.start(6000)
        self._refresh_cache_sizes()

    def _on_preload_failed(self, message: str):
        self._preload_status = f"Preload failed: {message}"
        self.preloadStatusChanged.emit()
        self.preloadRunningChanged.emit()

    def _refresh_cache_sizes(self):
        """Reload cache-size data and emit cacheSizesChanged."""
        try:
            from ..api import cache_sizes
            from ..api.cache_info import read_build_cache_info
            from datetime import datetime as dt

            sizes = cache_sizes()

            def _fmt(b: int) -> str:
                b = max(0, int(b))
                return "0 kB" if b == 0 else f"{(b + 1023) // 1024:,} kB"

            info = read_build_cache_info()
            last_ts = float(info.get("last_cached") or 0.0)
            last_cached = (
                dt.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M")
                if last_ts > 0
                else "never"
            )

            self._cache_sizes = {
                "details": _fmt(sizes.get("details", 0)),
                "builds": _fmt(sizes.get("builds", 0)),
                "artwork": _fmt(sizes.get("artwork", 0)),
                "buildsLastCached": last_cached,
            }
            self.cacheSizesChanged.emit()
        except Exception:
            logger.exception("Failed to refresh cache sizes")
