# NanokaLeaks
Quick VIBE CODED python script to quickly view newest characters in games tracked by [nanoka](https://nanoka.cc/)

## Building
`just build` produces a single-file binary with Nuitka. The first build is the slow one; Nuitka caches compiled C objects, bytecode, and the onefile payload, so repeat builds are much faster. Install `ccache` on Linux/macOS (`ccache` is used automatically by Nuitka) to make rebuilds after source changes fast too. On Windows, Nuitka uses its bundled `clcache` with MSVC.

`just appimage` builds a standalone AppImage at `dist/NanokaLeaks-<version>-x86_64.AppImage`. It downloads appimagetool 1.9.1 on first use; the AppImage bundles the standalone dist rather than the onefile payload, so startup does not unpack a temporary copy. The AppImage embeds GitHub release update information and a matching `.zsync` file is generated for AppImageUpdate/Gearlever.

# Disclaimer
This is pure AI slop, made for personal use.
