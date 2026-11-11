import QtQuick
import QtQuick.Controls

// Element/weapon mode switch inside a game's filter bar.  The two segments
// share the bar's background and are separated by a thin divider; only the
// active segment is highlighted, with a hover tint for the other one.
Item {
    id: toggle

    required property var filters

    readonly property bool elementMode: filters.mode === "element"
    readonly property bool weaponAvailable: filters.weaponAvailable

    implicitWidth: row.implicitWidth
    implicitHeight: 22

    Row {
        id: row
        anchors.centerIn: parent

        Item {
            id: elementSegment

            width: 22
            height: 22

            Rectangle {
                anchors.fill: parent
                radius: 4
                color: toggle.elementMode
                    ? palette.highlight
                    : (elementHover.hovered ? palette.alternateBase : "transparent")
            }

            Text {
                anchors.centerIn: parent
                text: "E"
                color: toggle.elementMode
                    ? palette.highlightedText : palette.text
                font.pixelSize: 11
                font.bold: toggle.elementMode
            }

            HoverHandler { id: elementHover }

            MouseArea {
                objectName: "filterModeelement"
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: toggle.filters.setMode("element")

                ToolTip.text: "Elements"
                ToolTip.visible: containsMouse
                ToolTip.delay: 600
            }
        }

        Item {
            width: 1
            height: 22

            Rectangle {
                anchors.centerIn: parent
                width: 1
                height: 14
                color: palette.mid
            }
        }

        Item {
            id: weaponSegment

            width: 22
            height: 22

            Rectangle {
                anchors.fill: parent
                radius: 4
                color: toggle.elementMode
                    ? (toggle.weaponAvailable && weaponHover.hovered
                        ? palette.alternateBase : "transparent")
                    : palette.highlight
            }

            Text {
                anchors.centerIn: parent
                text: "W"
                color: toggle.elementMode
                    ? (toggle.weaponAvailable
                        ? palette.text : palette.placeholderText)
                    : palette.highlightedText
                font.pixelSize: 11
                font.bold: !toggle.elementMode
            }

            HoverHandler { id: weaponHover }

            MouseArea {
                objectName: "filterModeweapon"
                anchors.fill: parent
                enabled: toggle.weaponAvailable
                cursorShape: Qt.PointingHandCursor
                onClicked: toggle.filters.setMode("weapon")

                ToolTip.text: toggle.weaponAvailable
                    ? "Weapons" : "This game has no weapon filters"
                ToolTip.visible: containsMouse
                ToolTip.delay: 600
            }
        }
    }
}
