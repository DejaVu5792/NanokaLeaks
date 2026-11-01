# UI architecture

The window is a Qt Widgets shell around a QML tree. This note records where the
boundary is and which parts of the hybrid are deliberate, so the next change does
not have to rediscover it.

## The split

- **QML** (`nanoka_viewer/qml/`) owns layout, animation, focus and scrolling.
  It holds no business logic: no HTTP, no caching, no file paths.
- **Python** (`nanoka_viewer/ui/`) owns state, threading and I/O, and exposes it
  through view models and Qt properties.

The QML tree reaches Python through context properties installed by
`qml_host.create_qml_widget()` before `setSource()` runs:

| Context property | Type | Used by |
| --- | --- | --- |
| `viewer` | `NanokaViewer` (`QObject` + `Property`) | `Main.qml`, `HeaderBar.qml`, `CharacterCard.qml` |
| `sections` | `SectionsModel` (`QAbstractListModel`) | `Main.qml` (`ListView.model`) |
| `details` | `DetailsViewModel` | `details/DetailsPanel.qml`, `details/ArtPanel.qml` |
| `settings` | `SettingsViewModel` | `settings/SettingsPanel.qml` |

Images never cross that boundary as `QPixmap`. They are served by `image://`
providers (`NanokaImageProvider`, and `NanokaArtProvider` for details artwork),
which keeps decoding, caching and rescaling on the Python side.

## The main tree is a QQuickWidget in a QMainWindow

`NanokaViewer` stays a `QMainWindow` because window management, the application
icon, desktop-file integration and the confirmation dialogs are cheaper there
than in QML. The content is one `QQuickWidget` (`qml_host.create_qml_widget`)
that fills the window.

`styles.py` is the remaining widget chrome: the window background, plain
`QPushButton`s used by `QMessageBox`, and transparent popup hosts. Do not add
new QSS for application UI; new visuals belong in QML.

## Overlays: QML content hosted in a QWidget

Details and settings render QML overlays but are hosted in a full-size child
`QWidget` (`popup_host.PopupHost`) rather than a QML `Popup`/`Overlay` inside
the main scene. That is deliberate:

- The host covers the central widget, so the overlay is above the
  `QQuickWidget` regardless of how Qt stacks native child surfaces. This is the
  case that breaks with a native child window (the Wayland/`WA_NativeWindow`
  anchor covered by `tests/test_native_stacking.py`).
- Modal input blocking is enforced at the widget level, not only by the QML
  backdrop: `PopupHost` installs an application event filter and drops input
  aimed at the host while the overlay is open.
- Closing returns focus to the triggering widget and clears stale hover state,
  which a Wayland click can otherwise leave behind.

The cost is roughly 300 lines of host plumbing (geometry re-sync, raising,
focus, input guard). Replacing it with QML `Popup` is only worth doing as a
full rewrite of both overlays, because the behaviour above is verified by
widget-level tests and cannot be checked headless any other way.

`details.py` and `settings.py` are controllers, not leftovers: they own load
threads, request generations, settings merging and cache actions. That is why
the Python side stays larger than the QML side even after the migration.

## Packaging

QML files are data, not imports. Nuitka cannot discover them, so every build
must ship `nanoka_viewer/qml` explicitly (`--include-data-dir`). A build that
forgets it compiles cleanly and then dies at startup with
`QML directory not found`. Keep the QML directory in the shared build flags, and
run the produced binary once before publishing.

## Rules of thumb

- New visual element → a `.qml` file.
- New state → a property on a view model, never a `globalThis` or a JS model.
- New image source → an `image://` provider.
- New widget styling → reconsider; it probably belongs in QML.
