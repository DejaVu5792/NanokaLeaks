pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// One collapsed-by-default overview section (passives, traces, mindscapes).
DisclosureRow {
    id: row

    property var entries: []

    toggleObjectName: "extraToggle"
    bodyObjectName: "extraBody"

    Repeater {
        model: row.entries

        delegate: ColumnLayout {
            id: entry
            required property var modelData

            Layout.fillWidth: true
            spacing: 2

            SelectableText {
                Layout.fillWidth: true
                text: entry.modelData.name
                color: palette.text
                font.pixelSize: 12
                font.bold: true
            }

            SelectableText {
                Layout.fillWidth: true
                visible: entry.modelData.text.length > 0
                text: entry.modelData.text
                textFormat: TextEdit.RichText
                color: palette.text
                font.pixelSize: 12
            }
        }
    }
}
