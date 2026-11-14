pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

// One game's filter bar: [E|W | * icon icon ...] in a single rounded bar.
//
// ``filters`` is the section's FilterModel.  The ``*`` button is highlighted
// when every category is enabled and dimmed otherwise; clicking it enables
// everything first (from a partial selection) and only then disables all.
// Category icons use the same artwork as the character cards.
Rectangle {
    id: bar

    required property var filters

    objectName: "filterBar"
    implicitWidth: content.implicitWidth + 6
    implicitHeight: 24
    radius: 5
    color: palette.button
    border.width: 1
    border.color: palette.mid

    Row {
        id: content
        anchors.centerIn: parent
        spacing: 0

        FilterToggle {
            filters: bar.filters
        }

        Item {
            width: 1
            height: 22

            Rectangle {
                anchors.centerIn: parent
                width: 1
                height: 14
                color: palette.mid
            }
        }

        Item {
            width: 6
            height: 1
        }

        Item {
            id: selectAll

            width: 24
            height: 22

            readonly property bool active: bar.filters.allEnabled

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: 4
                color: selectAll.active
                    ? palette.highlight
                    : (selectAllHover.hovered
                        ? palette.alternateBase : "transparent")
            }

            Text {
                anchors.centerIn: parent
                // The asterisk glyph sits near the top of its line box.
                anchors.verticalCenterOffset: 3
                text: "*"
                color: selectAll.active
                    ? palette.highlightedText : palette.placeholderText
                font.pixelSize: 16
                font.bold: true
            }

            HoverHandler { id: selectAllHover }

            MouseArea {
                objectName: "filterSelectAll"
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: bar.filters.toggleAll()

                ToolTip.text: selectAll.active
                    ? "Disable every filter"
                    : "Enable every filter"
                ToolTip.visible: containsMouse
                ToolTip.delay: 600
            }
        }

        Item {
            width: 3
            height: 1
        }

        Row {
            id: categoryRow
            spacing: 3

            Repeater {
                model: bar.filters

                delegate: Item {
                    id: category

                    required property var model

                    width: 22
                    height: 22
                    opacity: category.model.enabled ? 1.0 : 0.35

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: 4
                        color: category.model.enabled && !bar.filters.allEnabled
                            ? palette.highlight
                            : (categoryHover.hovered
                                ? palette.alternateBase : "transparent")
                    }

                    IconBadge {
                        anchors.centerIn: parent
                        source: category.model.icon
                        fallbackText: category.model.label.length > 0
                            ? category.model.label.charAt(0) : "?"
                        tooltip: category.model.label
                        size: 18
                    }

                    HoverHandler { id: categoryHover }

                    MouseArea {
                        objectName: "filterCategory-" + category.model.key
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: bar.filters.toggle(category.model.key)
                    }
                }
            }
        }
    }
}
