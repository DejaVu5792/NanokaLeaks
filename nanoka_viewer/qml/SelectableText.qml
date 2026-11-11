import QtQuick
import QtQuick.Controls

// Read-only text that supports the usual mouse selection gestures.
//
// Labels and Text items cannot be selected.  TextEdit keeps the same styling
// and wrapping while providing double-click word selection, double-click-drag
// extension, and drag selection inside the details pane.
//
// Rule-term links (``term:<id>``) also behave like hyperlinks: the cursor
// becomes a pointing hand, a tooltip shows the term, and a click asks the
// details model to reveal that term in the Rule Terms card.
TextEdit {
    id: editor

    readonly property bool hoveringTerm:
        hoveredLink.length > 5 && hoveredLink.indexOf("term:") === 0

    readonly property string termTooltip: {
        if (!hoveringTerm || typeof details === "undefined")
            return ""
        return details.termTooltip(hoveredLink.substring(5))
    }

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

    ToolTip.delay: 350
    ToolTip.visible: editor.hoveringTerm && editor.termTooltip.length > 0
    ToolTip.text: editor.termTooltip

    HoverHandler {
        cursorShape: editor.hoveringTerm
                     ? Qt.PointingHandCursor : Qt.IBeamCursor
    }

    onLinkActivated: function(link) {
        if (link.indexOf("term:") !== 0 || typeof details === "undefined")
            return
        details.activateTerm(link.substring(5))
    }
}
