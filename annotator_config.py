"""Shared configuration for the screen annotator."""

TOOLS_GRID = [
    ("Pen", "pencil", "Pencil"),
    ("Highlight", "highlighter", "Highlighter"),
    ("Eraser", "eraser", "Eraser"),
    ("Cursor", "pointer", "Normal cursor (no drawing)"),
    ("Rectangle", "rectangle", "Draw a rectangle"),
    ("Move", "select", "Select / move a drawing"),
    ("Line", "line", "Straight line"),
    ("Circle", "circle", "Circle / ellipse"),
    ("Undo", "undo", "Undo"),
    ("Redo", "redo", "Redo"),
    ("Clear", "clear", "Clear everything"),
    ("Hide", "hide", "Hide to the notification area"),
]

DRAWING_TOOLS = {
    "pencil", "highlighter", "eraser", "select", "pointer",
    "line", "circle", "rectangle",
}

CURSOR_MAP = {
    "pencil": "crosshair",
    "highlighter": "crosshair",
    "eraser": "circle",
    "select": "hand2",
    "rectangle": "crosshair",
    "pointer": "arrow",
    "line": "crosshair",
    "circle": "crosshair",
}