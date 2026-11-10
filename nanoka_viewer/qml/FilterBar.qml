pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

// One game's filter bar: [E|W  *  icon icon ...].
//
// ``filters`` is the section's FilterModel.  The ``*`` button is highlighted
// when every category is enabled and dimmed otherwise; clicking it enables
// everything first (from a partial selection) and only then disables all.
// Category icons use the same artwork as the character cards.
Row {
    id: bar

    required property var filters

    objectName: "filterBar"
    spacing: 4

    FilterToggle {
        anchors.verticalCenter: parent.verticalCenter
        filters: bar.filters
    }

    Item {
        id: selectAll

        anchors.verticalCenter: parent.verticalCenter
        width: 22
        height: 22

        readonly property bool active: bar.filters.allEnabled

        Rectangle {
            anchors.fill: parent
            radius: 4
            color: selectAll.active ? palette.highlight : palette.button
            border.width: 1
            border.color: selectAll.active ? palette.highlight : palette.mid
        }

        Text {
            anchors.centerIn: parent
            text: "*"
            color: selectAll.active
                ? palette.highlightedText : palette.placeholderText
            font.pixelSize: 16
            font.bold: true
        }

        MouseArea {
            objectName: "filterSelectAll"
            anchors.fill: parent
            onClicked: bar.filters.toggleAll()

            ToolTip.text: selectAll.active
                ? "Disable every filter"
                : "Enable every filter"
            ToolTip.visible: containsMouse
            ToolTip.delay: 600
        }
    }

    Repeater {
        model: bar.filters

        delegate: Item {
            id: category

            required property var model

            anchors.verticalCenter: parent.verticalCenter
            width: 22
            height: 22
            opacity: category.model.enabled ? 1.0 : 0.35

            IconBadge {
                anchors.centerIn: parent
                source: category.model.icon
                fallbackText: category.model.label.length > 0
                    ? category.model.label.charAt(0) : "?"
                tooltip: category.model.label
                size: 20
            }

            MouseArea {
                objectName: "filterCategory-" + category.model.key
                anchors.fill: parent
                onClicked: bar.filters.toggle(category.model.key)
            }
        }
    }
}
