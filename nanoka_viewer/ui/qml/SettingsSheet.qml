import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigami.formcard as FormCard

Item {
    id: root
    property var backend: null
    implicitWidth: Kirigami.Units.gridUnit * 30
    implicitHeight: Kirigami.Units.gridUnit * 25

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.largeSpacing

        Controls.Label {
            text: qsTr("Settings")
            font.bold: true
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.2
        }

        // Cache tab
        Controls.TabBar {
            id: tabBar
            Layout.fillWidth: true
            Controls.TabButton { text: qsTr("Cache") }
            Controls.TabButton { text: qsTr("View") }
        }

        StackLayout {
            currentIndex: tabBar.currentIndex
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Cache page
            Kirigami.ScrollablePage {
                FormCard.FormCard {
                    FormCard.FormCheckDelegate {
                        text: qsTr("Cache character details")
                        checked: backend ? backend.cacheDetails : true
                        onCheckedChanged: if (backend) backend.cacheDetails = checked
                    }
                    FormCard.FormCheckDelegate {
                        text: qsTr("Cache character builds")
                        checked: backend ? backend.cacheBuilds : true
                        onCheckedChanged: if (backend) backend.cacheBuilds = checked
                    }
                    FormCard.FormCheckDelegate {
                        text: qsTr("Cache character artwork")
                        checked: backend ? backend.cacheArtwork : true
                        onCheckedChanged: if (backend) backend.cacheArtwork = checked
                    }
                }

                Controls.Button {
                    text: qsTr("Clear cache")
                    onClicked: if (backend) backend.clearCache()
                }
            }

            // View / games page
            Kirigami.ScrollablePage {
                ColumnLayout {
                    width: parent.width
                    spacing: Kirigami.Units.smallSpacing

                    Controls.Label {
                        text: qsTr("Toggle Games")
                        font.bold: true
                    }

                    FormCard.FormCard {
                        Repeater {
                            model: backend ? backend.allGames : []
                            delegate: FormCard.FormCheckDelegate {
                                text: modelData.name
                                checked: modelData.enabled
                                onCheckedChanged: if (backend) backend.setGameEnabled(modelData.id, checked)
                            }
                        }
                    }
                }
            }
        }
    }
}
