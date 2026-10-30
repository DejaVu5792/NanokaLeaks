pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

// Root of the widget-hosted QML tree.
//
// ``viewer`` (the NanokaViewer window) and ``sections`` (SectionsModel) are
// context properties installed by nanoka_viewer/ui/qml_host.py before this
// tree is parsed; the bindings below are evaluated during loading, so both
// must exist by then.
Rectangle {
    id: root
    objectName: "mainRoot"
    color: palette.window

    HeaderBar {
        id: header
        objectName: "headerBar"
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 12
        anchors.bottomMargin: 0
    }

    ListView {
        id: sectionList
        objectName: "sectionList"
        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.topMargin: 8
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.bottomMargin: 12
        clip: true
        spacing: 0
        boundsBehavior: Flickable.StopAtBounds
        model: sections

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            contentItem: Rectangle {
                implicitWidth: 6
                radius: 3
                color: palette.mid
            }
            background: Rectangle { color: "transparent" }
        }

        delegate: Column {
            id: sectionRow
            required property int index
            required property var section

            width: sectionList.width

            GameSection {
                width: sectionRow.width
                section: sectionRow.section
            }

            Rectangle {
                width: sectionRow.width
                height: visible ? 1 : 0
                visible: sectionRow.index < sectionList.count - 1
                color: palette.mid
            }
        }
    }

    // Mirrors the widget version: an empty window explains itself instead of
    // showing nothing at all.
    Label {
        objectName: "emptyHint"
        anchors.centerIn: sectionList
        visible: sectionList.count === 0
        text: viewer.statusText
        color: palette.placeholderText
        font.pixelSize: 13
    }
}
