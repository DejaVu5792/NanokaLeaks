import QtQuick

// Read-only text that supports the usual mouse selection gestures.
//
// Labels and Text items cannot be selected.  TextEdit keeps the same styling
// and wrapping while providing double-click word selection, double-click-drag
// extension, and drag selection inside the details pane.
//
// Rule-term links (``term:<id>``) also behave like hyperlinks: the cursor
// becomes a pointing hand and hovering calls ``details.showTermHover()`` so
// the DetailsPanel can display a styled card.  Clicking asks the details model
// to reveal that term in the Rule Terms card.
TextEdit {
    id: editor

    readonly property bool hoveringTerm:
        hoveredLink.length > 5 && hoveredLink.indexOf("term:") === 0

    // Cursor position (editor-local) captured at the moment a term link is
    // entered.  Used by the timer so position is always from hover-entry, not
    // from an arbitrary future tick when the cursor may have moved away or
    // when hoverHandler.point has been reset by Qt.
    property real _hoverX: 0
    property real _hoverY: 0

    readOnly: true
    selectByMouse: true
    activeFocusOnPress: true
    cursorVisible: false
    wrapMode: TextEdit.Wrap
    textFormat: TextEdit.PlainText
    // Double-click selects a word; dragging after it extends word by word.
    mouseSelectionMode: TextEdit.SelectWords
    selectionColor: palette.highlight
    selectedTextColor: palette.highlightedText
    color: palette.text
    font.pixelSize: 12
    padding: 0
    textMargin: 0

    HoverHandler {
        id: hoverHandler
        cursorShape: editor.hoveringTerm
                     ? Qt.PointingHandCursor : Qt.IBeamCursor
    }

    onLinkActivated: function(link) {
        if (link.indexOf("term:") !== 0 || typeof details === "undefined")
            return
        details.activateTerm(link.substring(5))
    }

    // Hover delay timer — fires 350 ms after the cursor enters a term link.
    Timer {
        id: hoverTimer
        interval: 350
        repeat: false
        onTriggered: {
            if (!editor.hoveringTerm || typeof details === "undefined") return
            var termId = editor.hoveredLink.substring(5)
            // Use the position captured at hover-entry; fall back to the
            // current handler position and finally the item centre so a
            // stale/zero reading can never place the card off-screen.
            var hx = editor._hoverX > 0 ? editor._hoverX : hoverHandler.point.position.x
            var hy = editor._hoverY > 0 ? editor._hoverY : hoverHandler.point.position.y
            var mx = (hx >= 0 && hx <= editor.width) ? hx : (editor.width / 2)
            var my = (hy >= 0 && hy <= editor.height) ? hy : (editor.height / 2)
            var pt = editor.mapToItem(null, mx, my)
            details.showTermHover(termId, pt.x, pt.y)
        }
    }

    onHoveredLinkChanged: {
        if (editor.hoveringTerm) {
            // Snapshot the cursor position now, while hoverHandler.point is fresh.
            editor._hoverX = hoverHandler.point.position.x
            editor._hoverY = hoverHandler.point.position.y
            hoverTimer.restart()
        } else {
            editor._hoverX = 0
            editor._hoverY = 0
            hoverTimer.stop()
            if (typeof details !== "undefined")
                details.hideTermHover()
        }
    }
}
