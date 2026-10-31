import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// One cache option: checkbox + Preload button, with its size and (for the
// builds row) the last-cached time underneath.
ColumnLayout {
    id: row

    property string title: ""
    property string tooltip: ""
    property bool checked: true
    property bool checkEnabled: true
    property string buttonText: "Preload"
    property bool buttonEnabled: true
    property string buttonTooltip: ""
    property string buttonObjectName: ""
    property bool showButton: true
    property string sizeText: ""
    property string lastCachedText: ""

    signal toggled(bool checked)
    signal preloadClicked()

    spacing: 2

    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 4
        Layout.bottomMargin: 2
        spacing: 8

        CheckBox {
            id: box

            objectName: "cacheCheck"
            Layout.fillWidth: true
            text: row.title
            checked: row.checked
            enabled: row.checkEnabled
            font.pixelSize: 12
            onToggled: row.toggled(checked)

            ToolTip.text: row.tooltip
            ToolTip.visible: hovered && row.tooltip.length > 0
        }

        AppButton {
            objectName: row.buttonObjectName

            visible: row.showButton
            small: true
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.preferredWidth: 84
            text: row.buttonText
            enabled: row.buttonEnabled
            onClicked: row.preloadClicked()

            ToolTip.text: row.buttonTooltip
            ToolTip.visible: hovered && row.buttonTooltip.length > 0
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 26
        Layout.bottomMargin: 4
        spacing: 6

        Label {
            objectName: "cacheLastCached"
            visible: row.lastCachedText.length > 0
            text: row.lastCachedText
            color: palette.placeholderText
            font.pixelSize: 11
        }

        Item {
            Layout.fillWidth: true
        }

        Label {
            objectName: "cacheSize"
            text: row.sizeText
            color: palette.placeholderText
            font.pixelSize: 11
        }
    }
}
