import QtQuick

// Version badge next to a game title ("Live v1.2", "Beta v1.3").
//
// The tints are brighter on dark themes so they stay readable against the
// section header, exactly like the widget implementation.
Rectangle {
    id: badge

    property string text: ""
    property bool live: true

    readonly property bool darkTheme: palette.window.r * 0.299
                                    + palette.window.g * 0.587
                                    + palette.window.b * 0.114 < 0.5

    implicitWidth: label.implicitWidth + 12
    implicitHeight: label.implicitHeight + 4
    radius: 4
    border.width: 1

    color: live
        ? (darkTheme ? Qt.rgba(76 / 255, 175 / 255, 80 / 255, 0.15)
                     : Qt.rgba(46 / 255, 125 / 255, 50 / 255, 0.10))
        : (darkTheme ? Qt.rgba(255 / 255, 152 / 255, 0 / 255, 0.15)
                     : Qt.rgba(216 / 255, 67 / 255, 21 / 255, 0.08))

    border.color: live
        ? (darkTheme ? Qt.rgba(76 / 255, 175 / 255, 80 / 255, 0.30)
                     : Qt.rgba(46 / 255, 125 / 255, 50 / 255, 0.20))
        : (darkTheme ? Qt.rgba(255 / 255, 152 / 255, 0 / 255, 0.30)
                     : Qt.rgba(216 / 255, 67 / 255, 21 / 255, 0.20))

    Text {
        id: label
        anchors.centerIn: parent
        text: badge.text
        font.pixelSize: 10
        font.bold: true
        color: badge.live
            ? (badge.darkTheme ? "#4CAF50" : "#2E7D32")
            : (badge.darkTheme ? "#FF9800" : "#D84315")
    }
}
