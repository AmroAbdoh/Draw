#!/usr/bin/env python3
"""Entry point for the screen annotation tool."""

import sys
import threading
import tkinter as tk
from tkinter import messagebox

from annotator_config import CURSOR_MAP, DRAWING_TOOLS, TOOLS_GRID
from annotator_drawing import AnnotatorDrawingMixin
from annotator_input import AnnotatorInputMixin
from annotator_settings import load_settings, save_settings
from annotator_tray import AnnotatorTrayMixin
from annotator_ui import AnnotatorUIMixin

IS_WINDOWS = sys.platform.startswith("win")

_pynput_keyboard = None
_pynput_mouse = None

try:
    from pynput import keyboard as _pynput_keyboard, mouse as _pynput_mouse
    HAVE_PYNPUT = True
    PYNPUT_IMPORT_ERROR = None
except Exception as error:
    HAVE_PYNPUT = False
    PYNPUT_IMPORT_ERROR = str(error)


class ScreenAnnotator(
    AnnotatorUIMixin,
    AnnotatorInputMixin,
    AnnotatorDrawingMixin,
    AnnotatorTrayMixin,
):
    """Coordinate application state across the UI, input, and drawing layers."""

    TOOLS_GRID = TOOLS_GRID
    DRAWING_TOOLS = DRAWING_TOOLS
    CURSOR_MAP = CURSOR_MAP
    IS_WINDOWS = IS_WINDOWS
    HAVE_PYNPUT = HAVE_PYNPUT
    _pynput_keyboard = _pynput_keyboard
    _pynput_mouse = _pynput_mouse

    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()

        settings = load_settings()
        self.tool = "pencil"
        self.color = settings["color"]
        self.size = settings["size"]
        self.settings_ready = False

        self.history = []
        self.redo_stack = []
        self.current_item = None
        self.current_points = []
        self.start_x = self.start_y = 0
        self.selected_item = None
        self.selection_box = None
        self.resize_handles = []
        self.resize_handle = None
        self.selected_orig_coords = None
        self.drag_data = {"x": 0, "y": 0}

        self.tool_buttons = {}
        self._mouse_down = False
        self._move_lock = threading.Lock()
        self._pending_move = None
        self._move_callback_pending = False
        self.mouse_listener = None
        self.keyboard_listener = None
        self.tray_icon = None

        self._build_overlay()
        self._build_toolbar()
        self.settings_ready = True
        self.set_tool(self.tool)

        if self.HAVE_PYNPUT:
            self._start_mouse_hook()
        self._keep_toolbar_on_top()
        self._report_mode()

    def save_user_settings(self):
        save_settings(self.color, self.size)

    def _report_mode(self):
        print(f"[screen_annotator] python executable: {sys.executable}")
        if self.HAVE_PYNPUT:
            print("[screen_annotator] mode: FULL TRANSPARENCY (pynput active)")
            return

        print("[screen_annotator] mode: FALLBACK (pynput not active)")
        print(f"[screen_annotator] reason: {PYNPUT_IMPORT_ERROR}")
        print("[screen_annotator] fix: run this exact command, then restart the app:")
        print(f"    {sys.executable} -m pip install pynput")
        messagebox.showwarning(
            "Running in fallback mode",
            "pynput isn't active, so the overlay is using a semi-transparent "
            "fallback instead of true 100% transparency, and drawings will "
            "fade out in Cursor mode.\n\n"
            "To fix this, close the app and run this exact command "
            "(matching the Python that runs this script), then start the app "
            f"again:\n\n{sys.executable} -m pip install pynput\n\n"
            f"(reason pynput did not load: {PYNPUT_IMPORT_ERROR})",
        )

    def exit_app(self):
        self.save_user_settings()
        self._stop_tray()
        for listener in (self.mouse_listener, self.keyboard_listener):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
        for window in (self.overlay, self.toolbar):
            try:
                window.destroy()
            except Exception:
                pass
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ScreenAnnotator().run()
