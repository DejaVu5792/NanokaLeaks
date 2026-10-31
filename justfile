run:
    uv run main.py

# Nuitka caches C objects and the onefile payload in ~/.cache/Nuitka, so
# installing ccache makes repeat builds substantially faster.
build:
    #!/usr/bin/env bash
    set -euo pipefail

    # Qt QML modules that nothing in the bundle imports. --include-qt-plugins=qml
    # ships every module it finds, and each module's plugin DLL pulls its shared
    # library dependency chain along (QtWebEngine alone is ~200 MB), so the
    # unused modules are dropped here - QML sources and plugin binaries alike.
    # Only exclude a module if no shipped QML file imports it: QtQuick.Shapes,
    # for example, must stay because the Controls "Basic" style uses it.
    # Keep this list in sync with packaging/build_appimage.sh and
    # .github/workflows/release.yml.
    qml_excluded=(
        Qt3D Qt5Compat QtCharts QtDataVisualization QtGraphs QtLocation
        QtMultimedia QtPositioning QtQuick3D QtRemoteObjects QtScxml
        QtSensors QtTest QtTextToSpeech QtWayland QtWebChannel QtWebEngine
        QtWebSockets QtWebView
        Qt/labs
        QtQuick/Dialogs QtQuick/Effects QtQuick/LocalStorage QtQuick/Pdf
        QtQuick/Particles QtQuick/Scene2D QtQuick/Scene3D QtQuick/Timeline
        QtQuick/VectorImage QtQuick/VirtualKeyboard QtQuick/tooling
        QtQuick/Controls/FluentWinUI3 QtQuick/Controls/Imagine
        QtQuick/Controls/Material QtQuick/Controls/Universal
        QtQuick/Controls/designer
        QtQml/StateMachine
    )
    qml_flags=()
    for module in "${qml_excluded[@]}"; do
        qml_flags+=(--noinclude-data-files="PySide6/qml/$module"
                    --noinclude-dlls="PySide6/qml/$module/*")
    done

    uv run nuitka \
        --standalone \
        --onefile \
        --onefile-as-archive \
        --enable-plugin=pyside6 \
        --assume-yes-for-downloads \
        --include-data-files=nanoka_viewer/assets/nanokaleaks.png=nanokaleaks.png \
        --include-data-dir=nanoka_viewer/qml=nanoka_viewer/qml \
        --include-qt-plugins=qml \
        "${qml_flags[@]}" \
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
