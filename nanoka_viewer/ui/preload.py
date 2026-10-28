"""Background manager for bulk cache preloading.

The settings dialog owns the buttons, but the work must outlive the dialog:
closing settings while a long artwork download is running should not cancel it
(or worse, destroy a live QThread).  This module keeps one daemon thread and
forwards its progress to the GUI thread through Qt signals.

A plain ``threading.Thread`` is used instead of ``QThread`` on purpose.  The
preload is pure network/disk work, and a daemon thread cannot abort the
process on shutdown the way a destroyed QThread can.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Qt, Signal

from ..api.preload import (
    PRELOAD_KINDS,
    PreloadProgress,
    PreloadSummary,
    preload_characters,
)

logger = logging.getLogger(__name__)


class _Bridge(QObject):
    """Signals emitted from the worker thread."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)


class PreloadManager(QObject):
    """Own the single background preload and expose its state."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._kind = ""
        self.last_progress: PreloadProgress | None = None
        self.last_summary: PreloadSummary | None = None
        self.last_error = ""

        self._bridge = _Bridge(self)
        self._bridge.progress.connect(
            self._on_progress, Qt.ConnectionType.QueuedConnection
        )
        self._bridge.finished.connect(
            self._on_worker_finished, Qt.ConnectionType.QueuedConnection
        )
        self._bridge.failed.connect(
            self._on_worker_failed, Qt.ConnectionType.QueuedConnection
        )

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def kind(self) -> str:
        """The kind currently being cached, or ``""`` when idle."""
        return self._kind if self.running else ""

    def start(self, kind: str) -> bool:
        """Start *kind* in the background.  Returns false if already running."""
        if kind not in PRELOAD_KINDS:
            raise ValueError(f"Unknown preload kind: {kind!r}")
        if self.running:
            return False

        self._kind = kind
        self._stop.clear()
        self.last_progress = None
        self.last_summary = None
        self.last_error = ""
        bridge = self._bridge

        def run():
            try:
                summary = preload_characters(
                    kind,
                    bridge.progress.emit,
                    self._stop.is_set,
                )
            except Exception as exc:  # noqa: BLE001 - surface it in the dialog
                logger.exception("Preloading %s failed", kind)
                bridge.failed.emit(str(exc))
                return
            bridge.finished.emit(summary)

        thread = threading.Thread(
            target=run,
            name=f"nanoka-preload-{kind}",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        return True

    def cancel(self):
        """Ask the worker to stop after the character it is currently on."""
        if self.running:
            logger.info("Cancelling %s preload", self._kind)
            self._stop.set()

    def _on_progress(self, progress: PreloadProgress):
        self.last_progress = progress
        self.progress.emit(progress)

    def _on_worker_finished(self, summary: PreloadSummary):
        self._thread = None
        self._kind = ""
        self.last_summary = summary
        self.finished.emit(summary)

    def _on_worker_failed(self, message: str):
        self._thread = None
        self._kind = ""
        self.last_error = message
        self.failed.emit(message)


_manager: PreloadManager | None = None


def get_preload_manager() -> PreloadManager:
    """Return the process-wide preload manager (created lazily on the GUI thread)."""
    global _manager
    if _manager is None:
        _manager = PreloadManager()
    return _manager
