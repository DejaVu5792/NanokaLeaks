import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One themed card in the details scroll area.
//
// Children land in the body column, so a card reads as
//
//     DetailCard {
//         title: "Overview"
//         Label { ... }
//     }
Rectangle {
    id: card

    property string title: ""

    default property alias content: body.data

    width: parent ? parent.width : 0
    implicitHeight: layout.implicitHeight + 28
    height: implicitHeight
    radius: 8
    color: palette.base
    border.width: 1
    border.color: palette.mid

    ColumnLayout {
        id: layout
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 14
        spacing: 10

        Label {
            objectName: "detailSectionTitle"
            visible: card.title.length > 0
            Layout.fillWidth: true
            text: card.title
            color: palette.text
            font.pixelSize: 15
            font.bold: true
            wrapMode: Text.WordWrap
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 10
        }
    }
}
