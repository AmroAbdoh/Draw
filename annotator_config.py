"""Shared configuration for the screen annotator."""

TOOLS_GRID = [
    ("Pen", "pencil", "Pencil"),
    ("Highlight", "highlighter", "Highlighter"),
    ("Eraser", "eraser", "Eraser"),
    ("Cursor", "pointer", "Normal cursor (no drawing)"),
    ("Text", "text", "Add text"),
    ("Move", "select", "Select / move a drawing"),
    ("Line", "line", "Straight line"),
    ("Circle", "circle", "Circle / ellipse"),
    ("Undo", "undo", "Undo"),
    ("Redo", "redo", "Redo"),
    ("Clear", "clear", "Clear everything"),
    ("Exit", "exit", "Close the app"),
]

DRAWING_TOOLS = {
    "pencil", "highlighter", "eraser", "select", "text", "pointer",
    "line", "circle",
}

CURSOR_MAP = {
    "pencil": "crosshair",
    "highlighter": "crosshair",
    "eraser": "circle",
    "select": "hand2",
    "text": "xterm",
    "pointer": "arrow",
    "line": "crosshair",
    "circle": "crosshair",
}