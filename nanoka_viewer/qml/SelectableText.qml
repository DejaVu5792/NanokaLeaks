import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Read-only text that supports the usual mouse selection gestures.
//
// Labels and Text items cannot be selected.  TextEdit keeps the same styling
// and wrapping while providing double-click word selection, double-click-drag
// extension, and drag selection inside the details pane.
//
// Rule-term links (``term:<id>``) also behave like hyperlinks: the cursor
// becomes a pointing hand, a styled card tooltip shows the term's name and
// description after a short delay, and clicking asks the details model to
// reveal that term in the Rule Terms card.
TextEdit {
    id: editor

    readonly property bool hoveringTerm:
        hoveredLink.length > 5 && hoveredLink.indexOf("term:") === 0

    // Cursor position (editor-local) captured when the pointer enters a term
    // link.  The tooltip anchors to this point rather than to the whole TextEdit.
    property real _hoverX: 0
    property real _hoverY: 0

    onHoveringTermChanged: {
        if (!hoveringTerm)
            return
        var point = hoverHandler.point.position
        _hoverX = point.x
        _hoverY = point.y
    }

    // The details scroll pane actually on screen.  Walking the visual parent
    // chain keeps the tooltip width tied to the pane instead of guessing from
    // the window width (the artwork column and margins skew that estimate).
    readonly property Item _detailsPane: {
        var item = editor.parent
        while (item) {
            if (item.objectName === "detailsScroll")
                return item
            item = item.parent
        }
        return null
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

    // Styled card tooltip for rule-term links.
    //
    // ToolTip is a Popup: it renders at the window overlay layer and
    // therefore escapes any Flickable clip rectangle.  The built-in
    // delay/visible binding replaces an explicit Timer.
    ToolTip {
        id: termTip
        objectName: "termTooltip"

        // Resolved data for the currently hovered term.
        readonly property string _termId:
            editor.hoveringTerm ? editor.hoveredLink.substring(5) : ""
        readonly property string _termName:
            (_termId.length > 0 && typeof details !== "undefined")
                ? details.termName(_termId) : ""
        readonly property string _termBody:
            (_termId.length > 0 && typeof details !== "undefined")
                ? details.termTooltip(_termId) : ""

        visible: editor.hoveringTerm
                 && (_termName.length > 0 || _termBody.length > 0)
        delay: 350

        // The card always takes 60 % of the actual details pane width, so the
        // same term looks identical on every card and every window size.  The
        // popup width includes the card padding; the content item below takes
        // what remains.
        readonly property real _paneWidth:
            editor._detailsPane ? editor._detailsPane.width : editor.width
        readonly property int _popupW:
            Math.max(160, Math.round(_paneWidth * 0.60))
        readonly property int _contentW:
            Math.max(120, _popupW - leftPadding - rightPadding)

        width: _popupW

        // Anchor the popup to the captured pointer, not to the whole TextEdit.
        // x/y are editor-local (the popup's parent).  y is intentionally
        // unclamped: the card may extend above the text item (and even above
        // the pane) to stay next to the cursor instead of covering the text
        // under it.
        //
        // The offset to the pane is summed from the ancestor positions rather
        // than cached from mapToItem(): mapToItem() results are not reactive,
        // so a binding around it freezes the offset from the first layout pass
        // (before the detail cards have settled) and the clamp drifts by the
        // card margin.  Reading every ancestor's x/y makes the binding update
        // with layout and scrolling.
        readonly property point _paneOrigin: {
            var pane = editor._detailsPane
            if (!pane)
                return Qt.point(0, 0)
            var item = editor
            var x = 0
            var y = 0
            while (item && item !== pane) {
                x += item.x
                y += item.y
                item = item.parent
            }
            return Qt.point(x, y)
        }
        readonly property point _paneCursor:
            Qt.point(_paneOrigin.x + editor._hoverX,
                     _paneOrigin.y + editor._hoverY)
        readonly property real _paneLeft:
            Math.max(8, Math.min(_paneWidth - _popupW - 8,
                                 _paneCursor.x - _popupW / 2))
        x: Math.round(_paneLeft - _paneOrigin.x)
        y: Math.round(editor._hoverY - height - 12)

        // Replace the default plain background with a styled card.
        contentItem: ColumnLayout {
            id: tipLayout
            objectName: "termTooltipCard"
            implicitWidth: termTip._contentW
            width: termTip._contentW
            spacing: 6

            Text {
                visible: termTip._termName.length > 0
                Layout.fillWidth: true
                text: termTip._termName
                color: palette.text
                font.pixelSize: 13
                font.bold: true
                wrapMode: Text.Wrap
            }

            Text {
                visible: termTip._termBody.length > 0
                Layout.fillWidth: true
                text: termTip._termBody
                textFormat: Text.RichText
                color: palette.text
                font.pixelSize: 12
                wrapMode: Text.Wrap
            }
        }

        background: Rectangle {
            radius: 8
            color: palette.base
            border.width: 1
            border.color: palette.mid
        }

        // Comfortable card padding.
        leftPadding: 10
        rightPadding: 10
        topPadding: 10
        bottomPadding: 10
    }
}
