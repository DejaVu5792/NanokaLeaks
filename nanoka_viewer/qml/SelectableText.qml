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
// becomes a pointing hand, a card tooltip shows the term's name + description,
// and a click asks the details model to reveal that term in the Rule Terms card.
TextEdit {
    id: editor

    readonly property bool hoveringTerm:
        hoveredLink.length > 5 && hoveredLink.indexOf("term:") === 0

    readonly property string _hoveredTermId:
        editor.hoveringTerm ? hoveredLink.substring(5) : ""

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

    // -- hover delay timer ------------------------------------------------
    Timer {
        id: hoverTimer
        interval: 350
        repeat: false
        onTriggered: {
            if (editor.hoveringTerm)
                termCard.openFor(editor._hoveredTermId)
        }
    }

    onHoveredLinkChanged: {
        if (editor.hoveringTerm) {
            hoverTimer.restart()
        } else {
            hoverTimer.stop()
            termCard.close()
        }
    }

    // -- card-style term tooltip ------------------------------------------
    //
    // Using a Popup ensures the card renders at the window overlay layer and
    // therefore escapes any Flickable clip rectangle.
    //
    // Coordinate note: Popup.x/y are relative to the *parent item* (this
    // TextEdit).  Window-absolute coordinates come from mapToItem(null, …)
    // and are only used for the horizontal clamping calculation.
    Popup {
        id: termCard

        // Resolved data for the currently shown term.
        property string termId:   ""
        property string termName: ""
        property string termText: ""

        // Sizing: ~60 % of an approximate detail-pane column width.
        // Detail column is (windowWidth × 0.75) − 32 px; 60 % of that.
        readonly property int _cardW: {
            var winW = editor.Window.width || 800
            var approxCol = winW * 0.75 - 32
            return Math.max(160, Math.min(320, Math.round(approxCol * 0.60)))
        }

        // ---- reactive positioning (auto-corrects after first layout pass) ----

        // Map editor's top-left to window space for clamping.
        readonly property var _editorPos: editor.mapToItem(null, 0, 0)

        // Horizontal: centre popup over editor, clamped inside window.
        // Convert the resulting window-x back to editor-local by subtracting
        // the editor's own window x.
        x: {
            var winW   = editor.Window.width || 800
            var half   = termCard._cardW / 2
            var centre = _editorPos.x + editor.width / 2
            var winX   = Math.max(8, Math.min(centre - half, winW - termCard._cardW - 8))
            return winX - _editorPos.x
        }

        // Vertical: prefer above the editor, fall back to below.
        // Both values are in editor-local coordinates.
        y: {
            var popupH = cardRect.implicitHeight || 80   // 80 px fallback before layout
            var gap    = 8
            var spaceAbove = _editorPos.y - popupH - gap
            return spaceAbove >= 4
                ? -(popupH + gap)                // above editor's top edge
                :   editor.height + gap          // below editor's bottom edge
        }

        width:  _cardW
        height: cardRect.implicitHeight

        // Open for the given term id; just set data and let bindings handle position.
        function openFor(id) {
            if (typeof details === "undefined") return
            var name = details.termName(id)
            var text = details.termTooltip(id)
            if (name.length === 0 && text.length === 0) return
            termId   = id
            termName = name
            termText = text
            open()
        }

        // Raw popup chrome: none — card provides its own look.
        padding: 0
        background: null
        modal: false
        closePolicy: Popup.NoAutoClose
        dim: false

        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1
                              duration: 120; easing.type: Easing.OutCubic }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1; to: 0
                              duration: 80;  easing.type: Easing.InCubic }
        }

        // The styled card — mirrors DetailCard.qml at ~60 % scale.
        Rectangle {
            id: cardRect

            width:          termCard._cardW
            implicitHeight: innerCol.implicitHeight + 20
            radius: 8
            color:  palette.base
            border.width: 1
            border.color: palette.mid

            ColumnLayout {
                id: innerCol
                anchors.top:    parent.top
                anchors.left:   parent.left
                anchors.right:  parent.right
                anchors.margins: 10
                spacing: 4

                // Term name — bold title row.
                Text {
                    visible: termCard.termName.length > 0
                    Layout.fillWidth: true
                    text:  termCard.termName
                    color: palette.text
                    font.pixelSize: 13
                    font.bold: true
                    wrapMode: Text.Wrap
                }

                // Term description — rich text so markup is rendered.
                Text {
                    visible: termCard.termText.length > 0
                    Layout.fillWidth: true
                    text:  termCard.termText
                    textFormat: Text.RichText
                    color: palette.text
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                }
            }
        }
    }
}
