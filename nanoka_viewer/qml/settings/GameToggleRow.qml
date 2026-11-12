import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// One game in the Toggle View card: clicking anywhere on the row toggles it.
Item {
    id: row

    property string gameName: ""
    property bool checked: true
    property string countText: ""
    property string countTooltip: ""

    signal toggled(bool checked)

    implicitHeight: 36

    Rectangle {
        anchors.fill: parent
        radius: 4
        color: hover.hovered ? palette.alternateBase : "transparent"
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 2
        anchors.rightMargin: 8
        spacing: 8

        AppSwitch {
            objectName: "gameToggleSwitch"
            Layout.alignment: Qt.AlignVCenter
            checked: row.checked
            interactive: false
        }

        Label {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            text: row.gameName
            color: palette.text
            font.pixelSize: 12
            elide: Text.ElideRight
        }

        Label {
            id: countLabel

            objectName: "settingsCount"
            Layout.alignment: Qt.AlignVCenter
            text: row.countText
            color: palette.placeholderText
            font.pixelSize: 11
            horizontalAlignment: Text.AlignRight

            HoverHandler {
                id: countHover
            }

            ToolTip.text: row.countTooltip
            ToolTip.visible: countHover.hovered && row.countTooltip.length > 0
            ToolTip.delay: 600
        }
    }

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
        onTapped: row.toggled(!row.checked)
    }
}
