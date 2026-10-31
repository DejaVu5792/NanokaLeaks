pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One game row: header (name, version badges, load status) above a
// horizontally scrolling strip of character cards.
Item {
    id: sectionRoot

    required property var section

    readonly property int cardWidth: 180
    readonly property int cardSpacing: 8
    readonly property int rowHeight: 230

    implicitHeight: layout.implicitHeight

    Column {
        id: layout
        width: parent.width
        topPadding: 8
        bottomPadding: 8
        spacing: 4

        Rectangle {
            id: header
            objectName: "gameHeader"
            width: parent.width
            height: headerRow.implicitHeight + 20
            radius: 8
            color: palette.alternateBase

            RowLayout {
                id: headerRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 8

                Label {
                    objectName: "sectionTitle"
                    text: sectionRoot.section.name
                    color: palette.windowText
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                }

                Row {
                    spacing: 6
                    Layout.leftMargin: 8

                    Badge {
                        objectName: "liveBadge"
                        visible: sectionRoot.section.liveVersion.length > 0
                        text: "Live v" + sectionRoot.section.liveVersion
                        live: true
                    }

                    Badge {
                        objectName: "betaBadge"
                        visible: sectionRoot.section.liveVersion.length > 0
                                 && sectionRoot.section.latestVersion.length > 0
                        text: "Beta v" + sectionRoot.section.latestVersion.split("+")[0]
                        live: false
                    }
                }

                Item { Layout.fillWidth: true }

                Label {
                    objectName: "sectionStatus"
                    text: sectionRoot.section.status
                    color: palette.placeholderText
                    font.pixelSize: 12
                }
            }
        }

        ListView {
            id: cardList
            objectName: "cardList"
            width: parent.width
            height: sectionRoot.rowHeight + 12
            orientation: ListView.Horizontal
            spacing: sectionRoot.cardSpacing
            leftMargin: 4
            rightMargin: 4
            bottomMargin: 12
            // One viewport of look-ahead: cards just off screen load their
            // artwork before the user scrolls to them, while a cold start
            // still only touches a handful of delegates.
            cacheBuffer: Math.max(width, 0)
            reuseItems: true
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: sectionRoot.section.characters

            ScrollBar.horizontal: ScrollBar {
                policy: ScrollBar.AsNeeded
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                contentItem: Rectangle {
                    implicitHeight: 6
                    radius: 3
                    color: palette.mid
                }
                background: Rectangle { color: "transparent" }
            }

            MouseArea {
                anchors.fill: parent
                // Propagate clicks through to delegate items (e.g., character cards)
                propagateComposedEvents: true
                onPressed: (mouse) => mouse.accepted = false

                onWheel: (wheel) => {
                    if (wheel.modifiers & Qt.ShiftModifier) {
                        // Determine scroll distance from wheel delta
                        let delta = wheel.angleDelta.y !== 0 ? wheel.angleDelta.y : wheel.angleDelta.x
                        cardList.flick(delta * 5, 0) // Or directly adjust cardList.contentX
                        wheel.accepted = true
                    } else {
                        wheel.accepted = false // Allow standard vertical scroll to bubble up to parent page
                    }
                }
            }

            delegate: Item {
                id: slot

                required property string charId
                required property string fullName
                required property string displayName
                required property string rarity
                required property string rarityColor
                required property string element
                required property string elementText
                required property string elementImage
                required property string specialty
                required property string specialtyImage
                required property string image
                required property string url
                required property bool isNew

                width: sectionRoot.cardWidth
                height: cardList.height

                CharacterCard {
                    anchors.verticalCenter: parent.verticalCenter
                    game: sectionRoot.section.game
                    charId: slot.charId
                    fullName: slot.fullName
                    displayName: slot.displayName
                    rarity: slot.rarity
                    rarityColor: slot.rarityColor
                    element: slot.element
                    elementText: slot.elementText
                    elementImage: slot.elementImage
                    specialty: slot.specialty
                    specialtyImage: slot.specialtyImage
                    image: slot.image
                    url: slot.url
                    isNew: slot.isNew
                }
            }
        }
    }
}
