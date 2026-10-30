import QtQuick
import QtQuick.Controls

// The app's button look, drawn from the palette instead of a Controls style.
//
// It mirrors the QSS the widget UI used: 6px radius (4px for the small
// in-card buttons), palette(button) fill, palette(mid) border, hover
// palette(mid), pressed palette(midlight).  The primary variant uses
// palette(highlight), like the card's View button.
AbstractButton {
    id: control

    property bool primary: false
    property bool small: false
    property bool square: false
    // Disclosure rows read as a list entry, not as a centred button.
    property bool alignLeft: false

    implicitHeight: small ? 28 : 32
    implicitWidth: square
        ? implicitHeight
        : Math.ceil(contentItem.implicitWidth) + leftPadding + rightPadding

    leftPadding: small ? 12 : 16
    rightPadding: small ? 12 : 16
    topPadding: 6
    bottomPadding: 6
    font.pixelSize: small ? 11 : 13

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.primary
            ? palette.highlightedText
            : control.enabled ? palette.buttonText : palette.placeholderText
        horizontalAlignment: control.alignLeft ? Text.AlignLeft : Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: control.small ? 4 : 6
        color: {
            if (!control.enabled)
                return palette.midlight
            if (control.primary)
                return palette.highlight
            if (control.down)
                return palette.midlight
            if (control.hovered)
                return palette.mid
            return palette.button
        }
        border.width: 1
        border.color: control.primary
            ? (control.hovered ? palette.windowText : "transparent")
            : palette.mid
    }

    HoverHandler {
        cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }
}
