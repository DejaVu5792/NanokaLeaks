"""Tests for the background preload manager."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from nanoka_viewer.api.preload import (
    PRELOAD_DETAILS,
    PreloadProgress,
    PreloadSummary,
)
from nanoka_viewer.ui.preload import PreloadManager
from support import QtTestCase, wait


class PreloadManagerThreadTests(QtTestCase):
    def test_worker_signals_are_delivered_on_the_gui_thread(self):
        manager = PreloadManager()
        self.addCleanup(manager.deleteLater)
        progress = []
        finished = []

        def fake_preload(kind, on_progress, should_stop):
            on_progress(PreloadProgress(kind=kind, completed=0, total=1))
            on_progress(
                PreloadProgress(kind=kind, completed=1, total=1, name="Test")
            )
            return PreloadSummary(kind=kind, total=1, completed=1)

        manager.progress.connect(
            lambda value: progress.append((value, threading.current_thread()))
        )
        manager.finished.connect(finished.append)

        with patch(
            "nanoka_viewer.ui.preload.preload_characters",
            side_effect=fake_preload,
        ):
            self.assertTrue(manager.start(PRELOAD_DETAILS))
            for _ in range(100):
                wait(10)
                if finished:
                    break

        self.assertTrue(finished, "the manager must report completion")
        self.assertEqual(finished[0].completed, 1)
        self.assertEqual(len(progress), 2)
        self.assertIs(progress[0][1], threading.main_thread())


if __name__ == "__main__":
    unittest.main()
