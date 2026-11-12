import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// One cache option: switch + Preload button, with its size and (for the
// builds row) the last-cached time underneath.
//
// Like the game toggles, clicking anywhere on the row toggles the setting;
// the Preload button keeps owning its own clicks.
Item {
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

    implicitHeight: content.implicitHeight

    Rectangle {
        anchors.fill: content
        radius: 4
        color: hover.hovered && row.checkEnabled
            ? palette.alternateBase : "transparent"
    }

    MouseArea {
        anchors.fill: content
        enabled: row.checkEnabled
        cursorShape: row.checkEnabled
            ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: row.toggled(!row.checked)
    }

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: 2

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            Layout.bottomMargin: 2
            spacing: 8

            AppSwitch {
                id: box

                objectName: "cacheCheck"
                Layout.alignment: Qt.AlignVCenter
                checked: row.checked
                enabled: row.checkEnabled
                interactive: false
                tooltip: row.tooltip
            }

            Label {
                id: titleLabel

                objectName: "cacheRowTitle"
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                text: row.title
                color: row.checkEnabled ? palette.text : palette.placeholderText
                font.pixelSize: 12
                elide: Text.ElideRight

                HoverHandler { id: titleHover }

                ToolTip.text: row.tooltip
                ToolTip.visible: titleHover.hovered && row.tooltip.length > 0
                ToolTip.delay: 600
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
                ToolTip.delay: 600
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 48
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

    HoverHandler {
        id: hover
        cursorShape: row.checkEnabled
            ? Qt.PointingHandCursor : Qt.ArrowCursor
    }
}
