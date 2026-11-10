import QtQuick
import QtQuick.Controls

// Element/weapon mode switch of a game's filter bar.  Two segments; the
// active one is highlighted, and weapons are dimmed for games without a
// second category (NTE currently ships elements only).
Item {
    id: toggle

    required property var filters

    readonly property bool elementMode: filters.mode === "element"
    readonly property bool weaponAvailable: filters.weaponAvailable

    implicitWidth: row.implicitWidth + 4
    implicitHeight: 22

    Rectangle {
        anchors.fill: parent
        radius: 4
        color: palette.button
        border.width: 1
        border.color: palette.mid
    }

    Row {
        id: row
        anchors.centerIn: parent

        Repeater {
            model: [
                { mode: "element", label: "E", tooltip: "Elements" },
                { mode: "weapon", label: "W", tooltip: "Weapons" },
            ]

            delegate: Item {
                id: segment

                required property var modelData

                readonly property bool active: toggle.elementMode
                    ? segment.modelData.mode === "element"
                    : segment.modelData.mode === "weapon"
                readonly property bool available: segment.modelData.mode
                    === "element" || toggle.weaponAvailable

                width: 20
                height: 20

                Rectangle {
                    anchors.fill: parent
                    radius: 3
                    color: segment.active ? palette.highlight : "transparent"
                }

                Text {
                    anchors.centerIn: parent
                    text: segment.modelData.label
                    color: segment.active
                        ? palette.highlightedText
                        : (segment.available
                            ? palette.text : palette.placeholderText)
                    font.pixelSize: 11
                    font.bold: segment.active
                }

                MouseArea {
                    objectName: "filterMode" + segment.modelData.mode
                    anchors.fill: parent
                    enabled: segment.available
                    onClicked: toggle.filters.setMode(segment.modelData.mode)

                    ToolTip.text: segment.modelData.tooltip
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 600
                }
            }
        }
    }
}
