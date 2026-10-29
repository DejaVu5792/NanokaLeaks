import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    id: root
    property var cardData: ({})

    width: 180
    height: 220
    radius: Kirigami.Units.cornerRadius
    color: Kirigami.Theme.backgroundColor
    border.color: Kirigami.Theme.separatorColor
    border.width: 1

    // NEW badge
    Rectangle {
        visible: cardData.isNew || false
        z: 2
        x: 4; y: 4
        width: newLabel.implicitWidth + 6
        height: newLabel.implicitHeight + 2
        radius: 3
        color: Kirigami.Theme.highlightColor
        Controls.Label {
            id: newLabel
            anchors.centerIn: parent
            text: "NEW"
            font.bold: true
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.65
            color: Kirigami.Theme.highlightedTextColor
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.smallSpacing

        // Rarity label
        Controls.Label {
            Layout.alignment: Qt.AlignRight
            text: (cardData.rarity || "") + "★"
            font.bold: true
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.85
            color: {
                var r = cardData.rarity || ""
                if (r === "S" || r === "A") return "#FF6B6B"
                if (r === "5") return "#FFD700"
                if (r === "4") return "#9370DB"
                return Kirigami.Theme.textColor
            }
        }

        // Character image
        Image {
            id: charImage
            Layout.alignment: Qt.AlignHCenter
            width: 80; height: 80
            source: cardData.imageUrl || ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            clip: true
            layer.enabled: true
            layer.effect: null

            Rectangle {
                visible: charImage.status !== Image.Ready
                anchors.fill: parent
                radius: 8
                color: Kirigami.Theme.alternateBackgroundColor
                opacity: 0.8
            }
        }

        // Element + Specialty icons
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: Kirigami.Units.smallSpacing

            Image {
                width: 20; height: 20
                source: cardData.elementImageUrl || ""
                visible: (cardData.elementImageUrl || "") !== ""
                asynchronous: true
            }
            Image {
                width: 20; height: 20
                source: cardData.specialtyImageUrl || ""
                visible: (cardData.specialtyImageUrl || "") !== ""
                asynchronous: true
            }
        }

        // Name
        Controls.Label {
            Layout.fillWidth: true
            text: {
                var n = cardData.name || ""
                return n.length > 14 ? n.substring(0, 14) + "..." : n
            }
            font.bold: true
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.9
            horizontalAlignment: Text.AlignHCenter
        }

        // Action buttons
        RowLayout {
            Layout.fillWidth: true

            Controls.Button {
                Layout.fillWidth: true
                text: qsTr("View")
                onClicked: backend.openCharacterDetails(cardData.gameId, cardData.charId, cardData)
            }

            Controls.Button {
                icon.name: "document-open-remote"
                onClicked: Qt.openUrlExternally(cardData.url || "")
                implicitWidth: implicitHeight
            }
        }

        Item { Layout.fillHeight: true }
    }
}
