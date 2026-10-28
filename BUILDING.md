# Building NanokaLeaks

This document covers local builds, AppImage packaging, CI, and releases. The
short commands live in [`justfile`](justfile).

## Prerequisites

- **Python 3.13** – `uv` installs the version pinned in `.python-version`.
- **uv** – <https://docs.astral.sh/uv/>
- **just** – <https://github.com/casey/just> (optional; the commands below can
  also be run manually).
- **Linux:** `gcc` (or clang) and `patchelf` on `PATH`.
- **Windows:** Visual Studio Build Tools with the C++ workload. Nuitka uses
  MSVC and its bundled `clcache`.
- **ccache** (optional, recommended on Linux/macOS): Nuitka uses it
  automatically when it is installed.
- **AppImage:** Linux x86_64 only. `appimagetool` is downloaded automatically
  by the packaging script; no system package is required.

Install dependencies once:

```sh
uv sync
```

## Quick start

```sh
just run        # run from source
just test       # unittest suite, headless (offscreen Qt)
just build      # onefile binary at ./NanokaLeaks
just appimage   # AppImage + zsync under dist/
```

`just` runs commands through `uv`, so there is no need to activate `.venv`.

## What gets built

| Output | Recipe | Notes |
| --- | --- | --- |
| `NanokaLeaks` | `just build` | Linux onefile, ~41 MB |
| `NanokaLeaks.exe` | `just build` on Windows | onefile; add `--windows-disable-console` to hide the console (CI does) |
| `dist/NanokaLeaks-<version>-x86_64.AppImage` | `just appimage` | self-contained, ~49 MB |
| `dist/NanokaLeaks-<version>-x86_64.AppImage.zsync` | `just appimage` | delta-update control file, ~170 KB |

The version comes from `pyproject.toml`.

## Tests

The suite uses `unittest` and forces `QT_QPA_PLATFORM=offscreen` in
[`tests/support.py`](tests/support.py), so it runs without a display:

```sh
just test
# verbose:
uv run python -m unittest discover -s tests -v
```

## Onefile binary

`just build` runs:

```sh
uv run nuitka \
    --standalone \
    --onefile \
    --onefile-as-archive \
    --enable-plugin=pyside6 \
    --assume-yes-for-downloads \
    --include-data-files=nanoka_viewer/assets/nanokaleaks.png=nanokaleaks.png \
    -o NanokaLeaks \
    main.py
```

- `--standalone` bundles Python and the Qt/PySide6 libraries.
- `--onefile-as-archive` still produces a single executable, but uses Nuitka's
  archive format so its per-file compression cache can be reused. The default
  stream format recompresses the entire payload on every build (roughly a
  minute on this project).
- `--include-data-files` puts `nanokaleaks.png` beside the executable (inside the
  onefile payload, extracted at runtime). The app loads it from
  `QCoreApplication.applicationDirPath()`, falling back to
  `nanoka_viewer/assets/nanokaleaks.png` when running from source.

Nuitka creates `main.build/`, `main.dist/`, and `main.onefile-build/` as
intermediates. They are ignored by git.

On Windows the same recipe works; add `--windows-disable-console` to hide the
console window (CI does). Nuitka uses clcache automatically with MSVC.

### Caches

Nuitka keeps its caches under the platform cache directory (Linux:
`~/.cache/Nuitka`). Override it with `NUITKA_CACHE_DIR`.

| Path | Contents |
| --- | --- |
| `ccache/` | C objects on Linux/macOS |
| `clcache/` | C objects on Windows/MSVC |
| `module-cache/` | Compiled Python module cache |
| `onefile-compression/` | Compressed onefile payload entries (archive format only) |

`ccache` is used automatically when present. On Windows, Nuitka uses its
bundled `clcache`; no extra install is needed.

Rough timings on a 16-core Linux machine:

