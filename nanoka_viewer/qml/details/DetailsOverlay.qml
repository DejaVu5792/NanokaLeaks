import QtQuick

import ".."

// Character-details popup: the shared overlay shell around the details panel.
Overlay {
    id: detailsOverlay
    objectName: "detailsOverlay"

    panelColor: palette.base
    panelRadius: 10

    DetailsPanel {
        anchors.fill: parent
        cornerRadius: detailsOverlay.panelRadius
    }
}
