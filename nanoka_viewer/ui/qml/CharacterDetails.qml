import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: root
    property var backend: null
    implicitWidth: Kirigami.Units.gridUnit * 40
    implicitHeight: Kirigami.Units.gridUnit * 35

    property string currentGame: ""
    property string currentCharId: ""

    function load(gameId, charId, charData) {
        currentGame = gameId
        currentCharId = charId
        if (backend) backend.loadDetails(gameId, charId)
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Art column
        Rectangle {
            Layout.preferredWidth: 240
            Layout.fillHeight: true
            color: Kirigami.Theme.alternateBackgroundColor

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 0

                Image {
                    id: artImage
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: backend ? backend.detailArtUrl : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    verticalAlignment: Image.AlignTop
                }

                Controls.Label {
                    visible: artImage.status !== Image.Ready || artImage.source === ""
                    Layout.alignment: Qt.AlignCenter
                    text: backend && backend.detailArtUrl === "" ? qsTr("Art unavailable") : qsTr("Loading...")
                    color: Kirigami.Theme.disabledTextColor
                }
            }
        }

        // Details scroll area
        Kirigami.ScrollablePage {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                width: parent.width
                spacing: Kirigami.Units.largeSpacing

                Controls.BusyIndicator {
                    visible: backend && backend.detailLoading
                    Layout.alignment: Qt.AlignCenter
                }

                Controls.Label {
                    visible: backend && !backend.detailLoading && backend.detailError !== ""
                    text: backend ? backend.detailError : ""
                    color: Kirigami.Theme.negativeTextColor
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }

                // Overview
                Kirigami.FormCard.FormCard {
                    visible: backend && backend.detailOverview !== ""
                    Layout.fillWidth: true
                    Kirigami.FormCard.FormTextDelegate {
                        text: backend ? backend.detailOverview : ""
                        description: qsTr("Overview")
                    }
                }

                // Stats
                Repeater {
                    model: backend ? backend.detailStats : []
                    delegate: Kirigami.FormCard.FormCard {
                        Layout.fillWidth: true
                        Kirigami.FormCard.FormTextDelegate {
                            text: modelData.name
                            description: modelData.value
                        }
                    }
                }
            }
        }
    }
}