| Build | Time |
| --- | --- |
| First build, empty caches | ~2:37 |
| Repeat build, warm caches | ~20–25 s |
| One source file changed, warm caches | ~25 s |

The first build is the slow one. If Nuitka warns that ccache is not being used,
install it with your package manager; the cache is keyed by compiler output, so
it stays useful across unrelated source changes.

To clear Nuitka caches:

```sh
rm -rf ~/.cache/Nuitka
# or, for a single build:
uv run nuitka --clean-cache=all ...
```

## AppImage

`just appimage` runs [`packaging/build_appimage.sh`](packaging/build_appimage.sh).
It builds a **standalone** Nuitka dist (not the onefile payload), assembles an
AppDir, and runs appimagetool:

```text
build/appimage/NanokaLeaks.AppDir/
├── AppRun
├── nanokaleaks.desktop
├── nanokaleaks.png
├── .DirIcon
└── usr/
    ├── bin/                 # copies of main.dist, including nanokaleaks.png
    └── share/icons/hicolor/512x512/apps/nanokaleaks.png
```

Using the standalone dist means the AppImage mounts its squashfs and starts the
binary directly instead of unpacking a temporary onefile copy.

### appimagetool

The script pins appimagetool **1.9.1**, verifies its SHA-256, and downloads it to:

```text
~/.cache/nanokaleaks/appimagetool-1.9.1-x86_64.AppImage
```

It extracts the tool once into the sibling directory. The extracted tool ships
its own `mksquashfs` and `zsyncmake`, so no extra AppImage tooling or FUSE is
needed to build.

### Desktop integration

- `packaging/nanokaleaks.desktop` is the embedded desktop entry.
- `nanoka_viewer/assets/nanokaleaks.png` (512×512) is the icon used for the
  AppImage and for the application window.
- `AppRun` execs `usr/bin/NanokaLeaks` and sets `APPDIR`.

If you replace the icon, keep a 512×512 PNG at the same path (or update the
`--include-data-files` arguments and the AppImage script).

Wayland has no traditional window-icon property: `xdg-shell` carries an
`app_id`, and compositors use either the `xdg_toplevel_icon_v1` protocol or the
desktop entry matched by that `app_id`. The app sets:

```python
app.setDesktopFileName("nanokaleaks")   # matches nanokaleaks.desktop
app.setWindowIcon(icon)                 # sent over xdg_toplevel_icon_v1
```

If you rename the desktop entry, update `setDesktopFileName` and
`StartupWMClass` in the desktop file too. KWin 6.7 and Qt 6.11 support
`xdg_toplevel_icon_v1`; older compositors fall back to the desktop-entry icon.

### Updates (zsync)

The AppImage embeds:

```text
gh-releases-zsync|DejaVu5792|NanokaLeaks|latest|NanokaLeaks-*-x86_64.AppImage.zsync
```

The script generates the matching `.zsync` file with the bundled `zsyncmake`.
`zsyncmake` writes relative to its working directory, so the script invokes it
explicitly instead of relying on appimagetool's internal call.

AppImageUpdate, Gearlever, and similar tools read the embedded information,
download the `.zsync`, and fetch only changed blocks from the latest GitHub
release. Both files must be present in the same release:

```text
NanokaLeaks-<version>-x86_64.AppImage
NanokaLeaks-<version>-x86_64.AppImage.zsync
```

The update information uses `latest` (latest stable release). Forks must change
the owner/repository in `UPDATE_INFO` (or set the `UPDATE_INFO` environment
variable when running the script).

### Testing an AppImage

```sh
./dist/NanokaLeaks-*-x86_64.AppImage
./dist/NanokaLeaks-*-x86_64.AppImage --appimage-updateinformation
```

