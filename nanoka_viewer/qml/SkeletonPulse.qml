import QtQuick

// The 0.55 <-> 0.95 opacity pulse shared by every loading placeholder.
//
// ``target`` and ``targetProperty`` let one implementation drive either an
// item's opacity (artwork/skeleton pages) or a custom ``pulse`` property that
// the skeleton bars multiply into their colour.  Callers pass ``active`` so a
// hidden page does not keep an infinite animation running.
SequentialAnimation {
    id: animation

    property Item target: null
    property string targetProperty: "opacity"
    property bool active: true

    running: active && target !== null
    loops: Animation.Infinite

    NumberAnimation {
        target: animation.target
        property: animation.targetProperty
        from: 0.55
        to: 0.95
        duration: 900
        easing.type: Easing.InOutSine
    }

    NumberAnimation {
        target: animation.target
        property: animation.targetProperty
        from: 0.95
        to: 0.55
        duration: 900
        easing.type: Easing.InOutSine
    }
}
