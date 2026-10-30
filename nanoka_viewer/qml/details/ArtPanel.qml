import QtQuick
import QtQuick.Controls

// The artwork column: cover-cropped art, a bottom gradient and the name/meta
// overlay.
//
// QML's Image.PreserveAspectCrop centres the crop, but character faces live at
// the top, so the image is sized to cover the frame and pinned to y: 0 instead
// (the same rule the widget _ArtLabel implemented).
Item {
    id: artPanel
    objectName: "detailsArtColumn"

    // Same 50/50 Midlight/Mid blend the widget skeleton used.
    readonly property color skeletonColor: Qt.rgba(
        (palette.midlight.r + palette.mid.r) / 2,
        (palette.midlight.g + palette.mid.g) / 2,
        (palette.midlight.b + palette.mid.b) / 2,
        1)

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: palette.alternateBase
    }

    // The header sits directly above: keep the top corners square so the
    // rounded corners only show where they meet the panel edge.
    Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 10
        color: palette.alternateBase
    }

    Rectangle {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: 1
        color: palette.mid
    }

    // Loading placeholder: the whole column pulses.
    Rectangle {
        objectName: "detailArtSkeleton"
        anchors.fill: parent
        visible: details.artState === "skeleton"
        color: artPanel.skeletonColor
        Accessible.name: "Loading character artwork"

        SequentialAnimation on opacity {
            running: true
            loops: Animation.Infinite
            NumberAnimation {
                from: 0.55
                to: 0.95
                duration: 900
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                from: 0.95
                to: 0.55
                duration: 900
                easing.type: Easing.InOutSine
            }
        }
    }

    Item {
        id: artFrame
        anchors.fill: parent
        visible: details.artState === "ready"
        clip: true
        Accessible.name: "Character artwork"

        Image {
            id: art
            objectName: "detailArt"
            source: details.artSource
            asynchronous: true
            smooth: true
            cache: false
            fillMode: Image.Stretch

            readonly property real coverScale: Math.max(
                artFrame.width / Math.max(1, implicitWidth),
                artFrame.height / Math.max(1, implicitHeight))

            width: implicitWidth * coverScale
            height: implicitHeight * coverScale
            x: (artFrame.width - width) / 2
            y: 0
            opacity: status === Image.Ready ? 1 : 0

            Behavior on opacity {
                NumberAnimation {
                    duration: 180
                    easing.type: Easing.OutCubic
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: details.artState === "ready"
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.6; color: "transparent" }
            GradientStop { position: 0.78; color: Qt.rgba(0, 0, 0, 60 / 255) }
            GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 150 / 255) }
        }
    }

    Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 14
        spacing: 5
        visible: details.artState === "ready" || details.artState === "unavailable"

        Label {
            objectName: "detailArtName"
            width: parent.width
            visible: details.artName.length > 0
            text: details.artName
            color: "#ffffff"
            font.pixelSize: 22
            font.bold: true
            wrapMode: Text.WordWrap
        }

        Label {
            objectName: "detailArtMeta"
            width: parent.width
            visible: details.artMeta.length > 0
            text: details.artMeta
            color: Qt.rgba(1, 1, 1, 215 / 255)
            font.pixelSize: 11
            wrapMode: Text.WordWrap
        }
    }

    Label {
        objectName: "detailArtMessage"
        anchors.centerIn: parent
        visible: details.artState === "unavailable"
        text: details.artMessage
        color: palette.placeholderText
        font.pixelSize: 11
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }
}
