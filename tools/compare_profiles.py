#!/usr/bin/env python3
"""Compare two ``profile_navigation.py`` JSON reports.

Usage:
    python tools/compare_profiles.py profiles/main.json profiles/perf.json

The first file is treated as the baseline (``main``) and the second as the
current branch.  Phase wall/CPU times come from the JSON summary; the function
tables come from the matching ``.prof`` files written next to it.
"""

from __future__ import annotations

import argparse
import json
import pstats
from pathlib import Path

HARNESS_FILES = ("tools/profile_navigation.py",)


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def seconds(value: float | None) -> str:
    if value is None:
        return "-"
    if value < 1:
        return f"{value * 1000:.0f} ms"
    return f"{value:.2f} s"


def delta(current: float, baseline: float) -> str:
    if baseline == 0:
        return "-"
    change = (current - baseline) / baseline * 100
    return f"{change:+.1f}%"


def phase_map(report: dict) -> dict[str, dict]:
    return {phase["name"]: phase for phase in report.get("phases", [])}


def print_summary(baseline: dict, current: dict):
    print("=" * 78)
    print(f"baseline: {baseline['branch']} @ {baseline.get('commit') or '?'}")
    print(f"current:  {current['branch']} @ {current.get('commit') or '?'}")
    print("=" * 78)
    print(f"{'metric':<26}{'baseline':>14}{'current':>14}{'delta':>12}")
    rows = (
        ("startup", "startup_seconds"),
        ("initial load", "load_seconds"),
        ("navigation wall", ("navigation", "wall_seconds")),
        ("navigation CPU", ("navigation", "cpu_seconds")),
    )
    for label, key in rows:
        if isinstance(key, tuple):
            base_value = baseline[key[0]][key[1]]
            cur_value = current[key[0]][key[1]]
        else:
            base_value = baseline[key]
            cur_value = current[key]
        print(
            f"{label:<26}{seconds(base_value):>14}"
            f"{seconds(cur_value):>14}{delta(cur_value, base_value):>12}"
        )


def print_phase_table(baseline: dict, current: dict):
    base_phases = phase_map(baseline)
    cur_phases = phase_map(current)
    names = list(base_phases)
    names += [name for name in cur_phases if name not in base_phases]

    print("\nPhases (wall time; CPU in parentheses)")
    print(f"{'phase':<36} {'baseline':>17} {'current':>17} {'delta':>9}")
    print("-" * 82)
    total_base = total_cur = 0.0
    for name in names:
        base = base_phases.get(name)
        cur = cur_phases.get(name)
        base_wall = base["wall_seconds"] if base else 0.0
        cur_wall = cur["wall_seconds"] if cur else 0.0
        total_base += base_wall
        total_cur += cur_wall
        change = delta(cur_wall, base_wall) if base and cur else "-"
        base_text = (
            f"{seconds(base_wall)} ({seconds(base['cpu_seconds'])})"
            if base
            else "-"
        )
        cur_text = (
            f"{seconds(cur_wall)} ({seconds(cur['cpu_seconds'])})"
            if cur
            else "-"
        )
        print(f"{name:<36} {base_text:>17} {cur_text:>17} {change:>9}")
    print("-" * 82)
    print(
        f"{'sum of phases':<36} {seconds(total_base):>17}"
        f" {seconds(total_cur):>17} {delta(total_cur, total_base):>9}"
    )


NETWORK_MARKERS = (
    "/requests/",
    "/urllib3/",
    "/http/client.py",
    "/socket.py",
    "/ssl.py",
    "/ssl_.py",
)


def is_harness(filename: str) -> bool:
    return any(filename.endswith(name) for name in HARNESS_FILES)


def is_network(filename: str, name: str = "") -> bool:
    if any(marker in filename for marker in NETWORK_MARKERS):
        return True
    # C-level SSL reads are reported with a "~" filename and no Python frame.
    if filename == "~" and "ssl" in name.lower():
        return True
    return False


