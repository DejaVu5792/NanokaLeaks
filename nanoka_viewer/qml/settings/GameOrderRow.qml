import QtQuick
import QtQuick.Controls

// One row in the View Order list.
//
// The list itself owns the drag handling (see SettingsPanel.qml): it knows the
// row under the pointer for the whole drag, so the rows only paint their state
// and expose the two move buttons.
Item {
    id: row

    property string label: ""
    property bool dragging: false
    // A non-interactive copy shown under the pointer while this row is
    // dragged (see the ghost in SettingsPanel.qml).
    property bool ghost: false
    property bool canMoveUp: false
    property bool canMoveDown: false

    signal moveUp()
    signal moveDown()

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
        anchors.right: upButton.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: "\u28ff  " + row.label
        color: palette.text
        font.pixelSize: 12
        elide: Text.ElideRight
    }

    // Keyboard/pointer alternative to dragging: one step per click.
    MoveButton {
        id: upButton

        objectName: "orderRowUp"
        anchors.right: downButton.left
        anchors.rightMargin: 2
        anchors.verticalCenter: parent.verticalCenter
        glyph: "\u2191"
        tip: row.ghost ? "" : "Move up"
        enabled: row.canMoveUp
        onClicked: row.moveUp()
    }

    MoveButton {
        id: downButton

        objectName: "orderRowDown"
        anchors.right: parent.right
        anchors.rightMargin: 6
        anchors.verticalCenter: parent.verticalCenter
        glyph: "\u2193"
        tip: row.ghost ? "" : "Move down"
        enabled: row.canMoveDown
        onClicked: row.moveDown()
    }

    HoverHandler {
        id: hover
        enabled: !row.ghost
        cursorShape: Qt.OpenHandCursor
    }
}
