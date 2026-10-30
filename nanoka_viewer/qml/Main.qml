import QtQuick
import QtQuick.Controls

// Entry point of the widget-hosted QML tree.
//
// The QMainWindow in nanoka_viewer/ui/main_window.py keeps the window chrome
// (title, icon, minimum size, close-time thread handling); this root item
// fills its central widget.  The placeholder below is replaced by the header,
// game sections and card grid as the migration lands each screen.
Rectangle {
    id: root
    objectName: "mainRoot"
    color: palette.window

    Label {
        objectName: "placeholderTitle"
        anchors.centerIn: parent
        text: "Nanoka Viewer"
        font.pixelSize: 22
        font.weight: Font.DemiBold
        color: palette.text
    }
}
