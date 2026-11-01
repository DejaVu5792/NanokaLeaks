import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One character card: rarity, portrait, element/specialty icons, name and the
// two actions (details popup, external browser).
//
// Geometry mirrors the old CardWidget exactly (180x220, 12px margins, 80px
// portrait, 20px icons) so the row keeps its proportions while data and
// artwork stream in.
Item {
    id: card
    objectName: "characterCard"

    property string game: ""
    property string charId: ""
    property string fullName: ""
    property string displayName: ""
    property string rarity: ""
    property string rarityColor: ""
    property string element: ""
    property string elementText: "?"
    property string elementImage: ""
    property string specialty: ""
    property string specialtyImage: ""
    property string image: ""
    property string url: ""
    property bool isNew: false

    readonly property int cardWidth: 180
    readonly property int cardHeight: 220
    readonly property int portraitSize: 80
    readonly property int iconSize: 20

    // True when the portrait can never arrive: no URL, or the provider
    // returned a null image (QML reports that as Image.Error).
    readonly property bool portraitFailed: card.image.length === 0
                                          || portrait.status === Image.Error

    implicitWidth: cardWidth
    implicitHeight: cardHeight

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: palette.base
        border.width: 1
        border.color: palette.mid
    }

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 6

        Label {
            objectName: "rarityLabel"
            width: parent.width
            text: card.rarity
            horizontalAlignment: Text.AlignRight
            font.pixelSize: 11
            font.bold: true
            color: card.rarityColor.length > 0 ? card.rarityColor : palette.text
        }

        Item {
            width: parent.width
            height: card.portraitSize

            Rectangle {
                id: portraitFrame
                anchors.horizontalCenter: parent.horizontalCenter
                width: card.portraitSize
                height: card.portraitSize
                radius: 8
                color: "transparent"

                // The skeleton stays underneath the artwork so the image can
                // cross-fade in instead of popping over the card background.
                Rectangle {
                    id: placeholder
                    objectName: "portraitPlaceholder"
                    anchors.fill: parent
                    radius: portraitFrame.radius
                    visible: !card.portraitFailed
                    color: Qt.rgba(
                        (palette.midlight.r + palette.mid.r) / 2,
                        (palette.midlight.g + palette.mid.g) / 2,
                        (palette.midlight.b + palette.mid.b) / 2,
                        1)

                    SequentialAnimation on opacity {
                        running: placeholder.visible
                                 && portrait.status !== Image.Ready
                        loops: Animation.Infinite
                        NumberAnimation {
                            from: 0.55; to: 0.95
                            duration: 900
                            easing.type: Easing.InOutSine
                        }
                        NumberAnimation {
                            from: 0.95; to: 0.55
                            duration: 900
                            easing.type: Easing.InOutSine
                        }
                    }
                }

                Image {
                    id: portrait
                    objectName: "portrait"
                    anchors.fill: parent
                    asynchronous: true
                    fillMode: Image.PreserveAspectCrop
                    sourceSize.width: card.portraitSize
                    sourceSize.height: card.portraitSize
                    source: card.image
                        ? "image://nanoka/?url=" + encodeURIComponent(card.image)
                          + "&w=" + card.portraitSize + "&h=" + card.portraitSize
                        : ""
                    visible: status === Image.Ready
                    opacity: status === Image.Ready ? 1 : 0
                    Behavior on opacity {
                        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                    }
                }

                // Qt Quick cannot clip an Image to a rounded rectangle without
                // a shader effect; a rounded outline over the square artwork
                // keeps the frame visually consistent on every backend.
                Rectangle {
                    anchors.fill: parent
                    radius: portraitFrame.radius
                    color: "transparent"
                    border.width: 1
                    border.color: palette.mid
                    visible: portrait.status === Image.Ready
                }

                // A failed portrait shows a quiet dash instead of pulsing
                // forever (or looking like it is still loading).
                Rectangle {
                    objectName: "portraitUnavailable"
                    anchors.centerIn: parent
                    width: 12
                    height: 2
                    radius: 1
                    color: palette.placeholderText
                    opacity: 0.7
                    visible: card.portraitFailed
                }

                HoverHandler { id: portraitHover }

                ToolTip.visible: portraitHover.hovered && card.fullName.length > 0
                ToolTip.text: card.fullName
                ToolTip.delay: 600
            }
        }

        Item {
            width: parent.width
            height: card.iconSize

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 8

                IconBadge {
                    objectName: "elementIcon"
                    size: card.iconSize
                    source: card.elementImage
                    fallbackText: card.elementText
                    tooltip: card.element
                }

                IconBadge {
                    objectName: "specialtyIcon"
                    size: card.iconSize
                    visible: card.specialtyImage.length > 0
                    source: card.specialtyImage
                    fallbackText: "?"
                    tooltip: card.specialty
                }
            }
        }

        Label {
            objectName: "nameLabel"
            width: parent.width
            text: card.displayName
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            font.pixelSize: 12
            font.weight: Font.DemiBold
            color: palette.text
        }

        RowLayout {
            width: parent.width
            spacing: 4

            AppButton {
                objectName: "viewButton"
                Layout.fillWidth: true
                small: true
                primary: true
                text: "View"
                onClicked: viewer.openDetails(card.game, card.charId)

                ToolTip.visible: hovered
                ToolTip.text: "Open character details"
                ToolTip.delay: 600
            }

            AppButton {
                objectName: "browserButton"
                small: true
                square: true
                text: "\u2197"                          // fallback glyph
                icon.name: viewer.externalIconName
                icon.width: 16
                icon.height: 16
                onClicked: viewer.openExternal(card.url)

                ToolTip.visible: hovered
                ToolTip.text: "Open in default browser"
                ToolTip.delay: 600
            }
        }
    }

    Rectangle {
        objectName: "newBadge"
        visible: card.isNew
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 3
        radius: 6
        color: palette.highlight
        implicitWidth: newLabel.implicitWidth + 8
        implicitHeight: newLabel.implicitHeight + 4

        Text {
            id: newLabel
            anchors.centerIn: parent
            text: "NEW"
            color: palette.highlightedText
            font.pixelSize: 9
            font.bold: true
        }
    }
}
