import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl   // IconImage

// The app's button look, drawn from the palette instead of a Controls style.
//
// It mirrors the QSS the widget UI used: 6px radius (4px for the small
// in-card buttons), palette(button) fill, palette(mid) border, hover
// palette(mid), pressed palette(midlight).  The primary variant uses
// palette(highlight), like the card's View button.
//
// Set icon.name to draw a theme icon (tinted to the text colour); text is the
// fallback when the theme has no such icon.
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

    contentItem: Item {
        implicitWidth: label.implicitWidth
        implicitHeight: label.implicitHeight

        IconImage {
            id: glyph
            anchors.centerIn: parent
            name: control.icon.name
            color: label.color            // symbolic icons follow the palette
            sourceSize.width: control.icon.width > 0 ? control.icon.width : 16
            sourceSize.height: control.icon.height > 0 ? control.icon.height : 16
            visible: control.icon.name.length > 0 && status === Image.Ready
        }

        Text {
            id: label
            anchors.fill: parent
            visible: !glyph.visible       // "↗" shows if the theme has no icon
            text: control.text
            font: control.font
            color: control.primary
            ? palette.highlightedText
            : control.enabled ? palette.buttonText : palette.placeholderText
            horizontalAlignment: control.alignLeft ? Text.AlignLeft : Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
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
