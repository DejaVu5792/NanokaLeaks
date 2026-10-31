import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Section title with a right-aligned reset button.
RowLayout {
    id: header

    property string title: ""
    property string tooltip: ""
    property string resetObjectName: ""

    signal resetClicked()

    spacing: 6

    Label {
        Layout.alignment: Qt.AlignVCenter
        leftPadding: 2
        text: header.title
        color: palette.text
        font.pixelSize: 13
        font.bold: true
    }

    Item {
        Layout.fillWidth: true
    }

    ToolButton {
        id: resetButton

        objectName: header.resetObjectName
        implicitWidth: 24
        implicitHeight: 24
        onClicked: header.resetClicked()

        ToolTip.text: header.tooltip
        ToolTip.visible: hovered && header.tooltip.length > 0

        contentItem: Text {
            text: "\u21ba"
            color: palette.text
            font.pixelSize: 14
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            radius: 4
            color: resetButton.down
                ? palette.midlight
                : resetButton.hovered ? palette.alternateBase : "transparent"
        }

        HoverHandler {
            cursorShape: Qt.PointingHandCursor
        }
    }
}
