#!/usr/bin/env python3
"""Profile NanokaLeaks while driving a fixed navigation workload.

The workload matches the way a user explores the app:

* scroll the game sections vertically, top to bottom and back
* scroll every game's character strip horizontally, right and back
* open two cached character details in each game and scroll the panel
* open the settings View tab, toggle a game off/on and reorder the list

Only the navigation window is profiled, so startup and the initial data load
do not bury the navigation costs.  Their wall time is still recorded in the
JSON summary.

The script deliberately sticks to APIs that exist on both ``main`` and the
performance branches (``NanokaViewer.openDetails``, ``openSettings``,
``sections_model`` and the settings view-model slots) so the justfile can copy
it into a temporary ``main`` worktree and run the same workload there.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import logging
import os
import platform
import pstats
import statistics
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# Do not import PySide before the platform is chosen.  The real display is
# required here: an offscreen surface would not paint the QML tree, and the
# whole point is to measure navigation including rendering.  Prefer XWayland
# when both displays exist; on a pure Wayland session fall back to Wayland.
if not os.environ.get("QT_QPA_PLATFORM"):
    os.environ["QT_QPA_PLATFORM"] = "xcb" if os.environ.get("DISPLAY") else "wayland"
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false;qt.qml.*=false")

from PySide6.QtCore import QEventLoop, QObject, QTimer  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

logger = logging.getLogger("profile_navigation")

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 900
DETAIL_TIMEOUT_MS = 30_000
LOAD_TIMEOUT_MS = 180_000


# ---------------------------------------------------------------------------
# QML helpers
# ---------------------------------------------------------------------------


def find_qml_item(root, object_name: str):
    """Return the first QML item named *object_name*, depth-first."""
    for item in iter_qml_items(root):
        if item.objectName() == object_name:
            return item
    return None


def iter_qml_items(root):
    """Yield *root* and every visual descendant."""
    queue = [root]
    while queue:
        item = queue.pop(0)
        if item is None:
            continue
        yield item
        if isinstance(item, QQuickItem):
            queue.extend(item.childItems())


def game_of(item):
    """Return the game id of a ``GameSection`` delegate, or ``None``.

    ``ListView`` has its own ``section`` property whose C++ type has no
    Python converter, so the lookup is guarded and only a real ``Section``
    object with a string ``game`` counts as a delegate.
    """
    if not isinstance(item, QQuickItem):
        return None
    if item.metaObject().indexOfProperty("section") < 0:
        return None
    try:
        section = item.property("section")
    except RuntimeError:
        return None
    if not isinstance(section, QObject):
        return None
    game = getattr(section, "game", None)
    return game if isinstance(game, str) and game else None


# ---------------------------------------------------------------------------
# Workload driver
# ---------------------------------------------------------------------------


class NavigationWorkload:
    def __init__(self, app: QApplication, viewer, *, step_ms: int = 8):
        self.app = app
        self.viewer = viewer
        self.step_ms = step_ms

        self.phases: list[dict] = []
        self.detail_errors: list[str] = []
        self.details_opened = 0
        self.profiler = cProfile.Profile()

    # -- event loop -------------------------------------------------------

    def pump(self, milliseconds: int = 10):
        """Run a nested event loop for *milliseconds*.

        ``QTest.qWait`` deadlocks in this environment (it never returns while
        a load thread is running), so the driver uses an explicit event loop
        instead.  Calling this from the application's main loop is what gives
        the worker threads and the QML render thread a chance to progress.
        """
        loop = QEventLoop()
        QTimer.singleShot(max(0, milliseconds), loop.quit)
        loop.exec()

    def wait_until(self, predicate, timeout_ms: int, description: str):
        deadline = time.monotonic() + timeout_ms / 1000
        while not predicate():
            if time.monotonic() >= deadline:
                raise RuntimeError(f"timed out waiting for {description}")
            self.pump(10)

    def load_is_idle(self) -> bool:
        if getattr(self.viewer, "_load_in_progress", False):
            return False
        if getattr(self.viewer, "_pending_sections", set()):
            return False
        if not self.viewer.reloadEnabled:
            return False
        sections = self.viewer.sections_model.sections()
        return bool(sections) and all(
            section.characters.rowCount() > 0 for section in sections
        )

    def wait_for_load(self, description: str = "the initial data load"):
        self.wait_until(self.load_is_idle, LOAD_TIMEOUT_MS, description)
        # Let the queued card insertions and image callbacks settle.
        self.pump(250)

    # -- measurement ------------------------------------------------------

    @contextmanager
    def phase(self, name: str):
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        try:
            yield
        finally:
            self.phases.append(
                {
                    "name": name,
                    "wall_seconds": time.perf_counter() - wall_start,
                    "cpu_seconds": time.process_time() - cpu_start,
                }
            )

    def scroll_content(
        self,
        item,
        prop: str,
        *,
        steps: int = 20,
        step_ms: int | None = None,
        return_to_start: bool = True,
    ) -> bool:
        """Animate a ``Flickable``/``ListView`` property through its range."""
        if item is None:
            return False
        extent_prop = "contentWidth" if prop == "contentX" else "contentHeight"
        viewport = item.width() if prop == "contentX" else item.height()
        extent = float(item.property(extent_prop) or 0.0)
        maximum = max(0.0, extent - float(viewport))
        if maximum <= 0:
            return False

        delay = self.step_ms if step_ms is None else step_ms
        for index in range(1, steps + 1):
            item.setProperty(prop, maximum * index / steps)
            self.pump(delay)
        if return_to_start:
            for index in range(steps - 1, -1, -1):
                item.setProperty(prop, maximum * index / steps)
                self.pump(delay)
        return True

    # -- main page --------------------------------------------------------

    def section_list(self):
        return find_qml_item(self.viewer.qml_root(), "sectionList")

    def realized_sections(self) -> dict:
        """Map game id -> realized ``GameSection`` delegate item."""
        section_list = self.section_list()
        if section_list is None:
            return {}
        content_item = section_list.property("contentItem")
        found = {}
        for item in iter_qml_items(content_item):
            game = game_of(item)
            if game and game not in found:
                found[game] = item
        return found

    def scroll_sections_vertically(self):
        with self.phase("main_scroll_vertical"):
            self.scroll_content(
                self.section_list(), "contentY", steps=24, step_ms=self.step_ms
            )

    def scroll_cards_horizontally(self):
        section_list = self.section_list()
        if section_list is None:
            return

        extent = float(section_list.property("contentHeight") or 0.0)
        viewport = float(section_list.height())
        maximum = max(0.0, extent - viewport)
        step = max(120.0, viewport * 0.6)

        seen: set[str] = set()
        y = 0.0
        while True:
            section_list.setProperty("contentY", min(y, maximum))
            self.pump(30)
            for game, item in self.realized_sections().items():
                if game in seen:
                    continue
                card_list = find_qml_item(item, "cardList")
                if card_list is None:
                    continue
                seen.add(game)
                with self.phase(f"cards_scroll_horizontal_{game}"):
                    self.scroll_content(
                        card_list, "contentX", steps=18, step_ms=self.step_ms
                    )
            if y >= maximum:
                break
            y = min(maximum, y + step)

        section_list.setProperty("contentY", 0.0)
        self.pump(80)

    # -- details ----------------------------------------------------------

    def choose_characters(self):
        """Pick two characters per game, preferring cached detail payloads."""
        try:
            from nanoka_viewer.api.details import has_cached_detail
        except Exception:  # pragma: no cover - defensive for older revisions
            has_cached_detail = None

        choices = []
        for section in self.viewer.sections_model.sections():
            ids = list(section.characters.char_ids())
            if not ids:
                continue
            cached = []
            if has_cached_detail is not None:
                for char_id in ids:
                    try:
                        if has_cached_detail(section.game, char_id):
                            cached.append(char_id)
                    except Exception:
                        break
            picked = (cached or ids)[:2]
            choices.append((section.game, picked))
        return choices

    def open_details(self, game: str, char_id: str):
        from nanoka_viewer.ui import details as details_module

        with self.phase(f"details_{game}_{char_id}"):
            self.viewer.openDetails(game, char_id)
            popup = getattr(details_module, "_popup", None)
            if popup is None:
                raise RuntimeError(f"details popup was not created for {game}")

            model = getattr(popup, "_model", None)
            if model is not None:
                self.wait_until(
                    lambda: popup.isVisible()
                    and model.property("state") in ("ready", "error"),
                    DETAIL_TIMEOUT_MS,
                    f"details for {game}/{char_id}",
                )
                # The detail payload is ready; give the deferred build and
                # artwork passes a moment to finish so scrolling measures the
                # real panel rather than the skeleton.
                try:
                    self.wait_until(
                        lambda: model.property("buildState") != "skeleton"
                        and model.property("artState") != "skeleton",
                        20_000,
                        f"details extras for {game}/{char_id}",
                    )
                except RuntimeError:
                    pass
            else:
                self.wait_until(
                    lambda: popup.isVisible(), DETAIL_TIMEOUT_MS, f"details for {game}"
                )
                self.pump(400)

            root = popup._qml.rootObject() if getattr(popup, "_qml", None) else None
            if root is not None:
                self.scroll_content(
                    find_qml_item(root, "detailsScroll"),
                    "contentY",
                    steps=12,
                    step_ms=self.step_ms,
                )

            if model is not None and model.property("state") == "error":
                self.detail_errors.append(f"{game}/{char_id}")
            else:
                self.details_opened += 1

            popup.close_popup()
            self.wait_until(
                lambda: not popup.isVisible(), 5_000, "details popup to close"
            )

    def profile_details(self, choices):
        for game, char_ids in choices:
            for char_id in char_ids:
                self.open_details(game, char_id)

    # -- settings ---------------------------------------------------------

    def settings_workload(self):
        from nanoka_viewer.ui import settings as settings_module

        with self.phase("settings_open"):
            self.viewer.openSettings()
            popup = getattr(settings_module, "_settings_popup", None)
            if popup is None:
                raise RuntimeError("settings popup was not created")
            self.wait_until(
                lambda: popup.isVisible(), 5_000, "settings popup to open"
            )
            model = getattr(popup, "_model", None)
            if model is None:
                raise RuntimeError("settings model is unavailable")
            model.setTab(1)  # View tab
            self.pump(250)

        root = popup._qml.rootObject() if getattr(popup, "_qml", None) else None
        if root is not None:
            with self.phase("settings_scroll_view"):
                self.scroll_content(
                    find_qml_item(root, "settingsViewPage"),
                    "contentY",
                    steps=10,
                    step_ms=self.step_ms,
                )

        games = list(model.games.games())
        if games:
            target = games[-1]
            with self.phase(f"settings_toggle_off_{target}"):
                model.setGameEnabled(target, False)
                self.wait_for_load(f"{target} to be disabled")
            with self.phase(f"settings_toggle_on_{target}"):
                model.setGameEnabled(target, True)
                self.wait_for_load(f"{target} to be enabled")

        order = list(model.order.games())
        if len(order) > 1:
            with self.phase("settings_reorder_to_end"):
                model.moveGame(0, len(order) - 1)
                self.pump(300)
            with self.phase("settings_reorder_to_start"):
                model.moveGame(len(order) - 1, 0)
                self.pump(300)

        with self.phase("settings_close"):
            popup.close_popup()
            self.wait_until(
                lambda: not popup.isVisible(), 5_000, "settings popup to close"
            )
            self.pump(150)

    # -- entry point ------------------------------------------------------

    def run(self) -> dict:
        self.details_opened = 0
        self.detail_errors = []
        self.scroll_sections_vertically()
        self.scroll_cards_horizontally()
        choices = self.choose_characters()
        self.profile_details(choices)
        self.settings_workload()
        return {
            "details_choices": {
                game: char_ids for game, char_ids in choices
            },
            "details_opened": self.details_opened,
            "detail_errors": self.detail_errors,
        }


def aggregate_phases(samples: list[list[dict]]) -> list[dict]:
    """Return the median wall/CPU time for each phase across repetitions."""
    by_name: dict[str, list[dict]] = {}
    order: list[str] = []
    for sample in samples:
        for phase in sample:
            name = phase["name"]
            if name not in by_name:
                by_name[name] = []
                order.append(name)
            by_name[name].append(phase)
    return [
        {
            "name": name,
            "wall_seconds": statistics.median(
                phase["wall_seconds"] for phase in by_name[name]
            ),
            "cpu_seconds": statistics.median(
                phase["cpu_seconds"] for phase in by_name[name]
            ),
            "samples": len(by_name[name]),
        }
        for name in order
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def sanitize(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "-" for char in value
    )
    return cleaned.strip("-") or "unknown"


def git_value(*args: str, cwd: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def make_application() -> QApplication:
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    app.setApplicationName("NanokaLeaks")
    return app


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", help="Branch label stored in the results")
    parser.add_argument("--commit", help="Commit hash stored in the results")
    parser.add_argument(
        "--output-dir",
        default="profiles",
        help="Directory for the .prof, .txt and .json results (default: profiles)",
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_WIDTH, help="Window width"
    )
    parser.add_argument(
        "--height", type=int, default=DEFAULT_HEIGHT, help="Window height"
    )
    parser.add_argument(
        "--step-ms",
        type=int,
        default=8,
        help="Delay between scroll steps in milliseconds (default: 8)",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help=(
            "Measured navigation passes; the JSON reports the median phase "
            "times across them (default: 1)"
        ),
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    repo_root = Path.cwd()
    branch = args.branch or os.environ.get("NANOKA_PROFILE_BRANCH") or git_value(
        "rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root
    )
    commit = args.commit or os.environ.get("NANOKA_PROFILE_COMMIT") or git_value(
        "rev-parse", "--short", "HEAD", cwd=repo_root
    )
    label = sanitize(branch or "unknown")
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    app = make_application()
    from nanoka_viewer.ui.main_window import NanokaViewer

    startup_start = time.perf_counter()
    viewer = NanokaViewer()
    viewer.resize(args.width, args.height)
    viewer.show()
    startup_seconds = time.perf_counter() - startup_start
    load_start = time.perf_counter()

    workload = NavigationWorkload(app, viewer, step_ms=args.step_ms)
    exit_code = {"value": 0}

    def run_workload():
        try:
            workload.wait_for_load()
            loaded_seconds = time.perf_counter() - load_start
            logger.info(
                "Data loaded in %.2fs; starting profiled navigation",
                loaded_seconds,
            )

            repetitions = max(1, args.repetitions)
            repetition_samples = []
            phase_samples = []
            workload.profiler.enable()
            try:
                for index in range(1, repetitions + 1):
                    logger.info(
                        "Measured navigation pass %d/%d", index, repetitions
                    )
                    phase_start = len(workload.phases)
                    navigation_wall = time.perf_counter()
                    navigation_cpu = time.process_time()
                    details = workload.run()
                    repetition_samples.append(
                        {
                            "wall_seconds": time.perf_counter() - navigation_wall,
                            "cpu_seconds": time.process_time() - navigation_cpu,
                        }
                    )
                    phase_samples.append(workload.phases[phase_start:])
            finally:
                workload.profiler.disable()

            navigation_wall = statistics.median(
                sample["wall_seconds"] for sample in repetition_samples
            )
            navigation_cpu = statistics.median(
                sample["cpu_seconds"] for sample in repetition_samples
            )
            phases = aggregate_phases(phase_samples)

            prof_path = output_dir / f"{label}.prof"
            txt_path = output_dir / f"{label}.txt"
            json_path = output_dir / f"{label}.json"

            workload.profiler.dump_stats(str(prof_path))
            with txt_path.open("w", encoding="utf-8") as handle:
                stats = pstats.Stats(workload.profiler, stream=handle)
                stats.sort_stats("cumulative").print_stats(100)
            stats = pstats.Stats(workload.profiler)
            stats.sort_stats("cumulative")
            print(f"\n=== {branch} profile (top 30 by cumulative time) ===")
            stats.print_stats(30)

            from PySide6.QtCore import qVersion

            result = {
                "branch": branch,
                "label": label,
                "commit": commit,
                "source_root": str(repo_root),
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "python": platform.python_version(),
                "qt": qVersion(),
                "platform": platform.platform(),
                "window": {"width": args.width, "height": args.height},
                "step_ms": args.step_ms,
                "repetitions": repetitions,
                "startup_seconds": startup_seconds,
                "load_seconds": loaded_seconds,
                "navigation": {
                    "wall_seconds": navigation_wall,
                    "cpu_seconds": navigation_cpu,
                    "samples": repetition_samples,
                    "total_wall_seconds": sum(
                        sample["wall_seconds"] for sample in repetition_samples
                    ),
                    "total_cpu_seconds": sum(
                        sample["cpu_seconds"] for sample in repetition_samples
                    ),
                },
                "phases": phases,
                "phase_samples": phase_samples,
                "details": details,
                "profile": {
                    "prof": str(prof_path),
                    "txt": str(txt_path),
                },
            }
            json_path.write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
            logger.info("Wrote %s, %s and %s", prof_path, txt_path, json_path)
        except Exception:
            logger.exception("Profiled navigation failed")
            exit_code["value"] = 1
        finally:
            viewer.close()
            app.quit()

    # Run the driver from the real application event loop: QML rendering,
    # queued loader signals and the detail threads all need it.  The driver
    # itself uses nested event loops for its waits.
    QTimer.singleShot(0, run_workload)
    app.exec()
    return exit_code["value"]


if __name__ == "__main__":
    raise SystemExit(main())
