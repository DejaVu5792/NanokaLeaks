import QtQuick
import QtQuick.Controls

// The thin overlay scrollbar used by the settings and details pages.
ScrollBar {
    policy: ScrollBar.AsNeeded
    // AsNeeded can keep the bar visible after the page shrinks to fit (it is
    // re-evaluated on size changes only), so also track the size.
    visible: size < 1.0

    contentItem: Rectangle {
        // A vertical bar is sized by implicitWidth, a horizontal one by
        // implicitHeight.  Setting both keeps this shared component visible
        // in either orientation (the old per-page bars did exactly that).
        implicitWidth: 6
        implicitHeight: 6
        radius: 3
        color: palette.mid
    }

    background: Rectangle { color: "transparent" }
}
