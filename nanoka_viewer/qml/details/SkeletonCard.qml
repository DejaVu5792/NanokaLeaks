pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// One card-shaped loading placeholder: rows of pulsing bars.
//
// ``rows`` is a list of rows and each row is a list of ``[weight, height]``
// pairs, mirroring the width ratios the widget skeleton used.
Rectangle {
    id: card
    objectName: "detailSkeletonCard"

    property var rows: []
    property real pulse: 0.55

    implicitHeight: column.implicitHeight + 28
    height: implicitHeight
    radius: 8
    color: palette.base
    border.width: 1
    border.color: palette.mid

    // Same 50/50 Midlight/Mid blend the widget skeleton used: visible against
    // both Base and AlternateBase in light and dark themes.
    readonly property color skeletonColor: Qt.rgba(
        (palette.midlight.r + palette.mid.r) / 2,
        (palette.midlight.g + palette.mid.g) / 2,
        (palette.midlight.b + palette.mid.b) / 2,
        1)

    SequentialAnimation on pulse {
        running: true
        loops: Animation.Infinite
        NumberAnimation {
            from: 0.55
            to: 0.95
            duration: 900
            easing.type: Easing.InOutSine
        }
        NumberAnimation {
            from: 0.95
            to: 0.55
            duration: 900
            easing.type: Easing.InOutSine
        }
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
                        color: card.skeletonColor
                        opacity: card.pulse
                    }
                }
            }
        }
    }
}
