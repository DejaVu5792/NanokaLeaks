pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// Content of the character-details popup.
//
// ``details`` is the DetailsViewModel context property installed by
// nanoka_viewer/ui/details.py before this tree is parsed.  The overlay shell
// around it (backdrop, panel, Escape, click-outside) is Overlay.qml; this tree
// only owns everything inside the panel.
Item {
    id: panel
    objectName: "detailsPanelQml"

    // Matches the shell's panel radius so the header strip follows the top
    // corners.
    property int cornerRadius: 10

    // Scroll to the Rule Terms entry *termId* and briefly flash it.
    function revealTerm(termId) {
        var wanted = String(termId)
        for (var index = 0; index < details.terms.length; ++index) {
            if (String(details.terms[index].id) !== wanted)
                continue
            var item = termsRepeater.itemAt(index)
            if (!item)
                return
            var point = item.mapToItem(contentColumn, 0, 0)
            var top = point.y + contentColumn.y
            var maxY = Math.max(0, scroll.contentHeight - scroll.height)
            scroll.contentY = Math.max(0, Math.min(top - 12, maxY))
            if (item.flash)
                item.flash()
            return
        }
    }

    // Hide any active hover card.
    function hideTermHover() {
        termHoverCard.opacity = 0
    }

    // Display the hover card for *termId* anchored to scene point (*sceneX*, *sceneY*).
    function showTermHover(termId, sceneX, sceneY) {
        if (typeof details === "undefined")
            return
        var name = details.termName(termId)
        var body = details.termTooltip(termId)
        if (name.length === 0 && body.length === 0)
            return

        termHoverCard.termName = name
        termHoverCard.termText = body

        var panelPt = panel.mapFromItem(null, sceneX, sceneY)
        var cardW = termHoverCard.width
        var cardH = termHoverLayout.implicitHeight + 20
        var gap = 8

        // Horizontally center on panelPt.x, clamped inside panel
        var minX = scroll.x + 12
        var maxX = panel.width - cardW - 12
        var cx = panelPt.x - cardW / 2
        termHoverCard.x = Math.max(minX, Math.min(cx, maxX))

        // Position top preferably; flip to bottom if it doesn't fit on screen
        var topLimit = headerArea.height + 6
        var spaceAbove = (panelPt.y - cardH - gap) - topLimit

        if (spaceAbove >= 0) {
            termHoverCard.y = panelPt.y - cardH - gap
        } else {
            var bottomY = panelPt.y + 16 + gap
            var maxBottomY = panel.height - cardH - 10
            termHoverCard.y = Math.min(bottomY, maxBottomY)
        }

        termHoverCard.opacity = 1
    }

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
            height: headerArea.height + panel.cornerRadius
            radius: panel.cornerRadius
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
            onContentYChanged: panel.hideTermHover()

            ScrollBar.vertical: AppScrollBar {}

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
                        active: details.state === "loading"
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
                        active: details.state === "loading"
                        width: parent.width
                        rows: [
                            [[22, 16]],
                            [[94, 9], [86, 9], [66, 9]],
                            [[92, 9], [78, 9], [58, 9]]
                        ]
                    }

                    SkeletonCard {
                        active: details.state === "loading"
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
                        active: details.state === "loading"
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

                    SelectableText {
                        Layout.fillWidth: true
                        text: details.errorMessage
                        color: palette.placeholderText
                        font.pixelSize: 12
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

                    SelectableText {
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
                                        Layout.preferredWidth: 1      // equal halves
                                        Layout.alignment: Qt.AlignTop
                                        spacing: 4

                                        SelectableText {
                                            Layout.fillWidth: true
                                            text: buildSection.modelData.title
                                            color: palette.text
                                            font.pixelSize: 12
                                            font.bold: true
                                        }

                                        Repeater {
                                            model: buildSection.modelData.items

                                            delegate: SelectableText {
                                                required property var modelData

                                                Layout.fillWidth: true
                                                text: "\u2022 " + modelData
                                                color: palette.text
                                                font.pixelSize: 11
                                            }
                                        }
                                    }
                                }

                                // keeps a lone section (like Substats) at half width
                                Item {
                                    visible: buildRow.modelData.length < 2
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
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

                    SelectableText {
                        objectName: "detailsSubtitle"
                        Layout.fillWidth: true
                        visible: details.subtitle.length > 0
                        text: details.subtitle
                        textFormat: TextEdit.RichText
                        color: palette.placeholderText
                        font.pixelSize: 11
                    }

                    SelectableText {
                        objectName: "detailsOverview"
                        Layout.fillWidth: true
                        visible: details.overview.length > 0
                        text: details.overview
                        textFormat: TextEdit.RichText
                        color: palette.text
                        font.pixelSize: 12
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
                                        Layout.preferredWidth: 1          // equal halves in every row
                                        Layout.alignment: Qt.AlignTop
                                        spacing: 8

                                        SelectableText {
                                            Layout.preferredWidth: 112
                                            Layout.minimumWidth: 112
                                            Layout.alignment: Qt.AlignLeft | Qt.AlignTop
                                            text: stat.modelData.label
                                            color: palette.placeholderText
                                            font.pixelSize: 11
                                        }

                                        SelectableText {
                                            Layout.alignment: Qt.AlignLeft | Qt.AlignTop
                                            horizontalAlignment: Text.AlignLeft
                                            text: stat.modelData.value
                                            color: palette.text
                                            font.pixelSize: 11
                                            font.bold: true
                                        }

                                        // lets the cell grow to its half of the row; without a fill child the
                                        // cell is capped at its content width and the halves go uneven
                                        Item { Layout.fillWidth: true }
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

                    SelectableText {
                        Layout.fillWidth: true
                        text: "No constellation, sequence, mindscape, or resonance boosts."
                        color: palette.placeholderText
                        font.pixelSize: 11
                    }
                }

                // -- skills -----------------------------------------------
                DetailCard {
                    objectName: "detailsSkillsCard"
                    visible: details.state === "ready"
                             && details.skills.length > 0
                    title: "Skills"

                    SelectableText {
                        Layout.fillWidth: true
                        text: "Descriptions and multipliers are collapsed. "
                              + "Click a skill to expand."
                        color: palette.placeholderText
                        font.pixelSize: 11
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

                // -- rule terms -------------------------------------------
                DetailCard {
                    objectName: "detailsTermsCard"
                    visible: details.state === "ready"
                             && details.terms.length > 0
                    title: "Rule Terms"

                    Repeater {
                        id: termsRepeater
                        model: details.terms

                        delegate: Rectangle {
                            id: term
                            required property var modelData

                            function flash() {
                                flashAnimation.restart()
                            }

                            Layout.fillWidth: true
                            implicitHeight: termColumn.implicitHeight + 12
                            radius: 6
                            color: "transparent"

                            Rectangle {
                                id: termFlash
                                anchors.fill: parent
                                radius: parent.radius
                                color: palette.highlight
                                opacity: 0
                            }

                            SequentialAnimation {
                                id: flashAnimation
                                NumberAnimation {
                                    target: termFlash
                                    property: "opacity"
                                    from: 0.28
                                    to: 0
                                    duration: 900
                                    easing.type: Easing.OutCubic
                                }
                            }

                            ColumnLayout {
                                id: termColumn
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 6
                                spacing: 3

                                SelectableText {
                                    Layout.fillWidth: true
                                    text: term.modelData.name
                                    color: palette.text
                                    font.pixelSize: 12
                                    font.bold: true
                                }

                                SelectableText {
                                    Layout.fillWidth: true
                                    visible: term.modelData.text.length > 0
                                    text: term.modelData.text
                                    textFormat: TextEdit.RichText
                                    color: palette.text
                                    font.pixelSize: 12
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // -- rule terms hover card --------------------------------------------
    Rectangle {
        id: termHoverCard
        objectName: "termHoverCard"
        z: 100
        visible: opacity > 0
        opacity: 0

        property string termName: ""
        property string termText: ""

        width: Math.max(220, Math.min(380, Math.round((scroll.width - 32) * 0.60)))
        implicitHeight: termHoverLayout.implicitHeight + 20
        height: implicitHeight

        radius: 8
        color: palette.base
        border.width: 1
        border.color: palette.mid

        Behavior on opacity {
            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
        }

        ColumnLayout {
            id: termHoverLayout
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 10
            spacing: 6

            Text {
                objectName: "termHoverTitle"
                visible: termHoverCard.termName.length > 0
                Layout.fillWidth: true
                text: termHoverCard.termName
                color: palette.text
                font.pixelSize: 13
                font.bold: true
                wrapMode: Text.Wrap
            }

            Text {
                objectName: "termHoverBody"
                visible: termHoverCard.termText.length > 0
                Layout.fillWidth: true
                text: termHoverCard.termText
                textFormat: Text.RichText
                color: palette.text
                font.pixelSize: 12
                wrapMode: Text.Wrap
            }
        }
    }

    Connections {
        target: details

        function onStateChanged() {
            scroll.contentY = 0
            panel.hideTermHover()
        }

        function onTermActivated(termId) {
            panel.revealTerm(termId)
        }

        function onTermHoverShown(termId, wx, wy) {
            panel.showTermHover(termId, wx, wy)
        }

        function onTermHoverHidden() {
            panel.hideTermHover()
        }
    }
}
