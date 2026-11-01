import QtQuick

import ".."

// Settings popup: the shared overlay shell around the settings panel.
Overlay {
    objectName: "settingsOverlay"

    SettingsPanel {
        anchors.fill: parent
    }
}
