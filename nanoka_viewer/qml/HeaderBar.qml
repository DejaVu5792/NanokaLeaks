import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Window header: title, background cache progress, load status and the two
// global actions.  All text/enabled state is driven by NanokaViewer's
// properties so the state machine stays in Python.
RowLayout {
    id: header
    spacing: 8

    Label {
        objectName: "titleLabel"
        text: "Nanoka Viewer"
        color: palette.windowText
        font.pixelSize: 22
        font.weight: Font.DemiBold
    }

    Item { Layout.fillWidth: true }

    Label {
        objectName: "cacheLabel"
        text: viewer.cacheText
        visible: text.length > 0
        color: palette.placeholderText
        font.pixelSize: 12
        elide: Text.ElideRight
        Layout.maximumWidth: 360
    }

    Label {
        objectName: "statusLabel"
        text: viewer.statusText
        color: palette.placeholderText
        font.pixelSize: 12
    }

    AppButton {
        objectName: "settingsButton"
        text: "Settings"
        onClicked: viewer.openSettings()
    }

    AppButton {
        objectName: "reloadButton"
        text: viewer.reloadText
        enabled: viewer.reloadEnabled
        onClicked: viewer.reload()
    }
}
