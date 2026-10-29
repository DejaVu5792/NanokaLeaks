import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: root
    property var backend: null
    implicitWidth: Kirigami.Units.gridUnit * 50
    implicitHeight: Kirigami.Units.gridUnit * 38

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

        // ── Art column ────────────────────────────────────────────────────
        Rectangle {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 15
            Layout.fillHeight: true
            color: Kirigami.Theme.alternateBackgroundColor

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Character artwork
                Image {
                    id: artImage
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: backend ? backend.detailArtUrl : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    verticalAlignment: Image.AlignTop
                    clip: true
                }

                // Art placeholder / loading text
                Controls.Label {
                    visible: artImage.status !== Image.Ready || !artImage.source
                    Layout.alignment: Qt.AlignCenter
                    text: backend && backend.detailArtUrl === ""
                          ? (backend.detailLoading ? qsTr("Loading…") : qsTr("Art unavailable"))
                          : qsTr("Loading…")
                    color: Kirigami.Theme.disabledTextColor
                    padding: Kirigami.Units.largeSpacing
                }

                // Open source URL button (bottom of art panel)
                Controls.Button {
                    visible: backend && backend.detailSourceUrl !== ""
                    Layout.fillWidth: true
                    text: qsTr("Open on nanoka.cc")
                    icon.name: "document-open-remote"
                    flat: true
                    onClicked: if (backend) Qt.openUrlExternally(backend.detailSourceUrl)
                }
            }
        }

        // ── Details scroll area ───────────────────────────────────────────
        Kirigami.ScrollablePage {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                width: parent.width
                spacing: Kirigami.Units.largeSpacing

                // Loading indicator
                Controls.BusyIndicator {
                    visible: backend && backend.detailLoading
                    Layout.alignment: Qt.AlignCenter
                    implicitWidth: Kirigami.Units.gridUnit * 3
                    implicitHeight: Kirigami.Units.gridUnit * 3
                }

                // Error card
                Kirigami.InlineMessage {
                    visible: backend && !backend.detailLoading && backend.detailError !== ""
                    text: backend ? backend.detailError : ""
                    type: Kirigami.MessageType.Error
                    Layout.fillWidth: true
                    actions: [
                        Kirigami.Action {
                            text: qsTr("Retry")
                            icon.name: "view-refresh"
                            onTriggered: if (backend) backend.retryDetails()
                        }
                    ]
                }

                // ── Character header card ─────────────────────────────────
                Kirigami.Card {
                    visible: backend && !backend.detailLoading && backend.detailName !== ""
                    Layout.fillWidth: true

                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing

                        Controls.Label {
                            text: backend ? backend.detailName : ""
                            font.bold: true
                            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.3
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }

                        Controls.Label {
                            visible: backend && backend.detailSubtitle !== ""
                            text: backend ? backend.detailSubtitle : ""
                            color: Kirigami.Theme.disabledTextColor
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }

                        Controls.Label {
                            visible: backend && backend.detailLevelLabel !== ""
                            text: backend ? backend.detailLevelLabel : ""
                            color: Kirigami.Theme.disabledTextColor
                            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.9
                        }

                        // Badges row
                        Flow {
                            visible: backend && backend.detailBadges.length > 0
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.smallSpacing

                            Repeater {
                                model: backend ? backend.detailBadges : []
                                delegate: Rectangle {
                                    radius: 4
                                    color: "transparent"
                                    border.color: Kirigami.Theme.highlightColor
                                    border.width: 1
                                    width: badgeLabel.implicitWidth + 10
                                    height: badgeLabel.implicitHeight + 4
                                    Controls.Label {
                                        id: badgeLabel
                                        anchors.centerIn: parent
                                        text: modelData
                                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.75
                                        color: Kirigami.Theme.highlightColor
                                    }
                                }
                            }
                        }
                    }
                }

                // ── Recommended Build card ────────────────────────────────
                Kirigami.Card {
                    visible: backend && !backend.detailLoading && backend.detailBuild.length > 0
                    Layout.fillWidth: true

                    header: Kirigami.Heading {
                        text: qsTr("Recommended Build")
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }

                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing

                        Controls.Label {
                            text: qsTr("Suggested by nanoka.cc")
                            color: Kirigami.Theme.disabledTextColor
                            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.85
                        }

                        // Two-column build sections grid
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: Kirigami.Units.largeSpacing
                            rowSpacing: Kirigami.Units.largeSpacing

                            Repeater {
                                model: backend ? backend.detailBuild : []
                                delegate: ColumnLayout {
                                    spacing: Kirigami.Units.smallSpacing

                                    Controls.Label {
                                        text: modelData.title
                                        font.bold: true
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }

                                    Repeater {
                                        model: modelData.items
                                        delegate: Controls.Label {
                                            text: "• " + modelData
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.9
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ── Overview card ─────────────────────────────────────────
                Kirigami.Card {
                    visible: backend && !backend.detailLoading && backend.detailOverview !== ""
                    Layout.fillWidth: true

                    header: Kirigami.Heading {
                        text: qsTr("Overview")
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }

                    contentItem: Controls.Label {
                        text: backend ? backend.detailOverview : ""
                        wrapMode: Text.Wrap
                        textFormat: Text.RichText
                    }
                }

                // ── Stats card ────────────────────────────────────────────
                Kirigami.Card {
                    visible: backend && !backend.detailLoading && backend.detailStats.length > 0
                    Layout.fillWidth: true

                    header: Kirigami.Heading {
                        text: qsTr("Stats")
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }

                    contentItem: ColumnLayout {
                        spacing: 2

                        Repeater {
                            model: backend ? backend.detailStats : []
                            delegate: RowLayout {
                                Layout.fillWidth: true
                                spacing: Kirigami.Units.largeSpacing

                                Controls.Label {
                                    text: modelData.name
                                    color: Kirigami.Theme.disabledTextColor
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                                Controls.Label {
                                    text: modelData.value
                                    horizontalAlignment: Text.AlignRight
                                    wrapMode: Text.Wrap
                                }
                            }
                        }
                    }
                }

                // ── Skills card ───────────────────────────────────────────
                Kirigami.Card {
                    visible: backend && !backend.detailLoading && backend.detailSkills.length > 0
                    Layout.fillWidth: true

                    header: Kirigami.Heading {
                        text: qsTr("Skills")
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }

                    contentItem: ColumnLayout {
                        spacing: 0

                        Controls.Label {
                            text: qsTr("Descriptions and multipliers are collapsed. Click a skill to expand.")
                            color: Kirigami.Theme.disabledTextColor
                            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.85
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                            bottomPadding: Kirigami.Units.smallSpacing
                        }

                        Repeater {
                            model: backend ? backend.detailSkills : []
                            delegate: ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0

                                // Disclosure header
                                Controls.AbstractButton {
                                    id: skillToggle
                                    property bool expanded: false
                                    Layout.fillWidth: true
                                    checkable: true
                                    checked: expanded
                                    onCheckedChanged: expanded = checked

                                    contentItem: RowLayout {
                                        Kirigami.Icon {
                                            source: skillToggle.expanded ? "arrow-down" : "arrow-right"
                                            implicitWidth: Kirigami.Units.iconSizes.small
                                            implicitHeight: Kirigami.Units.iconSizes.small
                                        }
                                        Controls.Label {
                                            text: modelData.name + " · " + modelData.typeName + " · Lv. " + modelData.level
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }
                                    }

                                    background: Rectangle {
                                        color: skillToggle.hovered
                                               ? Kirigami.Theme.hoverColor
                                               : "transparent"
                                        radius: Kirigami.Units.cornerRadius
                                    }
                                    topPadding: Kirigami.Units.smallSpacing
                                    bottomPadding: Kirigami.Units.smallSpacing
                                    leftPadding: Kirigami.Units.smallSpacing
                                    rightPadding: Kirigami.Units.smallSpacing
                                }

                                // Skill body (collapsible)
                                ColumnLayout {
                                    visible: skillToggle.expanded
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    leftPadding: Kirigami.Units.largeSpacing

                                    Controls.Label {
                                        visible: modelData.description !== ""
                                        text: modelData.description
                                        wrapMode: Text.Wrap
                                        textFormat: Text.RichText
                                        Layout.fillWidth: true
                                    }

                                    // Multipliers sub-section
                                    ColumnLayout {
                                        visible: modelData.multipliers && modelData.multipliers.length > 0
                                        Layout.fillWidth: true
                                        spacing: Kirigami.Units.smallSpacing

                                        Controls.Label {
                                            text: qsTr("Multipliers")
                                            font.bold: true
                                        }

                                        GridLayout {
                                            columns: 2
                                            columnSpacing: Kirigami.Units.largeSpacing
                                            rowSpacing: 2
                                            Layout.fillWidth: true

                                            Repeater {
                                                model: modelData.multipliers
                                                delegate: Controls.Label {
                                                    text: modelData.label
                                                    color: Kirigami.Theme.disabledTextColor
                                                    wrapMode: Text.Wrap
                                                    Layout.fillWidth: true
                                                }
                                            }
                                            Repeater {
                                                model: modelData.multipliers
                                                delegate: Controls.Label {
                                                    text: modelData.value
                                                    horizontalAlignment: Text.AlignRight
                                                    wrapMode: Text.Wrap
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }
                                    }
                                }

                                // Separator between skills
                                Kirigami.Separator { Layout.fillWidth: true }
                            }
                        }
                    }
                }

                // ── Extras card ───────────────────────────────────────────
                Kirigami.Card {
                    visible: backend && !backend.detailLoading && backend.detailExtras.length > 0
                    Layout.fillWidth: true

                    header: Kirigami.Heading {
                        text: qsTr("Passives, Traces & More")
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }

                    contentItem: ColumnLayout {
                        spacing: 0

                        Repeater {
                            model: backend ? backend.detailExtras : []
                            delegate: ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0

                                Controls.AbstractButton {
                                    id: extraToggle
                                    property bool expanded: false
                                    Layout.fillWidth: true
                                    checkable: true
                                    checked: expanded
                                    onCheckedChanged: expanded = checked

                                    contentItem: RowLayout {
                                        Kirigami.Icon {
                                            source: extraToggle.expanded ? "arrow-down" : "arrow-right"
                                            implicitWidth: Kirigami.Units.iconSizes.small
                                            implicitHeight: Kirigami.Units.iconSizes.small
                                        }
                                        Controls.Label {
                                            text: modelData.title
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }
                                    }

                                    background: Rectangle {
                                        color: extraToggle.hovered
                                               ? Kirigami.Theme.hoverColor
                                               : "transparent"
                                        radius: Kirigami.Units.cornerRadius
                                    }
                                    topPadding: Kirigami.Units.smallSpacing
                                    bottomPadding: Kirigami.Units.smallSpacing
                                    leftPadding: Kirigami.Units.smallSpacing
                                    rightPadding: Kirigami.Units.smallSpacing
                                }

                                ColumnLayout {
                                    visible: extraToggle.expanded
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    leftPadding: Kirigami.Units.largeSpacing
                                    bottomPadding: Kirigami.Units.smallSpacing

                                    Repeater {
                                        model: modelData.entries
                                        delegate: ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 2

                                            Controls.Label {
                                                text: modelData.name
                                                font.bold: true
                                                wrapMode: Text.Wrap
                                                Layout.fillWidth: true
                                            }
                                            Controls.Label {
                                                visible: modelData.text !== ""
                                                text: modelData.text
                                                wrapMode: Text.Wrap
                                                textFormat: Text.RichText
                                                Layout.fillWidth: true
                                            }
                                        }
                                    }
                                }

                                Kirigami.Separator { Layout.fillWidth: true }
                            }
                        }
                    }
                }

                // Bottom spacer
                Item { implicitHeight: Kirigami.Units.largeSpacing }
            }
        }
    }
}
