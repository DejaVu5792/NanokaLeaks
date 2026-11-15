pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// One collapsed-by-default skill disclosure inside the Skills card.
DisclosureRow {
    id: row

    property string description: ""
    property var multipliers: []

    toggleObjectName: "skillToggle"
    bodyObjectName: "skillBody"

    SelectableText {
        objectName: "skillDescription"
        Layout.fillWidth: true
        visible: row.description.length > 0
        text: row.description
        textFormat: TextEdit.RichText
        color: palette.text
        font.pixelSize: 12
    }

    SelectableText {
        visible: row.multipliers.length > 0
        text: "Multipliers"
        color: palette.text
        font.pixelSize: 12
        font.bold: true
    }

    Repeater {
        model: row.multipliers

        delegate: Rectangle {
            id: multiplierRow
            required property int index
            required property var modelData

            objectName: "skillMultiplierRow"
            Layout.fillWidth: true
            implicitHeight: multiplierLayout.implicitHeight + 6
            radius: 4
            // Zebra banding so wide tables stay readable: every other row is
            // lifted out of the framed body's background.
            color: multiplierRow.index % 2 === 1 ? palette.base : "transparent"

            RowLayout {
                id: multiplierLayout
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                anchors.topMargin: 3
                anchors.bottomMargin: 3
                spacing: 16

                SelectableText {
                    Layout.fillWidth: true
                    text: multiplierRow.modelData.label
                    color: palette.placeholderText
                    font.pixelSize: 11
                }

                SelectableText {
                    Layout.alignment: Qt.AlignRight | Qt.AlignTop
                    text: multiplierRow.modelData.value
                    color: palette.text
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }
    }
}
