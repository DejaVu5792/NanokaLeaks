pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

import ".."

// Collapsed-by-default row: a full-width toggle above a framed body.
//
// Skills and overview sections share this chrome; they only differ in the
// body, which lands in the default ``content`` alias.  The toggle/body object
// names stay configurable because the tests (and QML lint) look them up.
ColumnLayout {
    id: row

    property string title: ""
    property bool expanded: false
    property string toggleObjectName: ""
    property string bodyObjectName: ""

    default property alias content: bodyColumn.data

    spacing: 0

    AppButton {
        objectName: row.toggleObjectName
        Layout.fillWidth: true
        alignLeft: true
        text: (row.expanded ? "\u25be  " : "\u25b8  ") + row.title
        onClicked: row.expanded = !row.expanded
    }

    Rectangle {
        objectName: row.bodyObjectName
        Layout.fillWidth: true
        Layout.topMargin: 4
        visible: row.expanded
        implicitHeight: bodyColumn.implicitHeight + 20
        radius: 6
        color: palette.alternateBase
        border.width: 1
        border.color: palette.mid

        ColumnLayout {
            id: bodyColumn
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 10
            spacing: 8
        }
    }
}
