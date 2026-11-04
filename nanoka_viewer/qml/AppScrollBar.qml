import QtQuick
import QtQuick.Controls

// The thin overlay scrollbar used by the settings and details pages.
ScrollBar {
    policy: ScrollBar.AsNeeded
    // AsNeeded can keep the bar visible after the page shrinks to fit (it is
    // re-evaluated on size changes only), so also track the size.
    visible: size < 1.0

    contentItem: Rectangle {
        implicitWidth: 6
        radius: 3
        color: palette.mid
    }

    background: Rectangle { color: "transparent" }
}
