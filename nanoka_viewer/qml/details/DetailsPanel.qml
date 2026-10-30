pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// Content of the character-details popup.
//
// ``details`` is the DetailsViewModel context property installed by
// nanoka_viewer/ui/details.py before this tree is parsed.  The widget overlay
// around it still owns the backdrop, the panel geometry, Escape handling and
// the modal input guard; this tree owns everything inside the panel.
Rectangle {
    id: panel
    objectName: "detailsPanelQml"

    radius: 10
    color: palette.base
    border.width: 1
    border.color: palette.mid

    // -- header -----------------------------------------------------------
    Item {
        id: headerArea
        objectName: "detailsHeader"
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 46
        clip: true

        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: headerArea.height + panel.radius
            radius: panel.radius
            color: palette.alternateBase
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 12
            spacing: 10

            Item { Layout.fillWidth: true }

            AppButton {
                objectName: "detailsCloseButton"
                text: "Close"
                small: true
                onClicked: details.requestClose()
            }
        }
    }

    // -- body -------------------------------------------------------------
    Row {
        anchors.top: headerArea.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        ArtPanel {
            id: artPanel
            width: Math.round(panel.width * 0.25)
            height: parent.height
        }

        Flickable {
            id: scroll
            objectName: "detailsScroll"
            width: parent.width - artPanel.width
            height: parent.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            contentWidth: width
            contentHeight: contentColumn.implicitHeight + 32

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle {
                    implicitWidth: 6
                    radius: 3
                    color: palette.mid
                }
                background: Rectangle { color: "transparent" }
            }

            Column {
                id: contentColumn
                objectName: "detailsContent"
                x: 16
                y: 16
                width: scroll.width - 32
                spacing: 12

                // -- loading ----------------------------------------------
                Column {
                    objectName: "detailsLoading"
                    width: parent.width
                    spacing: 12
                    visible: details.state === "loading"
                    Accessible.name: "Loading character details"

                    Label {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: "Loading fresh details from nanoka.cc..."
                        color: palette.placeholderText
                        font.pixelSize: 12
                    }

                    SkeletonCard {
                        width: parent.width
                        rows: [
                            [[26, 16]],
                            [[40, 9]],
                            [[34, 12], [30, 12]],
                            [[46, 10], [34, 10]],
                            [[42, 10], [30, 10]],
                            [[38, 10], [26, 10]]
                        ]
                    }

                    SkeletonCard {
                        width: parent.width
                        rows: [
                            [[22, 16]],
                            [[94, 9], [86, 9], [66, 9]],
                            [[92, 9], [78, 9], [58, 9]]
                        ]
                    }

                    SkeletonCard {
                        width: parent.width
                        rows: [
                            [[20, 16]],
                            [[16, 9], [12, 9]],
                            [[16, 9], [12, 9]],
                            [[16, 9], [12, 9]],
                            [[16, 9], [12, 9]]
                        ]
                    }

                    SkeletonCard {
                        width: parent.width
                        rows: [
                            [[18, 16]],
                            [[98, 30]],
                            [[98, 30]],
                            [[98, 30]]
                        ]
                    }
                }

                // -- error ------------------------------------------------
                DetailCard {
                    objectName: "detailsError"
                    visible: details.state === "error"
                    title: "Could not load details"

                    Label {
                        Layout.fillWidth: true
                        text: details.errorMessage
                        color: palette.placeholderText
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }

                    AppButton {
                        objectName: "detailsRetryButton"
                        Layout.alignment: Qt.AlignLeft
                        text: "Retry"
                        onClicked: details.requestRetry()
                    }
                }

                // -- recommended build ------------------------------------
                SkeletonCard {
                    objectName: "detailsBuildSkeleton"
                    width: parent.width
                    visible: details.buildState === "skeleton"
                    rows: [
                        [[26, 16]],
                        [[40, 9]],
                        [[34, 12], [30, 12]],
                        [[46, 10], [34, 10]],
                        [[42, 10], [30, 10]],
                        [[38, 10], [26, 10]]
                    ]
                }

                DetailCard {
                    objectName: "detailsBuildCard"
                    visible: details.buildState === "ready"
                    title: "Recommended Build"

                    Label {
                        Layout.fillWidth: true
                        text: "Suggested by nanoka.cc"
                        color: palette.placeholderText
                        font.pixelSize: 11
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Repeater {
                            model: details.buildRows

                            delegate: RowLayout {
                                id: buildRow
                                required property var modelData

                                Layout.fillWidth: true
                                spacing: 18

                                Repeater {
                                    model: buildRow.modelData

                                    delegate: ColumnLayout {
                                        id: buildSection
                                        required property var modelData

                                        Layout.fillWidth: true
                                        Layout.alignment: Qt.AlignTop
                                        spacing: 4

                                        Label {
                                            Layout.fillWidth: true
                                            text: buildSection.modelData.title
                                            color: palette.text
                                            font.pixelSize: 12
                                            font.bold: true
                                            wrapMode: Text.WordWrap
                                        }

                                        Repeater {
                                            model: buildSection.modelData.items

                                            delegate: Label {
                                                required property var modelData

                                                Layout.fillWidth: true
                                                text: "\u2022 " + modelData
                                                color: palette.text
                                                font.pixelSize: 11
                                                wrapMode: Text.WordWrap
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // -- overview ---------------------------------------------
                DetailCard {
                    objectName: "detailsOverviewCard"
                    visible: details.state === "ready" && details.hasOverview
                    title: "Overview"

                    Text {
                        objectName: "detailsSubtitle"
                        Layout.fillWidth: true
                        visible: details.subtitle.length > 0
                        text: details.subtitle
                        textFormat: Text.RichText
                        wrapMode: Text.WordWrap
                        color: palette.placeholderText
                        font.pixelSize: 11
                    }

                    Text {
                        objectName: "detailsOverview"
                        Layout.fillWidth: true
                        visible: details.overview.length > 0
                        text: details.overview
                        textFormat: Text.RichText
                        wrapMode: Text.WordWrap
                        color: palette.text
                        font.pixelSize: 12
                        linkColor: palette.link
                    }
                }

                // -- stats ------------------------------------------------
                DetailCard {
                    objectName: "detailsStatsCard"
                    visible: details.state === "ready"
                             && details.statRows.length > 0
                    title: "Stats \u00b7 " + details.levelLabel

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Repeater {
                            model: details.statRows

                            delegate: RowLayout {
                                id: statRow
                                required property var modelData

                                Layout.fillWidth: true
                                spacing: 18

                                Repeater {
                                    model: statRow.modelData

                                    delegate: RowLayout {
                                        id: stat
                                        required property var modelData

                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1      // equal halves in every row
                                        Layout.alignment: Qt.AlignTop
                                        spacing: 8

                                        Label {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            Layout.alignment: Qt.AlignLeft | Qt.AlignTop
                                            text: stat.modelData.label
                                            color: palette.placeholderText
                                            font.pixelSize: 11
                                            wrapMode: Text.WordWrap
                                        }

                                        Label {
                                            Layout.alignment: Qt.AlignRight | Qt.AlignTop
                                            horizontalAlignment: Text.AlignRight
                                            text: stat.modelData.value
                                            color: palette.text
                                            font.pixelSize: 11
                                            font.bold: true
                                        }
                                    }
                                }

                                // keeps a lone stat at half width instead of stretching across
                                Item {
                                    visible: statRow.modelData.length < 2
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                }
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        text: "No constellation, sequence, mindscape, or resonance boosts."
                        color: palette.placeholderText
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                }

                // -- skills -----------------------------------------------
                DetailCard {
                    objectName: "detailsSkillsCard"
                    visible: details.state === "ready"
                             && details.skills.length > 0
                    title: "Skills"

                    Label {
                        Layout.fillWidth: true
                        text: "Descriptions and multipliers are collapsed. "
                              + "Click a skill to expand."
                        color: palette.placeholderText
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }

                    Repeater {
                        model: details.skills

                        delegate: SkillRow {
                            required property var modelData

                            Layout.fillWidth: true
                            title: modelData.title
                            description: modelData.description
                            multipliers: modelData.multipliers
                        }
                    }
                }

                // -- passives, traces & more ------------------------------
                DetailCard {
                    objectName: "detailsExtrasCard"
                    visible: details.state === "ready"
                             && details.extras.length > 0
                    title: "Passives, Traces & More"

                    Repeater {
                        model: details.extras

                        delegate: ExtraRow {
                            required property var modelData

                            Layout.fillWidth: true
                            title: modelData.title
                            entries: modelData.entries
                        }
                    }
                }
            }
        }
    }

    Connections {
        target: details

        function onStateChanged() {
            scroll.contentY = 0
        }
    }
}
