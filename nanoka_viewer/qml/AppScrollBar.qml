import QtQuick
import QtQuick.Controls

// The thin overlay scrollbar used by the main list, the settings and details
// pages, and the card strips.
//
// Hover signals interactivity by tinting the handle, never by changing its
// thickness: the KDE HIG asks controls to signal interactivity with a hover
// effect that changes their background or outline, and Breeze keeps the
// scrollbar width constant so hovering cannot reflow the content next to it
// (KDE bug 414763).
ScrollBar {
    id: control

    policy: ScrollBar.AsNeeded
    // AsNeeded can keep the bar visible after the page shrinks to fit (it is
    // re-evaluated on size changes only), so also track the size.
    visible: size < 1.0

    // Control only tracks hover when asked to.
    hoverEnabled: true

    // Blend towards the text colour, which contrasts with the window in both
    // light and dark palettes; palette.dark would vanish against a dark
    // window.  Pressing goes a step further so dragging reads as a distinct
    // state.
    readonly property color hoverColor: Qt.tint(
        palette.mid,
        Qt.rgba(palette.text.r, palette.text.g, palette.text.b, 0.35)
    )
    readonly property color pressedColor: Qt.tint(
        palette.mid,
        Qt.rgba(palette.text.r, palette.text.g, palette.text.b, 0.6)
    )

    contentItem: Rectangle {
        // A vertical bar is sized by implicitWidth, a horizontal one by
        // implicitHeight.  Setting both keeps this shared component visible
        // in either orientation (the old per-page bars did exactly that).
        implicitWidth: 6
        implicitHeight: 6
        radius: 3
        color: control.pressed
            ? control.pressedColor
            : control.hovered
                ? control.hoverColor
                : palette.mid

        // Hover is a hint, not a jump: crossfade between the shades the way
        // qqc2-desktop-style crossfades its scrollbar styles.
        Behavior on color {
            ColorAnimation { duration: 120 }
        }
    }

    background: Rectangle { color: "transparent" }
}