On systems without FUSE (or with `libfuse2` missing):

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./dist/NanokaLeaks-*-x86_64.AppImage
```

You can check that the zsync metadata matches the AppImage:

```sh
sha1sum dist/NanokaLeaks-*-x86_64.AppImage
grep '^SHA-1:' dist/NanokaLeaks-*-x86_64.AppImage.zsync
```

## CI

The release workflow lives in
[`.github/workflows/release.yml`](.github/workflows/release.yml).

| Trigger | What runs |
| --- | --- |
| Tag `v*` | Linux/Windows onefile builds, AppImage + zsync, GitHub release |
| Push to `main` touching `uv.lock`, `pyproject.toml`, `.python-version`, or the workflow | Cache warm-up only |
| `workflow_dispatch` | Builds binaries/AppImage; publishes a release only when run on a tag |

Pull requests do not run this workflow. The `build` job runs on `ubuntu-latest`
and `windows-latest`; the `appimage` job runs on `ubuntu-latest` and only for
tags or manual dispatches. The release job requires both `build` and `appimage`
to succeed.

### CI cache

CI points `NUITKA_CACHE_DIR` at `.nuitka-cache` in the workspace and restores
it with `actions/cache`, keyed by OS, `uv.lock` hash, and commit SHA. `ccache`
is installed on Ubuntu; Windows uses clcache.

GitHub cache entries are **ref-scoped**:

- A tag build can restore a cache from the default branch (`main`) or its own
  tag, not from other tags.
- The `main` push triggers exist to warm the default-branch cache for later
  releases.
- Caches unused for 7 days may be evicted; infrequent releases can start cold.
- `workflow_dispatch` on `main` is a convenient way to warm the cache before
  tagging.

### Release assets

The release job collects:

```text
NanokaLeaks                      # Linux onefile
NanokaLeaks.exe                  # Windows onefile
NanokaLeaks-<version>-x86_64.AppImage
NanokaLeaks-<version>-x86_64.AppImage.zsync
```

## Release checklist

1. Update `version` in `pyproject.toml`, refresh the lockfile, and commit the
   bump:

   ```sh
   uv lock
   git add pyproject.toml uv.lock
   git commit -m "bump version"
   ```

2. Run the suite and a local build:

   ```sh
   just test
   just build
   just appimage
   ```

3. Push `main`; optionally dispatch the workflow on `main` first to warm the CI
   cache.

4. Tag the release commit (on `main`) and push the tag:

   ```sh
   git tag v<version>
   git push origin v<version>
   ```

5. Verify the release has both the AppImage and its `.zsync`, and that
   `--appimage-updateinformation` prints the expected string.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| First build takes minutes | Expected; install ccache and keep `~/.cache/Nuitka` for repeat builds |
| `ccache` not found warning | Install ccache (`apt install ccache`, `dnf install ccache`, `brew install ccache`, etc.) |
| `patchelf` missing | Install `patchelf`; it is required by Nuitka standalone on Linux |
| AppImage does not start | Install FUSE/`libfuse2`, or run with `APPIMAGE_EXTRACT_AND_RUN=1` |
| No titlebar icon on Wayland | Check `setDesktopFileName` matches the installed `.desktop` name and the icon is at `nanokaleaks.png` next to the executable |
| `.zsync` missing after packaging | The script fails if zsyncmake did not produce it; remove the appimagetool extraction cache and rebuild |
| Updates not detected | The latest GitHub release must contain both the AppImage and `.zsync`; check `--appimage-updateinformation` |
| CI cache never hits | Tag caches are isolated; warm the default branch or use `workflow_dispatch` on `main` |

## Generated files

These are build products and are gitignored:

```text
main.build/        main.dist/        main.onefile-build/
build/appimage/    dist/
NanokaLeaks        NanokaLeaks.exe
.nuitka-cache/     # CI workspace cache
```

For a clean rebuild:

```sh
rm -rf main.build main.dist main.onefile-build build/appimage dist NanokaLeaks
```

Do not delete `~/.cache/Nuitka` unless you are troubleshooting; it is what makes
repeat builds fast.
