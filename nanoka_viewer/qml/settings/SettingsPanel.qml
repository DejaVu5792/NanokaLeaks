pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

// Content of the settings popup.
//
// ``settings`` is the SettingsViewModel context property installed by
// nanoka_viewer/ui/settings.py before this tree is parsed.  The widget
// overlay around it still owns the backdrop, the panel geometry, Escape
// handling and the modal input guard; this tree owns everything inside the
// panel.
Rectangle {
    id: panel
    objectName: "settingsPanelQml"

    radius: 8
    color: palette.window
    border.width: 1
    border.color: palette.mid

    // -- header -----------------------------------------------------------
    Item {
        id: headerArea
        objectName: "settingsHeader"
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 48
        clip: true

        // Square off the top corners the way the panel radius does.
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: headerArea.height + panel.radius
            radius: panel.radius
            color: palette.window
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: palette.midlight
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 12
            spacing: 10

            Label {
                objectName: "settingsTitle"
                Layout.alignment: Qt.AlignVCenter
                text: "Settings"
                color: palette.text
                font.pixelSize: 16
                font.bold: true
            }

            Item {
                Layout.fillWidth: true
            }

            AppButton {
                objectName: "settingsCloseButton"
                Layout.alignment: Qt.AlignVCenter
                text: "Close"
                small: true
                onClicked: settings.requestClose()
            }
        }
    }

    TabBar {
        id: tabBar
        objectName: "settingsTabs"
        anchors.top: headerArea.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        currentIndex: settings.tabIndex
        onCurrentIndexChanged: settings.setTab(currentIndex)

        background: Item {}

        SettingsTabButton {
            objectName: "settingsTabCache"
            text: "Cache"
        }

        SettingsTabButton {
            objectName: "settingsTabView"
            text: "View"
        }
    }

    // -- Cache tab --------------------------------------------------------
    Flickable {
        id: cachePage
        objectName: "settingsCachePage"
        anchors.top: tabBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        clip: true
        visible: settings.tabIndex === 0
        boundsBehavior: Flickable.StopAtBounds
        contentWidth: width
        contentHeight: cacheColumn.implicitHeight + 38

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            // AsNeeded can keep the bar visible after the page shrinks to fit
            // (it is re-evaluated on size changes only), so track the size.
            visible: size < 1.0
            contentItem: Rectangle {
                implicitWidth: 6
                radius: 3
                color: palette.mid
            }
            background: Rectangle { color: "transparent" }
        }

        Column {
            id: cacheColumn
            x: 20
            y: 18
            width: cachePage.width - 40
            spacing: 8

            SettingsSectionHeader {
                width: parent.width
                title: "Caching"
                tooltip: "Reset the cache options to their defaults"
                resetObjectName: "resetCaching"
                onResetClicked: settings.resetSection("caching")
            }

            SettingsCard {
                width: parent.width

                CacheRow {
                    objectName: "cacheRow-details"
                    Layout.fillWidth: true
                    title: "Cache character details"
                    tooltip: "Caches the detail text: overview, stats, skills, and extras."
                    checked: settings.cacheDetails
                    checkEnabled: settings.cacheEnabled
                    buttonText: settings.detailsButtonText
                    buttonEnabled: settings.detailsButtonEnabled
                    buttonTooltip: settings.detailsButtonTooltip
                    buttonObjectName: "preloadDetails"
                    sizeText: settings.detailsSize
                    onToggled: (checked) => settings.setCache("details", checked)
                    onPreloadClicked: settings.preload("details")
                }

                Rectangle {
                    objectName: "settingsRowSeparator"
                    Layout.fillWidth: true
                    implicitHeight: 1
                    color: palette.midlight
                }

                CacheRow {
                    objectName: "cacheRow-builds"
                    Layout.fillWidth: true
                    title: "Cache character builds"
                    tooltip: "Always refreshes the per-version build tables used by recommended builds; unchanged tables are revalidated with ETags."
                    checked: settings.cacheBuilds
                    checkEnabled: settings.cacheEnabled
                    buttonText: settings.buildsButtonText
                    buttonEnabled: settings.buildsButtonEnabled
                    buttonTooltip: settings.buildsButtonTooltip
                    buttonObjectName: "preloadBuilds"
                    sizeText: settings.buildsSize
                    lastCachedText: settings.buildsLast
                    onToggled: (checked) => settings.setCache("builds", checked)
                    onPreloadClicked: settings.preload("builds")
                }

                Rectangle {
                    objectName: "settingsRowSeparator"
                    Layout.fillWidth: true
                    implicitHeight: 1
                    color: palette.midlight
                }

                CacheRow {
                    objectName: "cacheRow-artwork"
                    Layout.fillWidth: true
                    title: "Cache character details artwork"
                    tooltip: "Details artwork is a large download and uses much more disk space than the text caches."
                    checked: settings.cacheArtwork
                    checkEnabled: settings.cacheEnabled
                    buttonText: settings.artworkButtonText
                    buttonEnabled: settings.artworkButtonEnabled
                    buttonTooltip: settings.artworkButtonTooltip
                    buttonObjectName: "preloadArtwork"
                    sizeText: settings.artworkSize
                    onToggled: (checked) => settings.setCache("artwork", checked)
                    onPreloadClicked: settings.preload("artwork")
                }
            }

            Label {
                objectName: "cacheStatus"
                width: parent.width
                visible: text.length > 0
                text: settings.cacheStatus
                color: palette.placeholderText
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            Item {
                width: 1
                height: 4
            }

            AppButton {
                objectName: "clearCacheButton"
                text: settings.clearCacheText
                enabled: settings.clearCacheEnabled
                onClicked: settings.clearCache()

                ToolTip.text: settings.clearCacheTooltip
                ToolTip.visible: hovered && settings.clearCacheTooltip.length > 0
            }

            Item {
                width: 1
                height: 8
            }
        }
    }

    // -- View tab ---------------------------------------------------------
    Flickable {
        id: viewPage
        objectName: "settingsViewPage"
        anchors.top: tabBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        clip: true
        visible: settings.tabIndex === 1
        boundsBehavior: Flickable.StopAtBounds
        contentWidth: width
        contentHeight: viewColumn.implicitHeight + 38

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            // AsNeeded can keep the bar visible after the page shrinks to fit
            // (it is re-evaluated on size changes only), so track the size.
            visible: size < 1.0
            contentItem: Rectangle {
                implicitWidth: 6
                radius: 3
                color: palette.mid
            }
            background: Rectangle { color: "transparent" }
        }

        Column {
            id: viewColumn
            x: 20
            y: 18
            width: viewPage.width - 40
            spacing: 8

            SettingsSectionHeader {
                width: parent.width
                title: "Toggle View"
                tooltip: "Enable every game"
                resetObjectName: "resetToggle"
                onResetClicked: settings.resetSection("toggle")
            }

            SettingsCard {
                width: parent.width

                Repeater {
                    model: settings.games

                    delegate: Item {
                        id: toggleSlot
                        required property int index
                        required property string gameId
                        required property string name
                        required property bool gameEnabled
                        required property string countText
                        required property string countTooltip

                        Layout.fillWidth: true
                        implicitHeight: rowItem.implicitHeight
                            + (toggleSlot.index > 0 ? 1 : 0)

                        Rectangle {
                            width: parent.width
                            height: 1
                            visible: toggleSlot.index > 0
                            color: palette.midlight
                        }

                        GameToggleRow {
                            id: rowItem
                            objectName: "gameToggleRow-" + toggleSlot.gameId
                            width: parent.width
                            y: toggleSlot.index > 0 ? 1 : 0
                            gameName: toggleSlot.name
                            checked: toggleSlot.gameEnabled
                            countText: toggleSlot.countText
                            countTooltip: toggleSlot.countTooltip
                            onToggled: (checked) => settings.setGameEnabled(
                                toggleSlot.gameId, checked
                            )
                        }
                    }
                }
            }

            Item {
                width: 1
                height: 8
            }

            SettingsSectionHeader {
                width: parent.width
                title: "View Order"
                tooltip: "Restore the default game order"
                resetObjectName: "resetOrder"
                onResetClicked: settings.resetSection("order")
            }

            Label {
                objectName: "settingsHint"
                width: parent.width
                text: "Drag the enabled games to reorder their sections."
                color: palette.placeholderText
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            SettingsCard {
                width: parent.width
                horizontalPadding: 4

                Item {
                    id: orderArea

                    Layout.fillWidth: true
                    implicitHeight: orderList.contentHeight

                    ListView {
                        id: orderList
                        objectName: "gameOrderList"
                        anchors.fill: parent
                        interactive: false
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        model: settings.order

                        delegate: GameOrderRow {
                            required property int index
                            required property string gameId
                            required property string gameName

                            objectName: "gameOrderRow-" + gameId
                            width: orderList.width
                            label: gameName
                            dragging: orderDrag.active
                                && orderDrag.from === index
                        }
                    }

                    // Insertion line, like the widget list's drop indicator.
                    Rectangle {
                        objectName: "orderDropIndicator"
                        visible: orderDrag.active
                            && orderDrag.targetIndex !== orderDrag.from
                        x: 0
                        width: parent.width
                        height: 4
                        color: palette.highlight
                        y: Math.max(
                            0,
                            Math.min(
                                orderArea.height - height,
                                orderDrag.targetIndex * 34
                            )
                        )
                    }

                    MouseArea {
                        id: orderDrag
                        objectName: "gameOrderDragArea"
                        anchors.fill: parent
                        hoverEnabled: true

                        property int from: -1
                        property int targetIndex: -1
                        readonly property bool active: pressed && from >= 0

                        onPressed: (mouse) => {
                            from = orderList.indexAt(mouse.x, mouse.y)
                            targetIndex = from
                        }

                        onPositionChanged: (mouse) => {
                            if (from < 0)
                                return
                            const index = orderList.indexAt(mouse.x, mouse.y)
                            if (index >= 0)
                                targetIndex = index
                            else if (mouse.y < 0)
                                targetIndex = 0
                            else
                                targetIndex = orderList.count - 1
                        }

                        onReleased: {
                            if (from >= 0 && targetIndex >= 0
                                    && targetIndex !== from)
                                settings.moveGame(from, targetIndex)
                            from = -1
                            targetIndex = -1
                        }

                        onCanceled: {
                            from = -1
                            targetIndex = -1
                        }
                    }
                }

                Label {
                    objectName: "gameOrderEmptyHint"
                    Layout.fillWidth: true
                    Layout.margins: 10
                    visible: orderList.count === 0
                    text: "No games enabled."
                    color: palette.placeholderText
                    font.pixelSize: 11
                }
            }

            Item {
                width: 1
                height: 8
            }

            SettingsSectionHeader {
                width: parent.width
                title: "Experimental"
                tooltip: "Reset experimental options to their defaults"
                resetObjectName: "resetExperimental"
                onResetClicked: settings.resetSection("experimental")
            }

            Label {
                objectName: "experimentalHint"
                width: parent.width
                text: "Experimental artwork options. Changes apply the next time a character detail popup opens."
                color: palette.placeholderText
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            SettingsCard {
                width: parent.width

                CacheRow {
                    objectName: "experimentalRow"
                    Layout.fillWidth: true
                    showButton: false
                    title: "Smart artwork centering"
                    tooltip: "Offsets the details artwork horizontally toward the spectral-residual saliency centroid. On by default."
                    checked: settings.srCentroid
                    onToggled: (checked) => settings.setSrCentroid(checked)
                }
            }

            Item {
                width: 1
                height: 8
            }
        }
    }
}
