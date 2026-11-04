import QtQuick
import QtQuick.Controls

// One step of the View Order list's keyboard/pointer alternative to dragging.
ToolButton {
    id: button

    property string glyph: ""
    property string tip: ""

    implicitWidth: 22
    implicitHeight: 22

    ToolTip.text: tip
    ToolTip.visible: hovered && enabled && tip.length > 0
    ToolTip.delay: 600

    background: Rectangle {
        radius: 3
        color: button.hovered && button.enabled
            ? palette.alternateBase
            : "transparent"
    }

    contentItem: Text {
        text: button.glyph
        color: palette.text
        opacity: button.enabled ? 1.0 : 0.35
        font.pixelSize: 12
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
