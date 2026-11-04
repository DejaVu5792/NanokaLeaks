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
    --include-package-data=certifi
    --include-data-files=nanoka_viewer/assets/nanokaleaks.png=nanokaleaks.png
    --include-data-dir=nanoka_viewer/qml=nanoka_viewer/qml
    --include-qt-plugins=qml
)

# Qt QML modules that nothing in the bundle imports.
#
# --include-qt-plugins=qml makes Nuitka walk the whole PySide6/Qt/qml tree and
# ship every module it finds, together with each module's plugin libraries and
# their shared-library dependency chain (QtWebEngine alone is about 200 MB on
# disk). Dropping the unused modules takes the onefile payload from ~136 MB to
# ~41 MB, and removes ~2100 of the ~2300 files that Nuitka compresses one at a
# time while packing: each file gets a fresh zstd level-22 stream, and the
# context setup alone costs ~360 ms regardless of file size, so those files are
# what make a cold onefile build take 10-15 minutes.
#
# Only exclude a module that no shipped QML file imports. QtQuick.Shapes must
# stay, for example, because the Controls "Basic" style imports it. The viewer
# imports QtQuick, QtQuick.Controls (plus its `impl` submodule and the Fusion
# style) and QtQuick.Layouts.
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

for module in "${qml_excluded[@]}"; do
    nuitka_flags+=(
        --noinclude-data-files="PySide6/qml/$module"
        --noinclude-dlls="PySide6/qml/$module/*"
    )
done

# Qt shared libraries that only exist for modules the viewer never imports.
#
# --include-qt-plugins=qml makes Nuitka pull every QML plugin, and it follows
# each plugin's dependency chain into the Qt libraries before the QML file
# exclusions above are applied. The result is a bundle carrying most of the Qt
# SDK: QtWebEngineCore alone is ~195 MB, and Qt 3D, Charts, Multimedia, Pdf and
# the unused Controls styles add another ~60 MB.
#
# These are matched against the destination filename, so they sit at the
# distribution root. Four namespaces are deliberately kept: QtQuick (plus
# Controls/Controls2 Templates/Basic/Fusion/Impl, Layouts, Shapes, Window),
# QtQml, QtSvg (theme icons) and the platform integration (XcbQpa, Wayland).
qt_libs_excluded=(
    libQt6WebEngine* libQt6WebChannel* libQt6WebView*
    libQt6WebSockets* libQt6Positioning*
    libQt6Quick3D* libQt63D* libQt6ShaderTools* libQt6SpatialAudio*
    libQt6Charts* libQt6DataVisualization* libQt6Graphs*
    libQt6Multimedia* libQt6Pdf* libQt6VirtualKeyboard*
    libQt6RemoteObjects* libQt6Scxml* libQt6Sensors* libQt6StateMachine*
    libQt6TextToSpeech* libQt6Location* libQt6Labs*
    libQt6QuickTimeline* libQt6QuickParticles* libQt6QuickEffects*
    libQt6QuickVectorImage* libQt6QuickDialogs2* libQt6QuickTest*
    libQt6Test* libQt6Sql* libQt6QmlLocalStorage*
    libQt6QuickControls2FluentWinUI3* libQt6QuickControls2Imagine*
    libQt6QuickControls2Material* libQt6QuickControls2Universal*
    libQt6WaylandCompositor* libQt6EglFS* libQt6EglFsKmsSupport*
)

for lib in "${qt_libs_excluded[@]}"; do
    nuitka_flags+=(--noinclude-dlls="$lib")
done

# Shared libraries nothing in the bundle links any more; they are leftovers of
# the Qt SDK and Addons chains dropped above.
#
#   libcrypto.so.3 / libssl.so.3 - OpenSSL 3. Python links OpenSSL 4 (that pair
#     is kept, requests needs it), and the Qt TLS plugin is dropped below.
#   libavif-* - no image-format plugin in the bundle references it.
qt_orphan_libs=(libcrypto.so.3 libssl.so.3 libavif-*)

for lib in "${qt_orphan_libs[@]}"; do
    nuitka_flags+=(--noinclude-dlls="$lib")
done

# Qt plugins the viewer never loads. Image formats stay limited to what the
# artwork and theme icons use: PNG (built into Qt), JPEG, WebP and SVG.
qt_plugins_excluded=(
    "PySide6/qt-plugins/tls/*"
    "PySide6/qt-plugins/printsupport/*"
    "PySide6/qt-plugins/imageformats/*tiff*"
    "PySide6/qt-plugins/imageformats/*wbmp*"
    "PySide6/qt-plugins/imageformats/*tga*"
    "PySide6/qt-plugins/imageformats/*icns*"
    "PySide6/qt-plugins/imageformats/*qpdf*"
)

for plugin in "${qt_plugins_excluded[@]}"; do
    nuitka_flags+=(--noinclude-dlls="$plugin")
done
