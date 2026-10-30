import QtQuick
import QtQuick.Layouts

// Kirigami FormCard-like container for one group of settings rows.
Rectangle {
    id: card

    // The cache and games cards inset their rows by 14px; the order card only
    // needs a 4px frame around its list.
    property int horizontalPadding: 14
    property int verticalPadding: 4

    default property alias content: body.data

    implicitHeight: body.implicitHeight + 2 * verticalPadding
    radius: 6
    color: palette.base
    border.width: 1
    border.color: palette.midlight

    ColumnLayout {
        id: body
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: card.verticalPadding
        anchors.leftMargin: card.horizontalPadding
        anchors.rightMargin: card.horizontalPadding
        spacing: 0
    }
}
