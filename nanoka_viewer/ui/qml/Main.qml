import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: qsTr("Nanoka Viewer")
    minimumWidth: Kirigami.Units.gridUnit * 50
    minimumHeight: Kirigami.Units.gridUnit * 37

    // Backend is exposed as context property "backend" from Python

    pageStack.initialPage: mainPage

    Component {
        id: mainPage
        Kirigami.Page {
            title: qsTr("Nanoka Viewer")
            // header area with status labels and buttons
            actions: [
                Kirigami.Action {
                    icon.name: "view-refresh"
                    text: qsTr("Reload")
                    enabled: !backend.loadInProgress
                    onTriggered: backend.loadData()
                },
                Kirigami.Action {
                    icon.name: "settings-configure"
                    text: qsTr("Settings")
                    onTriggered: settingsDialog.open()
                }
            ]

            // Status bar in the header
            Kirigami.InlineMessage {
                id: cacheMsg
                visible: backend.cacheLabel !== ""
                text: backend.cacheLabel
                type: Kirigami.MessageType.Information
            }

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Cache/status labels
                Controls.Label {
                    Layout.fillWidth: true
                    text: backend.statusLabel
                    color: Kirigami.Theme.disabledTextColor
                    horizontalAlignment: Text.AlignRight
                    visible: text !== ""
                }

                // Scrollable list of game sections
                Kirigami.ScrollablePage {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ListView {
                        id: gameList
                        model: backend.gameSections
                        spacing: Kirigami.Units.smallSpacing
                        delegate: GameSection {
                            width: gameList.width
                            gameName: modelData.gameName
                            gameId: modelData.gameId
                            cards: modelData.cards
                            liveVersion: modelData.liveVersion
                            latestVersion: modelData.latestVersion
                            statusText: modelData.statusText
                        }
                    }
                }
            }
        }
    }

    // Settings sheet
    Kirigami.OverlaySheet {
        id: settingsDialog
        SettingsSheet {
            backend: backend
        }
    }

    // Details sheet
    Kirigami.OverlaySheet {
        id: detailsSheet
        CharacterDetails {
            id: detailsContent
            backend: backend
        }
    }

    Connections {
        target: backend
        function onOpenDetails(gameId, charId, charData) {
            detailsContent.load(gameId, charId, charData)
            detailsSheet.open()
        }
        function onCloseDetails() {
            detailsSheet.close()
        }
    }
}
