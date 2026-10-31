import QtQuick
import QtQuick.Controls

// One row in the View Order list.
//
// The list itself owns the pointer handling (see SettingsPanel.qml): it knows
// the row under the pointer for the whole drag, so the rows only paint their
// state.
Item {
    id: row

    property string label: ""
    property bool dragging: false

    implicitHeight: 34

    Rectangle {
        x: 2
        y: 2
        width: row.width - 4
        height: row.height - 4
        radius: 4
        color: row.dragging
            ? palette.midlight
            : hover.hovered ? palette.alternateBase : "transparent"
    }

    Text {
        objectName: "orderRowLabel"
        anchors.left: parent.left
        anchors.leftMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        text: "\u28ff  " + row.label
        color: palette.text
        font.pixelSize: 12
    }

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
    }
}
