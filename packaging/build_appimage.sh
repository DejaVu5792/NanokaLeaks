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

echo "Building standalone Nuitka distribution..."
uv run nuitka \
    --standalone \
    --enable-plugin=pyside6 \
    --assume-yes-for-downloads \
    --include-data-files=nanoka_viewer/assets/nanokaleaks.png=nanokaleaks.png \
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
rm -f "$OUTPUT"
ARCH="$ARCH" VERSION="$VERSION" "$APPIMAGETOOL" \
    --appimage-extract-and-run \
    --no-appstream \
    "$APPDIR" \
    "$OUTPUT"
echo "Created $OUTPUT"
