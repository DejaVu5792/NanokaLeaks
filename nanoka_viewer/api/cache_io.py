"""Small helpers for safe cache-file I/O."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write *data* through a temp file so readers never see a partial cache.

    The preload worker and the details popup can race for the same cache
    entry.  ``os.replace`` makes the swap atomic, so a reader either sees the
    old complete file or the new complete file, never a half-written payload.
    """
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def directory_size_bytes(directory: Path) -> int:
    """Return the total size of regular files under *directory* in bytes."""
    total = 0
    try:
        entries = directory.rglob("*")
        for entry in entries:
            try:
                if entry.is_file():
                    total += entry.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total
