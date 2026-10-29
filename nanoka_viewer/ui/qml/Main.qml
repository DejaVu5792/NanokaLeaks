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
        Kirigami.ScrollablePage {
            title: qsTr("Nanoka Viewer")
            actions: [
                Kirigami.Action {
                    icon.name: "view-refresh"
                    text: qsTr("Reload")
                    enabled: !backend.loadInProgress
                    onTriggered: backend.loadData()
                    shortcut: "F5"
                },
                Kirigami.Action {
                    icon.name: "settings-configure"
                    text: qsTr("Settings")
                    onTriggered: settingsDialog.open()
                }
            ]

            // Inline cache/preload progress message
            header: Kirigami.InlineMessage {
                id: cacheMsg
                visible: backend.cacheLabel !== ""
                text: backend.cacheLabel
                type: Kirigami.MessageType.Information
                Layout.fillWidth: true
            }

            ColumnLayout {
                width: parent.width
                spacing: Kirigami.Units.smallSpacing

                // Status label (right-aligned, e.g. "Loaded at 12:34")
                Controls.Label {
                    Layout.fillWidth: true
                    text: backend.statusLabel
                    color: Kirigami.Theme.disabledTextColor
                    horizontalAlignment: Text.AlignRight
                    visible: text !== ""
                }

                // Game sections list
                Repeater {
                    model: backend.gameSections
                    delegate: GameSection {
                        Layout.fillWidth: true
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
