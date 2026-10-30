"""Lint every shipped QML source with qmllint.

Syntax errors in QML are otherwise only discovered at window startup, which
makes them easy to miss on CI where the suite runs headless against a QML
tree that may never have been parsed.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

from support import DETAILS_ROOT


def _qmllint_binary() -> str | None:
    binary = shutil.which("pyside6-qmllint")
    if binary:
        return binary
    try:
        import PySide6

        candidate = Path(PySide6.__file__).parent / "qmllint"
        if candidate.exists():
            return str(candidate)
    except ImportError:  # pragma: no cover - PySide6 is a hard dependency
        pass
    return None


class QmlLintTests(unittest.TestCase):
    def test_all_qml_sources_lint_without_errors(self):
        binary = _qmllint_binary()
        if binary is None:  # pragma: no cover - tooling ships with PySide6
            self.skipTest("qmllint is not available")

        sources = sorted(
            (Path(DETAILS_ROOT) / "nanoka_viewer" / "qml").rglob("*.qml")
        )
        self.assertTrue(sources, "no QML sources found to lint")

        result = subprocess.run(
            [binary, *map(str, sources)],
            capture_output=True,
            text=True,
            cwd=DETAILS_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"qmllint reported errors:\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
