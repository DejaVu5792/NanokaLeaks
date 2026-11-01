pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// One collapsed-by-default overview section (passives, traces, mindscapes).
ColumnLayout {
    id: row

    property string title: ""
    property var entries: []
    property bool expanded: false

    spacing: 0

    AppButton {
        objectName: "extraToggle"
        Layout.fillWidth: true
        alignLeft: true
        text: (row.expanded ? "\u25be  " : "\u25b8  ") + row.title
        onClicked: row.expanded = !row.expanded
    }

    Rectangle {
        objectName: "extraBody"
        Layout.fillWidth: true
        Layout.topMargin: 4
        visible: row.expanded
        implicitHeight: bodyLayout.implicitHeight + 20
        radius: 6
        color: palette.alternateBase
        border.width: 1
        border.color: palette.mid

        ColumnLayout {
            id: bodyLayout
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 10
            spacing: 8

            Repeater {
                model: row.entries

                delegate: ColumnLayout {
                    id: entry
                    required property var modelData

                    Layout.fillWidth: true
                    spacing: 2

                    Label {
                        Layout.fillWidth: true
                        text: entry.modelData.name
                        color: palette.text
                        font.pixelSize: 12
                        font.bold: true
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: entry.modelData.text.length > 0
                        text: entry.modelData.text
                        textFormat: Text.RichText
                        wrapMode: Text.WordWrap
                        color: palette.text
                        font.pixelSize: 12
                        linkColor: palette.link
                    }
                }
            }
        }
    }
}
