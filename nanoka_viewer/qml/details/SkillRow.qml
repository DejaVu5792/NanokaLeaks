pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// One collapsed-by-default skill disclosure inside the Skills card.
ColumnLayout {
    id: row

    property string title: ""
    property string description: ""
    property var multipliers: []
    property bool expanded: false

    spacing: 0

    AppButton {
        objectName: "skillToggle"
        Layout.fillWidth: true
        alignLeft: true
        text: (row.expanded ? "\u25be  " : "\u25b8  ") + row.title
        onClicked: row.expanded = !row.expanded
    }

    Rectangle {
        objectName: "skillBody"
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

            Text {
                objectName: "skillDescription"
                Layout.fillWidth: true
                visible: row.description.length > 0
                text: row.description
                textFormat: Text.RichText
                wrapMode: Text.WordWrap
                color: palette.text
                font.pixelSize: 12
                linkColor: palette.link
            }

            Label {
                visible: row.multipliers.length > 0
                text: "Multipliers"
                color: palette.text
                font.pixelSize: 12
                font.bold: true
            }

            Repeater {
                model: row.multipliers

                delegate: RowLayout {
                    id: multiplier
                    required property var modelData

                    Layout.fillWidth: true
                    spacing: 16

                    Label {
                        Layout.fillWidth: true
                        text: multiplier.modelData.label
                        color: palette.placeholderText
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }

                    Label {
                        Layout.alignment: Qt.AlignRight | Qt.AlignTop
                        text: multiplier.modelData.value
                        color: palette.text
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
            }
        }
    }
}
