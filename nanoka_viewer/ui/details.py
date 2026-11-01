"""In-window character details view, rendered by QML.

The popup keeps the thin widget shell Qt needs to cover the central widget
(:class:`~nanoka_viewer.ui.popup_host.PopupHost`) and renders the backdrop,
panel and content from ``qml/details/DetailsOverlay.qml``.  Python still owns
everything that is not presentation:

* the three worker threads (detail, recommended build, artwork);
* the request-id scheme that drops stale results;
* the cache probes and the deferred-skeleton fallback timers, so a warm cache
  does not flash a placeholder;
* decoding the artwork bytes and publishing them through the
  ``image://nanokaart`` provider, because QML cannot read a ``bytes`` object.

The QML bindings read from :class:`DetailsViewModel`, which mirrors the
loading state machine without needing a QML engine to be tested.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QCursor, QImage
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from ..api.details import (
    BuildSection,
    CharacterDetail,
    DetailUnavailable,
    has_cached_art,
    has_cached_build,
    has_cached_detail,
    load_character_art,
    load_character_build,
    load_character_detail,
)
from ..saliency import sr_centroid_x
from ..settings import get_setting
from .details_model import DetailsViewModel
from .image_provider import ART_PROVIDER_ID, NanokaArtProvider
from .popup_host import PopupHost, is_alive

logger = logging.getLogger(__name__)

# When the caches say a character is already warm, the loader thread usually
# finishes in a few milliseconds, so the skeleton would only flash.  If it is
# still pending after this delay the cache probe was wrong (for example the
# manifest went stale) and we fall back to the normal loading screen.
LOADING_FALLBACK_MS = 150


class _DetailLoadThread(QThread):
    """Fetch a character detail payload without blocking the UI."""

    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, game: str, char_id: str, parent=None):
        super().__init__(parent)
        self._game = game
        self._char_id = char_id

    def run(self):
        try:
            self.loaded.emit(load_character_detail(self._game, self._char_id))
        except DetailUnavailable as exc:
            self.failed.emit(str(exc))
        except Exception:
            logger.exception("Failed to load character details")
            self.failed.emit("Could not load character details. Please try again.")


class _BuildLoadThread(QThread):
    """Fetch recommended-build metadata separately from the text payload."""

    loaded = Signal(object)
    failed = Signal()

    def __init__(self, detail: CharacterDetail, parent=None):
        super().__init__(parent)
        self._detail = detail

    def run(self):
        try:
            self.loaded.emit(load_character_build(self._detail))
        except Exception:
            logger.exception("Failed to load recommended build")
            self.failed.emit()


class _ArtLoadThread(QThread):
    """Fetch character art separately from the text payload."""

    loaded = Signal(object)
    failed = Signal()

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        data = load_character_art(self._url)
        if not data:
            self.failed.emit()
            return

        focus_x = 0.5
        if get_setting("sr_centroid_centering"):
            try:
                focus_x = sr_centroid_x(data)
            except Exception:  # noqa: BLE001 - artwork must still render
                logger.exception("Could not compute artwork focus")
        self.loaded.emit((data, focus_x))


class CharacterDetailsPopup(PopupHost):
    """Lightbox-style character details overlay."""

    overlay_object_name = "detailsOverlay"
    source = "details/DetailsOverlay.qml"
    blocks_host_input = True
    log_name = "details popup"
    logger = logging.getLogger(__name__)

    def __init__(self, host):
        super().__init__(host)
        self._request_id = 0
        self._thread: _DetailLoadThread | None = None
        self._build_thread: _BuildLoadThread | None = None
        self._art_thread: _ArtLoadThread | None = None
        self._deferred_request_id: int | None = None
        self._deferred_build_request_id: int | None = None
        self._deferred_art_request_id: int | None = None
        self._loading_timer = QTimer(self)
        self._loading_timer.setSingleShot(True)
        self._loading_timer.setInterval(LOADING_FALLBACK_MS)
        self._loading_timer.timeout.connect(self._show_deferred_loading)
        self._build_loading_timer = QTimer(self)
        self._build_loading_timer.setSingleShot(True)
        self._build_loading_timer.setInterval(LOADING_FALLBACK_MS)
        self._build_loading_timer.timeout.connect(
            self._show_deferred_build_skeleton
        )
        self._art_loading_timer = QTimer(self)
        self._art_loading_timer.setSingleShot(True)
        self._art_loading_timer.setInterval(LOADING_FALLBACK_MS)
        self._art_loading_timer.timeout.connect(
            self._show_deferred_art_placeholder
        )
        self._game = ""
        self._char_id = ""
        self._source: QWidget | None = None

        self._model = DetailsViewModel(self)
        self._art_provider = NanokaArtProvider()
        self._art_token = 0

        self._qml = self._create_view(
            {"details": self._model},
            image_providers={ART_PROVIDER_ID: self._art_provider},
        )
        # The model must not outlive the engine that binds to it: as a child of
        # the view it is destroyed right after the engine, so no binding is
        # ever evaluated against a dangling context property.
        self._model.setParent(self._qml)

        self._model.closeRequested.connect(self._request_close)
        self._model.retryRequested.connect(self._retry)

    def open_character(
        self, game: str, char_id: str, source: QWidget | None = None
    ):
        """Show the popup and fetch *char_id*'s details from nanoka.cc.

        *source* is the widget that triggered the popup (usually the card's
        View button).  Its hover/pressed state is cleared so it does not keep
        painting as if it were still interactive underneath the overlay.
        """
        self._game = game
        self._char_id = char_id
        self._source = source
        self._request_id += 1
        request_id = self._request_id

        cursor_pos = QCursor.pos()
        logger.debug(
            "open details %s/%s source=%r grabber=%r widget_at_cursor=%r "
            "focus=%r",
            game,
            char_id,
            source,
            QWidget.mouseGrabber(),
            QApplication.widgetAt(cursor_pos),
            QApplication.focusWidget(),
        )

        self.clear_stale_input_state(source)
        self._cancel_deferred_loading()
        self._cancel_deferred_build_loading()
        self._cancel_deferred_art_loading()
        self._clear_content()
        if has_cached_detail(game, char_id):
            # Cache hit: render as soon as the loader thread returns instead of
            # showing a skeleton that would only flash for a frame or two.
            self._deferred_request_id = request_id
            self._loading_timer.start()
        else:
            self._show_loading()
        self.show_overlay()
        logger.debug(
            "details shown: host=%s overlay=%s panel=%s visible=%s "
            "focus=%r guard=%s",
            self._host.size(),
            self.size(),
            self.panel_rect(),
            self.isVisible(),
            QApplication.focusWidget(),
            self._input_guard_installed,
        )
        self._start_load(request_id)

    def _start_load(self, request_id: int):
        thread = _DetailLoadThread(self._game, self._char_id, self)
        thread.loaded.connect(
            lambda detail: self._on_loaded(request_id, detail)
        )
        thread.failed.connect(
            lambda message: self._on_failed(request_id, message)
        )
        thread.finished.connect(lambda t=thread: self._on_thread_finished(t))
        self._thread = thread
        thread.start()

    def _on_thread_finished(self, thread: _DetailLoadThread):
        if self._thread is thread:
            self._thread = None
        thread.deleteLater()

    def _on_loaded(self, request_id: int, detail: CharacterDetail):
        if request_id != self._request_id or not self.isVisible():
            return
        self._cancel_deferred_loading()
        self._clear_content()
        self._model.set_detail(detail)
        if not detail.build and detail.build_context is not None:
            if has_cached_build(detail):
                self._deferred_build_request_id = request_id
                self._build_loading_timer.start()
            else:
                self._model.show_build_skeleton()
            self._start_build_load(request_id, detail)
        if detail.art_url:
            if has_cached_art(detail.art_url):
                # The deferred art timer shows the placeholder if this is slow.
                self._deferred_art_request_id = request_id
                self._art_loading_timer.start()
            else:
                self._model.show_art_skeleton()
            self._start_art_load(request_id, detail.art_url)

    def _start_build_load(self, request_id: int, detail: CharacterDetail):
        thread = _BuildLoadThread(detail, self)
        thread.loaded.connect(
            lambda sections: self._on_build_loaded(request_id, sections)
        )
        thread.failed.connect(lambda: self._on_build_failed(request_id))
        thread.finished.connect(
            lambda t=thread: self._on_build_thread_finished(t)
        )
        self._build_thread = thread
        thread.start()

    def _on_build_thread_finished(self, thread: _BuildLoadThread):
        if self._build_thread is thread:
            self._build_thread = None
        thread.deleteLater()

    def _on_build_loaded(self, request_id: int, sections: list[BuildSection]):
        if request_id != self._request_id or not self.isVisible():
            return
        self._cancel_deferred_build_loading()
        self._model.set_build(sections or [])

    def _on_build_failed(self, request_id: int):
        if request_id != self._request_id or not self.isVisible():
            return
        self._cancel_deferred_build_loading()
        self._model.set_build([])

    def _start_art_load(self, request_id: int, art_url: str):
        thread = _ArtLoadThread(art_url, self)
        thread.loaded.connect(
            lambda data: self._on_art_loaded(request_id, data)
        )
        thread.failed.connect(lambda: self._on_art_failed(request_id))
        thread.finished.connect(lambda t=thread: self._on_art_thread_finished(t))
        self._art_thread = thread
        thread.start()

    def _on_art_thread_finished(self, thread: _ArtLoadThread):
        if self._art_thread is thread:
            self._art_thread = None
        thread.deleteLater()

    def _on_art_loaded(self, request_id: int, payload: object):
        if request_id != self._request_id or not self.isVisible():
            return
        self._cancel_deferred_art_loading()
        if isinstance(payload, tuple):
            data, focus_x = payload
        else:
            data, focus_x = payload, 0.5
        image = QImage()
        if not image.loadFromData(data):
            self._set_art_message("Art unavailable")
            return
        self._art_token += 1
        source = self._art_provider.add(str(self._art_token), image)
        self._model.set_art(source, focus_x)

    def _on_art_failed(self, request_id: int):
        if request_id != self._request_id or not self.isVisible():
            return
        self._cancel_deferred_art_loading()
        self._set_art_message("Art unavailable")

    def _set_art_message(self, message: str):
        """Drop the artwork and show *message* in its place."""
        self._cancel_deferred_art_loading()
        self._art_provider.clear()
        self._model.set_art_unavailable(message)

    def _on_failed(self, request_id: int, message: str):
        if request_id != self._request_id or not self.isVisible():
            return
        self._cancel_deferred_loading()
        self._clear_content()
        self._model.set_error(message)

    def _retry(self):
        self._request_id += 1
        request_id = self._request_id
        self._cancel_deferred_loading()
        self._clear_content()
        self._show_loading()
        self._start_load(request_id)

    def _show_deferred_loading(self):
        """Show the skeleton if a cache-hit load is unexpectedly slow."""
        request_id = self._deferred_request_id
        self._deferred_request_id = None
        if request_id is None or request_id != self._request_id:
            return
        if not self.isVisible():
            return
        if self._thread is None:
            # The loader already finished; its content (or error card) is up.
            return
        self._clear_content()
        self._show_loading()

    def _show_deferred_build_skeleton(self):
        """Show the build skeleton if cached build IO is unexpectedly slow."""
        request_id = self._deferred_build_request_id
        self._deferred_build_request_id = None
        if request_id is None or request_id != self._request_id:
            return
        if not self.isVisible() or self._build_thread is None:
            return
        self._model.show_build_skeleton()

    def _show_deferred_art_placeholder(self):
        """Show the art placeholder if cached artwork IO is unexpectedly slow."""
        request_id = self._deferred_art_request_id
        self._deferred_art_request_id = None
        if request_id is None or request_id != self._request_id:
            return
        if not self.isVisible() or self._art_thread is None:
            return
        self._model.show_art_skeleton()

    def _cancel_deferred_loading(self):
        self._deferred_request_id = None
        self._loading_timer.stop()

    def _cancel_deferred_build_loading(self):
        self._deferred_build_request_id = None
        self._build_loading_timer.stop()

    def _cancel_deferred_art_loading(self):
        self._deferred_art_request_id = None
        self._art_loading_timer.stop()

    def _show_loading(self):
        self._model.show_loading()

    def _clear_content(self):
        self._cancel_deferred_loading()
        self._cancel_deferred_build_loading()
        self._cancel_deferred_art_loading()
        self._art_provider.clear()
        self._model.reset()

    def _source_widget(self) -> QWidget | None:
        return self._source

    def _on_close(self):
        self._request_id += 1
        self._clear_content()
        self._game = ""
        self._char_id = ""
        self._source = None

    def showEvent(self, event):
        logger.debug(
            "details showEvent: visible=%s geometry=%s state=%s",
            self.isVisible(),
            self.geometry(),
            self._host.window().windowState(),
        )
        super().showEvent(event)


_popup = None


def open_details(
    game: str,
    char_id: str,
    _char_data=None,
    parent=None,
    source: QWidget | None = None,
):
    """Show the shared character-details popup."""
    global _popup
    if parent is None:
        return
    if isinstance(parent, QMainWindow):
        host = parent.centralWidget() or parent
    else:
        host = parent

    # The module-level popup outlives old host windows; never touch a wrapper
    # whose C++ object is already gone.
    if _popup is not None and not is_alive(_popup):
        _popup = None
    if _popup is not None and _popup._host is not host:
        _popup.close_popup()
        _popup = None
    if _popup is None:
        _popup = CharacterDetailsPopup(host)

    if (
        _popup.isVisible()
        and _popup._game == game
        and _popup._char_id == char_id
    ):
        logger.debug(
            "details already open for %s/%s; raising instead of reloading",
            game,
            char_id,
        )
        _popup.bring_to_front()
        return

    _popup.open_character(game, char_id, source)
