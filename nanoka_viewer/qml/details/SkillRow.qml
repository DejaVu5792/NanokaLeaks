pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One collapsed-by-default skill disclosure inside the Skills card.
DisclosureRow {
    id: row

    property string description: ""
    property var multipliers: []

    toggleObjectName: "skillToggle"
    bodyObjectName: "skillBody"

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
