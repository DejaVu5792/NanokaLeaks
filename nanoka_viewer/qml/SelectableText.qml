import QtQuick

// Read-only text that supports the usual mouse selection gestures.
//
// Labels and Text items cannot be selected.  TextEdit keeps the same styling
// and wrapping while providing double-click word selection, double-click-drag
// extension, and drag selection inside the details pane.
TextEdit {
    id: text

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
}
