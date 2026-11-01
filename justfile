run:
    uv run main.py

# Nuitka caches C objects and the onefile payload in ~/.cache/Nuitka, so
# installing ccache makes repeat builds substantially faster.
build:
    #!/usr/bin/env bash
    set -euo pipefail

    source packaging/nuitka_flags.sh

    uv run nuitka \
        --standalone \
        --onefile \
        --onefile-as-archive \
        "${nuitka_flags[@]}" \
        -o NanokaLeaks \
        main.py

# Build a standalone AppImage under dist/. Downloads appimagetool on first use.
appimage:
    packaging/build_appimage.sh

test:
    uv run python -m unittest discover -s tests

# qmllint over every shipped QML source (also run as a unittest).
lint:
    uv run pyside6-qmllint $(find nanoka_viewer/qml -name '*.qml')
