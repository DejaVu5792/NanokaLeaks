import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard 1.0 as FormCard

Item {
    id: root
    property var backend: null
    implicitWidth: Kirigami.Units.gridUnit * 34
    implicitHeight: Kirigami.Units.gridUnit * 30

    onVisibleChanged: if (visible && backend) backend.refreshCacheSizes()

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Controls.TabBar {
            id: tabBar
            Layout.fillWidth: true
            Controls.TabButton { text: qsTr("Cache") }
            Controls.TabButton { text: qsTr("Games") }
        }

        Kirigami.Separator { Layout.fillWidth: true }

        StackLayout {
            currentIndex: tabBar.currentIndex
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Cache Tab
            Kirigami.ScrollablePage {
                ColumnLayout {
                    width: parent.width
                    spacing: Kirigami.Units.largeSpacing

                    Kirigami.Heading {
                        text: qsTr("Caching")
                        level: 3
                        Layout.fillWidth: true
                    }

                    FormCard.FormCard {
                        Layout.fillWidth: true

                        FormCard.FormCheckDelegate {
                            text: qsTr("Cache character details")
                            description: qsTr("Caches the detail text: overview, stats, skills, and extras.")
                            checked: backend ? backend.cacheDetails : true
                            onCheckedChanged: if (backend) backend.cacheDetails = checked
                        }
                        Kirigami.Separator { Layout.fillWidth: true }
                        FormCard.FormCheckDelegate {
                            text: qsTr("Cache character builds")
                            description: qsTr("Refreshes build tables each version; unchanged tables are revalidated with ETags.")
                            checked: backend ? backend.cacheBuilds : true
                            onCheckedChanged: if (backend) backend.cacheBuilds = checked
                        }
                        Kirigami.Separator { Layout.fillWidth: true }
                        FormCard.FormCheckDelegate {
                            text: qsTr("Cache character artwork")
                            description: qsTr("Artwork is a large download and uses much more disk space than text caches.")
                            checked: backend ? backend.cacheArtwork : true
                            onCheckedChanged: if (backend) backend.cacheArtwork = checked
                        }
                    }

                    Kirigami.Heading {
                        text: qsTr("Preload")
                        level: 3
                        Layout.fillWidth: true
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing

                        Controls.Button {
                            text: qsTr("Preload Details")
                            icon.name: "download"
                            enabled: backend && !backend.preloadRunning && backend.cacheDetails
                            onClicked: if (backend) backend.startPreload("details")
                        }
                        Controls.Button {
                            text: qsTr("Preload Builds")
                            icon.name: "download"
                            enabled: backend && !backend.preloadRunning && backend.cacheBuilds
                            onClicked: if (backend) backend.startPreload("builds")
                        }
                        Controls.Button {
                            text: qsTr("Preload Artwork")
                            icon.name: "download"
                            enabled: backend && !backend.preloadRunning && backend.cacheArtwork
                            onClicked: if (backend) backend.startPreload("artwork")
                        }
                        Controls.Button {
                            text: qsTr("Stop")
                            icon.name: "process-stop"
                            visible: backend && backend.preloadRunning
                            onClicked: if (backend) backend.stopPreload()
                        }
                    }

                    Controls.Label {
                        visible: backend && backend.preloadStatus !== ""
                        text: backend ? backend.preloadStatus : ""
                        color: Kirigami.Theme.disabledTextColor
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }

                    Kirigami.Heading {
                        text: qsTr("Cache Sizes")
                        level: 3
                        Layout.fillWidth: true
                    }

                    FormCard.FormCard {
                        Layout.fillWidth: true

                        FormCard.FormTextDelegate {
                            text: qsTr("Details cache")
                            description: backend && backend.cacheSizeInfo["details"]
                            ? backend.cacheSizeInfo["details"] : "—"
                        }
                        Kirigami.Separator { Layout.fillWidth: true }
                        FormCard.FormTextDelegate {
                            text: qsTr("Builds cache")
                            description: {
                                if (!backend) return "—"
                                    var sz = backend.cacheSizeInfo["builds"] || "—"
                                    var last = backend.cacheSizeInfo["buildsLastCached"] || ""
                                    return last ? sz + " · Last cached: " + last : sz
                            }
                        }
                        Kirigami.Separator { Layout.fillWidth: true }
                        FormCard.FormTextDelegate {
                            text: qsTr("Artwork cache")
                            description: backend && backend.cacheSizeInfo["artwork"]
                            ? backend.cacheSizeInfo["artwork"] : "—"
                        }
                    }

                    Controls.Button {
                        text: qsTr("Clear cache")
                        icon.name: "edit-clear-all"
                        enabled: backend && !backend.preloadRunning
                        Controls.ToolTip.text: qsTr("Stop the running preload before clearing it.")
                        Controls.ToolTip.visible: hovered && backend && backend.preloadRunning
                        onClicked: if (backend) backend.clearCache()
                    }

                    Item { implicitHeight: Kirigami.Units.largeSpacing }
                }
            }

            // Games Tab
            Kirigami.ScrollablePage {
                ColumnLayout {
                    width: parent.width
                    spacing: Kirigami.Units.largeSpacing

                    Kirigami.Heading {
                        text: qsTr("Toggle Games")
                        level: 3
                        Layout.fillWidth: true
                    }

                    Controls.Label {
                        text: qsTr("Unchecking a game hides it and stops loading its characters, details, builds, and artwork.")
                        color: Kirigami.Theme.disabledTextColor
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }

                    FormCard.FormCard {
                        Layout.fillWidth: true

                        Repeater {
                            model: backend ? backend.allGames : []
                            delegate: ColumnLayout {
                                spacing: 0
                                Layout.fillWidth: true

                                FormCard.FormCheckDelegate {
                                    text: modelData.name
                                    checked: modelData.enabled
                                    onCheckedChanged: {
                                        if (backend && modelData.enabled !== checked)
                                            backend.setGameEnabled(modelData.id, checked)
                                    }
                                }
                                Kirigami.Separator {
                                    Layout.fillWidth: true
                                    visible: index < (backend ? backend.allGames.length - 1 : 0)
                                }
                            }
                        }
                    }

                    Item { implicitHeight: Kirigami.Units.largeSpacing }
                }
            }
        }
    }
}