def canonical_filename(filename: str, source_root: str) -> str:
    """Make paths from two checkouts comparable.

    The baseline runs from a temporary worktree, so its ``nanoka_viewer/...``
    paths have a different prefix than the current checkout.  Stripping the
    checkout root and the virtualenv prefix turns the same function into the
    same key in both profiles.
    """
    if filename == "~":
        return filename
    if source_root:
        prefix = source_root.rstrip("/") + "/"
        if filename.startswith(prefix):
            return filename[len(prefix) :]
    for marker in ("/site-packages/", "/.venv/"):
        if marker in filename:
            return filename.split(marker, 1)[1]
    return filename


def profile_entries(report: dict) -> dict[tuple, tuple]:
    """Return {(file, line, function): (calls, tottime, cumtime)}.

    The driver and the network stack are filtered out of the function tables:
    navigation wall/CPU already accounts for their cost, and the HTTP jitter
    would otherwise dominate the per-function deltas.
    """
    prof_path = report.get("profile", {}).get("prof")
    if not prof_path or not Path(prof_path).is_file():
        return {}
    source_root = report.get("source_root", "")
    stats = pstats.Stats(prof_path)
    entries = {}
    for (filename, lineno, name), (_cc, nc, tt, ct, _callers) in stats.stats.items():
        if is_harness(filename) or is_network(filename, name):
            continue
        # The driver waits on (and scrolls through) the event loop; those rows
        # only measure the harness, not the application code.
        if name in ("qWait", "processEvents") and "PySide6" in filename:
            continue
        if filename == "~" and "QEventLoop" in name:
            continue
        key = (canonical_filename(filename, source_root), lineno, name)
        entries[key] = (nc, tt, ct)
    return entries


def short_name(key: tuple) -> str:
    filename, lineno, name = key
    if filename == "~":
        return f"<C> {name}"
    return f"{Path(filename).name}:{lineno} {name}"


def print_function_table(baseline: dict, current: dict):
    base_entries = profile_entries(baseline)
    cur_entries = profile_entries(current)
    if not base_entries or not cur_entries:
        return

    print("\nTop self time (tottime)")
    print(f"{'function':<52} {'baseline':>11} {'current':>11} {'delta':>9}")
    print("-" * 86)
    top_keys = set()
    for entries in (base_entries, cur_entries):
        top_keys.update(
            key
            for key, _value in sorted(
                entries.items(), key=lambda item: item[1][1], reverse=True
            )[:12]
        )
    for key in sorted(
        top_keys,
        key=lambda key: max(
            base_entries.get(key, (0, 0, 0))[1],
            cur_entries.get(key, (0, 0, 0))[1],
        ),
        reverse=True,
    )[:18]:
        base_tt = base_entries.get(key, (0, 0, 0))[1]
        cur_tt = cur_entries.get(key, (0, 0, 0))[1]
        print(
            f"{short_name(key):<52} {seconds(base_tt):>11}"
            f" {seconds(cur_tt):>11} {delta(cur_tt, base_tt):>9}"
        )

    print("\nLargest self-time changes (common functions)")
    print(f"{'function':<52} {'baseline':>11} {'current':>11} {'delta':>9}")
    print("-" * 86)
    common = set(base_entries) & set(cur_entries)
    rows = []
    for key in common:
        base_tt = base_entries[key][1]
        cur_tt = cur_entries[key][1]
        rows.append((abs(cur_tt - base_tt), key, base_tt, cur_tt))
    for _change, key, base_tt, cur_tt in sorted(rows, reverse=True)[:20]:
        print(
            f"{short_name(key):<52} {seconds(base_tt):>11}"
            f" {seconds(cur_tt):>11} {delta(cur_tt, base_tt):>9}"
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    args = parser.parse_args(argv)

    baseline = load_report(args.baseline)
    current = load_report(args.current)
    print_summary(baseline, current)
    print_phase_table(baseline, current)
    print_function_table(baseline, current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
