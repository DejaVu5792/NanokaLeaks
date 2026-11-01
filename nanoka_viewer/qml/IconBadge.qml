import QtQuick
import QtQuick.Controls

// Small circular icon with a text fallback, mirroring the widget's 20x20
// element/specialty labels: the letter shows until the artwork is decoded,
// and stays if the download fails.
Item {
    id: icon

    property string source: ""
    property string fallbackText: "?"
    property string tooltip: ""
    property int size: 20

    implicitWidth: size
    implicitHeight: size

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: "#2A2A2A"
        border.width: 1
        border.color: "#444444"
    }

    Text {
        anchors.centerIn: parent
        text: icon.fallbackText
        visible: image.status !== Image.Ready
        color: palette.placeholderText
        font.pixelSize: 9
    }

    Image {
        id: image
        anchors.fill: parent
        asynchronous: true
        fillMode: Image.PreserveAspectFit
        sourceSize.width: icon.size - 2
        sourceSize.height: icon.size - 2
        source: icon.source
            ? "image://nanoka/?url=" + encodeURIComponent(icon.source)
              + "&w=" + (icon.size - 2) + "&h=" + (icon.size - 2)
            : ""
    }

    HoverHandler { id: hover }

    ToolTip.visible: hover.hovered && icon.tooltip.length > 0
    ToolTip.text: icon.tooltip
    ToolTip.delay: 600
}
