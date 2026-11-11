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

        // Sizing: ~60 % of an approximate detail-pane column width.
        // Detail column is (windowWidth × 0.75) − 32 px; 60 % of that.
        readonly property int _cardW: {
            var winW = editor.Window.width || 800
            var approxCol = winW * 0.75 - 32
            return Math.max(200, Math.min(380, Math.round(approxCol * 0.60)))
        }

        // Replace the default plain background with a styled card.
        contentItem: ColumnLayout {
            id: tipLayout
            width: termTip._cardW
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
