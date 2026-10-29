import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: root
    property string gameName: ""
    property string gameId: ""
    property var cards: []
    property string liveVersion: ""
    property string latestVersion: ""
    property string statusText: ""
    height: sectionColumn.implicitHeight + Kirigami.Units.largeSpacing

    ColumnLayout {
        id: sectionColumn
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: Kirigami.Units.smallSpacing

        // Header
        Rectangle {
            Layout.fillWidth: true
            color: Kirigami.Theme.alternateBackgroundColor
            radius: Kirigami.Units.cornerRadius
            height: headerRow.implicitHeight + Kirigami.Units.smallSpacing * 2

            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing

                Controls.Label {
                    text: gameName
                    font.bold: true
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.1
                }

                // Live version badge
                Rectangle {
                    visible: liveVersion !== ""
                    color: "transparent"
                    border.color: Kirigami.Theme.positiveTextColor
                    border.width: 1
                    radius: 4
                    width: liveLabel.implicitWidth + 8
                    height: liveLabel.implicitHeight + 4
                    Controls.Label {
                        id: liveLabel
                        anchors.centerIn: parent
                        text: "Live v" + liveVersion
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.8
                        color: Kirigami.Theme.positiveTextColor
                        font.bold: true
                    }
                }

                // Beta version badge
                Rectangle {
                    visible: latestVersion !== ""
                    color: "transparent"
                    border.color: Kirigami.Theme.neutralTextColor
                    border.width: 1
                    radius: 4
                    width: betaLabel.implicitWidth + 8
                    height: betaLabel.implicitHeight + 4
                    Controls.Label {
                        id: betaLabel
                        anchors.centerIn: parent
                        text: "Beta v" + latestVersion.split("+")[0]
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.8
                        color: Kirigami.Theme.neutralTextColor
                        font.bold: true
                    }
                }

                Item { Layout.fillWidth: true }

                Controls.Label {
                    text: statusText
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.85
                }
            }
        }

        // Horizontal card row
        Controls.ScrollView {
            Layout.fillWidth: true
            height: 240
            Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AsNeeded
            Controls.ScrollBar.vertical.policy: Controls.ScrollBar.AlwaysOff
            clip: true

            Row {
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: root.cards
                    delegate: CharacterCard {
                        cardData: modelData
                    }
                }
            }
        }
    }
}
