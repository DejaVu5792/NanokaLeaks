run:
    uv run main.py

# Nuitka caches C objects and the onefile payload in ~/.cache/Nuitka, so
# installing ccache makes repeat builds substantially faster.
build:
    #!/usr/bin/env bash
    set -euo pipefail

    uv run nuitka \
        --standalone \
        --onefile \
        --onefile-as-archive \
        --enable-plugin=pyside6 \
        --assume-yes-for-downloads \
        --include-data-files=nanoka_viewer/assets/nanokaleaks.png=nanokaleaks.png \
        --include-data-dir=nanoka_viewer/qml=nanoka_viewer/qml \
        --include-qt-plugins=qml \
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
