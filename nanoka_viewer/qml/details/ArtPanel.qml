import QtQuick
import QtQuick.Controls

import "../Theme.js" as Theme
import ".."

// The artwork column: cover-cropped art, a bottom gradient and the name/meta
// overlay.
//
// QML's Image.PreserveAspectCrop centres the crop, but character faces live at
// the top, so the image is sized to cover the frame and pinned to y: 0 instead
// (the same rule the widget _ArtLabel implemented).
//
// The artwork can be dragged and zoomed with the wheel.  Offsets are measured
// from the default cover crop: the horizontal focus is the detail centroid
// when Smart artwork centering is on, or the geometric centre when it is off
// (Python reports 0.5 for that case, so this file needs no extra flag).
Item {
    id: artPanel
    objectName: "detailsArtColumn"

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
        id: skeleton
        objectName: "detailArtSkeleton"
        anchors.fill: parent
        visible: details.artState === "skeleton"
        color: Theme.skeletonColor(palette)
        Accessible.name: "Loading character artwork"

        SkeletonPulse {
            target: skeleton
            active: skeleton.visible
        }
    }

    Item {
        id: artFrame
        objectName: "detailArtFrame"
        anchors.fill: parent
        visible: details.artState === "ready"
        clip: true
        Accessible.name: "Character artwork"

        // 1.0 is the cover crop; the extra zoom is for inspecting details.
        property real zoom: 1.0
        readonly property real maxZoom: 4.0

        Image {
            id: art
            objectName: "detailArt"
            source: details.artSource
            asynchronous: true
            smooth: true
            mipmap: true          // proper downscale filtering
            cache: false
            fillMode: Image.Stretch

            readonly property real coverScale: Math.max(
                artFrame.width / Math.max(1, implicitWidth),
                                                        artFrame.height / Math.max(1, implicitHeight))
            readonly property real baseWidth:
                Math.max(1, Math.round(implicitWidth * coverScale))
            readonly property real baseHeight:
                Math.max(1, Math.round(implicitHeight * coverScale))

            // The default crop, before any drag: centred on the detail
            // centroid and pinned to the top.  Clamp so the artwork never
            // reveals an edge.
            readonly property real defaultX: Math.min(0, Math.max(
                artFrame.width - baseWidth,
                artFrame.width / 2 - details.artFocusX * baseWidth))
            readonly property real defaultY: 0

            // Pan offset from the default crop, in frame pixels.  Dragging
            // updates it; the x/y bindings clamp it so no edge is exposed.
            property real offsetX: 0
            property real offsetY: 0

            // whole pixels so the texture isn't resampled at a half-pixel offset
            width: Math.round(baseWidth * artFrame.zoom)
            height: Math.round(baseHeight * artFrame.zoom)
            x: Math.round(Math.min(0, Math.max(
                artFrame.width - width, defaultX + offsetX)))
            y: Math.round(Math.min(0, Math.max(
                artFrame.height - height, defaultY + offsetY)))
            opacity: status === Image.Ready ? 1 : 0

            // Visible only while the artwork is not in its default position
            // (or scale).  Read x/y rather than the offsets so a clamp after a
            // resize does not keep the reset icon up for an unchanged crop.
            readonly property bool moved: artFrame.zoom > 1.001
                || Math.abs(x - defaultX) > 0.5
                || Math.abs(y - defaultY) > 0.5
            readonly property bool canPan: artFrame.zoom > 1.001
                || baseWidth > artFrame.width + 1
                || baseHeight > artFrame.height + 1

            function panTo(offset) {
                offsetX = clampOffsetX(offset.x)
                offsetY = clampOffsetY(offset.y)
            }

            function clampOffsetX(value) {
                return Math.min(-defaultX, Math.max(
                    artFrame.width - width - defaultX, value))
            }

            function clampOffsetY(value) {
                return Math.min(-defaultY, Math.max(
                    artFrame.height - height - defaultY, value))
            }

            // Zoom around *px*/*py* (frame coordinates) so the point under
            // the pointer stays put.
            function zoomAt(wanted, px, py) {
                var next = Math.min(artFrame.maxZoom, Math.max(1.0, wanted))
                if (Math.abs(next - artFrame.zoom) < 0.001)
                    return
                var fractionX = width > 0 ? (px - x) / width : 0.5
                var fractionY = height > 0 ? (py - y) / height : 0.5
                artFrame.zoom = next
                var nextWidth = Math.round(baseWidth * next)
                var nextHeight = Math.round(baseHeight * next)
                panTo(Qt.point(px - fractionX * nextWidth - defaultX,
                               py - fractionY * nextHeight - defaultY))
            }

            function resetView() {
                artFrame.zoom = 1.0
                offsetX = 0
                offsetY = 0
            }

            // The popup and its QML tree are reused for every character; a
            // new artwork must start from its own default crop, not keep the
            // previous one's zoom and pan.
            onSourceChanged: resetView()

            Behavior on opacity {
                NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
            }
        }

        MouseArea {
            id: artDrag
            objectName: "detailArtDrag"
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            preventStealing: true
            // QQuickWidget never shows QML cursors, so the widget-side tracker
            // (ui/qml_cursor.py) reads this binding and applies it instead.
            cursorShape: pressed
                ? Qt.ClosedHandCursor
                : (art.canPan ? Qt.OpenHandCursor : Qt.ArrowCursor)

            property real lastX: 0
            property real lastY: 0

            onPressed: (mouse) => {
                lastX = mouse.x
                lastY = mouse.y
            }
            onPositionChanged: (mouse) => {
                if (!pressed)
                    return
                // Start from the painted position, not the stored offset: a
                // clamp may have moved the art since the last drag.
                art.panTo(Qt.point(art.x - art.defaultX + mouse.x - lastX,
                                   art.y - art.defaultY + mouse.y - lastY))
                lastX = mouse.x
                lastY = mouse.y
            }
            onWheel: (wheel) => {
                if (wheel.angleDelta.y === 0)
                    return
                art.zoomAt(artFrame.zoom
                           * Math.pow(1.0015, wheel.angleDelta.y),
                           wheel.x, wheel.y)
                wheel.accepted = true
            }
        }

        // Reset floats over the artwork and only appears once the user has
        // moved or zoomed it; the page itself owns no other chrome here.
        AppButton {
            objectName: "detailArtReset"
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 8
            small: true
            square: true
            text: "\u21ba"
            visible: art.moved
            Accessible.name: "Reset artwork position"
            onClicked: art.resetView()
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

        SelectableText {
            objectName: "detailArtName"
            width: parent.width
            visible: details.artName.length > 0
            text: details.artName
            color: "#ffffff"
            font.pixelSize: 22
            font.bold: true
        }

        SelectableText {
            objectName: "detailArtMeta"
            width: parent.width
            visible: details.artMeta.length > 0
            text: details.artMeta
            color: Qt.rgba(1, 1, 1, 215 / 255)
            font.pixelSize: 11
        }
    }

    SelectableText {
        objectName: "detailArtMessage"
        anchors.centerIn: parent
        width: parent.width - 28
        visible: details.artState === "unavailable"
        text: details.artMessage
        color: palette.placeholderText
        font.pixelSize: 11
        horizontalAlignment: Text.AlignHCenter
    }
}
