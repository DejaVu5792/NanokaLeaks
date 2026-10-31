import QtQuick

// Full-window lightbox shell shared by the popups.
//
// The hosting widget only covers the central widget and paints nothing: the
// dimmed backdrop, the centred rounded panel, Escape and click-outside all
// live here.  The backdrop MouseArea sits under the panel, so panel content
// keeps every event it accepts and only the gaps fall through to it.
Item {
    id: overlay
    objectName: "overlayRoot"

    // Panel sizing, mirroring the values the widget overlay used.
    property real panelWidthRatio: 0.92
    property int minPanelWidth: 560
    property int maxPanelWidth: 1180
    property int hardMinPanelWidth: 300
    property real panelHeightRatio: 0.9
    property int minPanelHeight: 420
    property int maxPanelHeight: 880
    property int hardMinPanelHeight: 240
    property int edgeMargin: 24

    // Panel look; each popup themes the shell instead of painting its own.
    property color panelColor: palette.window
    property color panelBorderColor: palette.mid
    property int panelRadius: 8

    // The panel item itself cannot cross the PySide boundary (its C++ type is
    // not convertible), so the shell exposes its geometry as a plain rect.
    readonly property rect panelGeometry: Qt.rect(
        panel.x, panel.y, panel.width, panel.height
    )
    default property alias content: panelBody.data

    signal closeRequested()

    focus: true

    Keys.onEscapePressed: overlay.closeRequested()

    Rectangle {
        id: backdrop
        objectName: "overlayBackdrop"
        anchors.fill: parent
        color: "#a0000000"
    }

    // Catches everything the panel does not consume: it blocks input to the
    // window underneath and closes the popup when a press starts and ends on
    // the backdrop, like the widget overlay did.
    MouseArea {
        id: backdropArea
        objectName: "overlayBackdropArea"
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton

        property bool pressedOnBackdrop: false

        function overBackdrop(x, y) {
            const point = panel.mapFromItem(overlay, x, y)
            return point.x < 0 || point.y < 0
                || point.x >= panel.width || point.y >= panel.height
        }

        onPressed: (mouse) => {
            pressedOnBackdrop = overBackdrop(mouse.x, mouse.y)
        }
        onReleased: (mouse) => {
            if (pressedOnBackdrop && overBackdrop(mouse.x, mouse.y))
                overlay.closeRequested()
            pressedOnBackdrop = false
        }
        onCanceled: pressedOnBackdrop = false
    }

    Rectangle {
        id: panel
        objectName: "overlayPanel"
        anchors.centerIn: parent
        radius: overlay.panelRadius
        color: overlay.panelColor
        border.width: 1
        border.color: overlay.panelBorderColor
        clip: true

        width: Math.min(
            overlay.maxPanelWidth,
            Math.max(
                overlay.minPanelWidth,
                overlay.width * overlay.panelWidthRatio
            ),
            Math.max(
                overlay.hardMinPanelWidth,
                overlay.width - overlay.edgeMargin
            )
        )
        height: Math.min(
            overlay.maxPanelHeight,
            Math.max(
                overlay.minPanelHeight,
                overlay.height * overlay.panelHeightRatio
            ),
            Math.max(
                overlay.hardMinPanelHeight,
                overlay.height - overlay.edgeMargin
            )
        )

        Item {
            id: panelBody
            anchors.fill: parent
        }
    }
}
