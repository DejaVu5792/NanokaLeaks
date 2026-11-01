#!/usr/bin/env bash
# Shared Nuitka flags for every build (just build, packaging/build_appimage.sh
# and the release workflow). Source it from the repository root:
#
#     source packaging/nuitka_flags.sh
#     uv run nuitka ... "${nuitka_flags[@]}" ...
#
# Keep all data-file/QML/plugin flags here so the builds cannot drift apart;
# without --include-data-dir the frozen binary cannot find nanoka_viewer/qml.
nuitka_flags=(
    --enable-plugin=pyside6
    --assume-yes-for-downloads
    --include-data-files=nanoka_viewer/assets/nanokaleaks.png=nanokaleaks.png
    --include-data-dir=nanoka_viewer/qml=nanoka_viewer/qml
    --include-qt-plugins=qml
)
