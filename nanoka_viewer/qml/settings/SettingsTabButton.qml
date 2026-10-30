import QtQuick
import QtQuick.Controls

// One tab in the settings TabBar, drawn from the palette.
TabButton {
    id: control

    implicitHeight: 32
    leftPadding: 14
    rightPadding: 14
    font.pixelSize: 12
    font.bold: true

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.checked || control.hovered
            ? palette.text
            : palette.placeholderText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Item {
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 2
            color: control.checked ? palette.highlight : "transparent"
        }
    }

    HoverHandler {
        cursorShape: Qt.PointingHandCursor
    }
}
