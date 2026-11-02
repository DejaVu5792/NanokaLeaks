.pragma library

// Shared palette-derived tints.
//
// The loading skeletons used to repeat the same 50/50 Midlight/Mid blend in
// three files; keep the formula here so the placeholder colour stays identical
// everywhere.
function skeletonColor(palette) {
    return Qt.rgba(
        (palette.midlight.r + palette.mid.r) / 2,
        (palette.midlight.g + palette.mid.g) / 2,
        (palette.midlight.b + palette.mid.b) / 2,
        1)
}
