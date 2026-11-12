import QtQuick
import QtQuick.Controls

// Kirigami-style toggle switch drawn from the palette.
//
// Unlike a Controls Switch, it never owns the checked state: callers bind
// ``checked`` and handle ``toggled`` so the model stays the single source of
// truth.  Set ``interactive`` to false when a surrounding row handles clicks
// itself (the game toggles do this).
Item {
    id: control

    property bool checked: false
    property bool interactive: true
    property string tooltip: ""

    signal toggled(bool checked)

    readonly property bool darkTheme: palette.window.r * 0.299
                                    + palette.window.g * 0.587
                                    + palette.window.b * 0.114 < 0.5

    implicitWidth: 40
    implicitHeight: 20
    opacity: enabled ? 1.0 : 0.5
    activeFocusOnTab: interactive

    Rectangle {
        id: track

        anchors.fill: parent
        radius: height / 2
        color: control.checked
            ? (hover.hovered && control.interactive
                ? Qt.lighter(palette.highlight, 1.12)
                : palette.highlight)
            : (hover.hovered && control.interactive
                ? palette.mid
                : (control.darkTheme ? palette.button : palette.midlight))
        border.width: 1
        border.color: control.checked ? palette.highlight : palette.mid

        Behavior on color {
            ColorAnimation { duration: 120 }
        }
    }

    Rectangle {
        id: focusRing

        anchors.fill: track
        anchors.margins: -3
        radius: height / 2
        color: "transparent"
        border.width: 1
        border.color: palette.highlight
        visible: control.activeFocus
    }

    Rectangle {
        id: handle

        width: 14
        height: 14
        radius: width / 2
        y: (track.height - height) / 2
        x: control.checked ? track.width - width - 3 : 3
        color: control.checked
            ? palette.highlightedText : palette.windowText

        Behavior on x {
            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }

    HoverHandler {
        id: hover
        cursorShape: control.enabled
            ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    TapHandler {
        enabled: control.interactive && control.enabled
        onTapped: {
            control.forceActiveFocus()
            control.toggled(!control.checked)
        }
    }

    Keys.onPressed: (event) => {
        if (!control.interactive || !control.enabled)
            return
        if (event.key === Qt.Key_Space
                || event.key === Qt.Key_Return
                || event.key === Qt.Key_Enter) {
            control.toggled(!control.checked)
            event.accepted = true
        }
    }

    ToolTip.text: control.tooltip
    ToolTip.visible: hover.hovered && control.tooltip.length > 0
    ToolTip.delay: 600
}
