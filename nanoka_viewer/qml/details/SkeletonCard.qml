pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

import "../Theme.js" as Theme
import ".."

// One card-shaped loading placeholder: rows of pulsing bars.
//
// ``rows`` is a list of rows and each row is a list of ``[weight, height]``
// pairs, mirroring the width ratios the widget skeleton used.
Rectangle {
    id: card
    objectName: "detailSkeletonCard"

    property var rows: []
    property real pulse: 0.55
    // The caller keeps this false while the skeleton page is hidden; a hidden
    // delegate still reports visible == true, so visibility alone is not enough
    // to stop the pulse animation.
    property bool active: true

    implicitHeight: column.implicitHeight + 28
    height: implicitHeight
    radius: 8
    color: palette.base
    border.width: 1
    border.color: palette.mid

    SkeletonPulse {
        target: card
        targetProperty: "pulse"
        active: card.active && card.visible
    }

    ColumnLayout {
        id: column
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 14
        spacing: 10

        Repeater {
            model: card.rows

            delegate: RowLayout {
                id: row
                required property var modelData

                Layout.fillWidth: true
                spacing: 12

                Repeater {
                    model: row.modelData

                    delegate: Rectangle {
                        required property var modelData

                        Layout.fillWidth: true
                        Layout.preferredWidth: modelData[0]
                        implicitHeight: modelData[1]
                        radius: 4
                        color: Theme.skeletonColor(palette)
                        opacity: card.pulse
                    }
                }
            }
        }
    }
}
