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

        delegate: RowLayout {
            id: multiplier
            required property var modelData

            Layout.fillWidth: true
            spacing: 16

            SelectableText {
                Layout.fillWidth: true
                text: multiplier.modelData.label
                color: palette.placeholderText
                font.pixelSize: 11
            }

            SelectableText {
                Layout.alignment: Qt.AlignRight | Qt.AlignTop
                text: multiplier.modelData.value
                color: palette.text
                font.pixelSize: 11
                font.bold: true
            }
        }
    }
}
