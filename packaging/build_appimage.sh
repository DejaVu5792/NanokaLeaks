#!/usr/bin/env bash
# Build a standalone AppImage from the Nuitka dist folder.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -n1)"
ARCH="$(uname -m)"

if [ "$(uname -s)" != "Linux" ]; then
    echo "build_appimage.sh only runs on Linux" >&2
    exit 1
fi

if [ "$ARCH" != "x86_64" ]; then
    echo "build_appimage.sh currently supports x86_64 only (got $ARCH)" >&2
    exit 1
fi

APPIMAGETOOL_VERSION="${APPIMAGETOOL_VERSION:-1.9.1}"
APPIMAGETOOL_SHA256="${APPIMAGETOOL_SHA256:-ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0}"
APPIMAGETOOL="${APPIMAGETOOL:-${XDG_CACHE_HOME:-$HOME/.cache}/nanokaleaks/appimagetool-${APPIMAGETOOL_VERSION}-${ARCH}.AppImage}"
UPDATE_INFO="${UPDATE_INFO:-gh-releases-zsync|DejaVu5792|NanokaLeaks|latest|NanokaLeaks-*-x86_64.AppImage.zsync}"

if [ ! -x "$APPIMAGETOOL" ]; then
    mkdir -p "$(dirname "$APPIMAGETOOL")"
    URL="https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage"
    echo "Downloading appimagetool ${APPIMAGETOOL_VERSION}..."
    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 -o "$APPIMAGETOOL" "$URL"
    else
        wget -O "$APPIMAGETOOL" "$URL"
    fi
    chmod +x "$APPIMAGETOOL"
fi

if [ -n "$APPIMAGETOOL_SHA256" ]; then
    echo "$APPIMAGETOOL_SHA256  $APPIMAGETOOL" | sha256sum -c -
fi

# Extract once so we can use the bundled mksquashfs/zsyncmake without FUSE.
APPIMAGETOOL_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/nanokaleaks/appimagetool-${APPIMAGETOOL_VERSION}-${ARCH}"
if [ ! -x "$APPIMAGETOOL_DIR/squashfs-root/AppRun" ]; then
    rm -rf "$APPIMAGETOOL_DIR"
    mkdir -p "$APPIMAGETOOL_DIR"
    (
        cd "$APPIMAGETOOL_DIR"
        "$APPIMAGETOOL" --appimage-extract >/dev/null
    )
fi
APPIMAGETOOL_RUN="$APPIMAGETOOL_DIR/squashfs-root/AppRun"
ZSYNC_MAKE="$APPIMAGETOOL_DIR/squashfs-root/usr/bin/zsyncmake"

echo "Building standalone Nuitka distribution..."

# Qt QML modules that nothing in the bundle imports. --include-qt-plugins=qml
# ships every module it finds, and each module's plugin DLL pulls its shared
# library dependency chain along (QtWebEngine alone is ~200 MB), so the unused
# modules are dropped here - QML sources and plugin binaries alike. Only
# exclude a module if no shipped QML file imports it. Keep this list in sync
# with the justfile `build` recipe and .github/workflows/release.yml.
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
    --enable-plugin=pyside6 \
    --assume-yes-for-downloads \
    --include-data-files=nanoka_viewer/assets/nanokaleaks.png=nanokaleaks.png \
    --include-data-dir=nanoka_viewer/qml=nanoka_viewer/qml \
    --include-qt-plugins=qml \
    "${qml_flags[@]}" \
    -o NanokaLeaks \
    main.py

APPDIR="$ROOT/build/appimage/NanokaLeaks.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/icons/hicolor/512x512/apps" "$ROOT/dist"

cp -a "$ROOT/main.dist/." "$APPDIR/usr/bin/"
install -m 755 "$ROOT/packaging/AppRun" "$APPDIR/AppRun"
install -m 644 "$ROOT/packaging/nanokaleaks.desktop" "$APPDIR/nanokaleaks.desktop"
install -m 644 "$ROOT/nanoka_viewer/assets/nanokaleaks.png" "$APPDIR/nanokaleaks.png"
install -m 644 "$ROOT/nanoka_viewer/assets/nanokaleaks.png" "$APPDIR/.DirIcon"
install -m 644 "$ROOT/nanoka_viewer/assets/nanokaleaks.png" \
    "$APPDIR/usr/share/icons/hicolor/512x512/apps/nanokaleaks.png"

OUTPUT="$ROOT/dist/NanokaLeaks-${VERSION}-${ARCH}.AppImage"
rm -f "$OUTPUT" "$OUTPUT.zsync"
(
    cd "$ROOT/dist"
    ARCH="$ARCH" VERSION="$VERSION" "$APPIMAGETOOL_RUN" \
        --no-appstream \
        --updateinformation "$UPDATE_INFO" \
        "$APPDIR" \
        "$OUTPUT"
)

# zsyncmake writes relative to its working directory and appimagetool runs it
# inside its extracted runtime, so generate the control file explicitly.
"$ZSYNC_MAKE" -u "$(basename "$OUTPUT")" -o "$OUTPUT.zsync" "$OUTPUT"

if [ ! -f "$OUTPUT.zsync" ]; then
    echo "Failed to create $OUTPUT.zsync" >&2
    exit 1
fi
echo "Created $OUTPUT"
echo "Created $OUTPUT.zsync"
