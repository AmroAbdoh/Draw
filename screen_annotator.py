#!/usr/bin/env python3
"""
Screen Annotator
=================
A floating toolbar + full-screen transparent overlay that lets you draw
directly on top of your desktop / any app - like Epic Pen / screen-annotation
tools.

Features (mapped to the toolbar buttons):
  - COLOR swatch  -> pick drawing color
  - Pencil        -> freehand draw anywhere on screen
  - Highlighter   -> thick, semi-transparent freehand stroke
  - Eraser        -> erase parts of your drawing
  - Select (arrow)-> click & drag an existing shape to move it
  - Text (T)      -> click and type text onto the screen
  - Pointer (+)   -> "normal cursor" mode - stop drawing and (on Windows)
                     let clicks pass through to whatever is underneath
  - Line          -> draw a straight line
  - Save (down arrow) -> export your drawing to a PNG
  - Undo / Redo   -> step backward / forward through your actions
  - Trash         -> clear everything
  - Exit          -> close the app
  - SIZE slider   -> controls brush / highlighter / eraser / text size

Requirements:
  - Python 3 with tkinter (included with most Python installs)
  - Optional but recommended: pynput (`pip install pynput`)
    Lets the overlay be 100% see-through (true transparent background)
    while drawing still works, by capturing clicks at the OS level
    instead of relying on the (click-blocking) transparent window itself.
    Without pynput, the app still runs, but falls back to a semi
    -transparent overlay instead of a fully invisible one.
  - Optional: Pillow (`pip install pillow`) for PNG export.
    Without Pillow, Save will still work but produces a .ps (PostScript) file.

Notes:
  - True see-through transparency + true click-through (Pointer tool) use
    Windows-only APIs. On other platforms the overlay still works for
    drawing, just without real desktop click-through in Pointer mode.

Run:
    python screen_annotator.py
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import ctypes

try:
    from pynput import keyboard as _pynput_keyboard, mouse as _pynput_mouse
    HAVE_PYNPUT = True
    PYNPUT_IMPORT_ERROR = None
except Exception as _e:
    HAVE_PYNPUT = False
    PYNPUT_IMPORT_ERROR = str(_e)


class ScreenAnnotator:
    # Plain text labels (not emoji/unicode glyphs) so they always render
    # correctly, laid out 2-per-row in the order requested:
    #   Pen | Highlight
    #   Eraser | Cursor
    #   Text | Move
    #   Line | Circle
    #   Undo | Redo
    #   Clear | Exit
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

    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()

        # ---- state ----
        self.tool = "pencil"
        self.color = "#ff2d55"
        self.size = 4

        self.history = []       # list of action dicts, for undo
        self.redo_stack = []    # list of action dicts, for redo

        self.current_item = None
        self.current_points = []
        self.start_x = self.start_y = 0

        self.selected_item = None
        self.selection_box = None
        self.selected_orig_coords = None
        self.drag_data = {"x": 0, "y": 0}

        self.tool_buttons = {}
        self._mouse_down = False
        self.mouse_listener = None
        self.keyboard_listener = None

        self._build_overlay()
        self._build_toolbar()
        self.set_tool(self.tool)

        if HAVE_PYNPUT:
            self._start_mouse_hook()

        # The overlay and the toolbar are both "always on top" windows, so
        # whichever one is clicked/drawn-on most recently can end up
        # stacking above the other, making the toolbar look unresponsive.
        # Keep re-asserting the toolbar above the overlay on a short timer.
        self._keep_toolbar_on_top()

        self._report_mode()

    def _report_mode(self):
        print(f"[screen_annotator] python executable: {sys.executable}")
        if HAVE_PYNPUT:
            print("[screen_annotator] mode: FULL TRANSPARENCY (pynput active)")
        else:
            print("[screen_annotator] mode: FALLBACK (pynput not active)")
            print(f"[screen_annotator] reason: {PYNPUT_IMPORT_ERROR}")
            print(f"[screen_annotator] fix: run this exact command, then restart the app:")
            print(f"    {sys.executable} -m pip install pynput")
            messagebox.showwarning(
                "Running in fallback mode",
                "pynput isn't active, so the overlay is using a semi-"
                "transparent fallback instead of true 100% transparency, "
                "and drawings will fade out in Cursor mode.\n\n"
                "To fix this, close the app and run this exact command "
                "(matching the Python that runs this script), then start "
                "the app again:\n\n"
                f"{sys.executable} -m pip install pynput\n\n"
                f"(reason pynput did not load: {PYNPUT_IMPORT_ERROR})",
            )

    # ------------------------------------------------------------------
    # Overlay (the full-screen drawing surface)
    # ------------------------------------------------------------------
    def _build_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)

        sw = self.overlay.winfo_screenwidth()
        sh = self.overlay.winfo_screenheight()
        self.overlay.geometry(f"{sw}x{sh}+0+0")

        self.DEFAULT_ALPHA = 0.55  # only used in the alpha fallback mode

        if HAVE_PYNPUT:
            # Full transparency mode: the background is genuinely invisible
            # via a Windows "color key". That normally also makes clicks on
            # the background pass straight through to the desktop (which is
            # what broke drawing before) - so here we DON'T rely on the
            # overlay to receive clicks at all. Instead a global mouse hook
            # (pynput) reports clicks regardless of which window "got" them,
            # and we draw from that. Actual drawn strokes use real colors,
            # so they stay fully visible and opaque.
            self.transparent_color = "#010101"
            self.overlay.config(bg=self.transparent_color)
            try:
                self.overlay.attributes("-transparentcolor", self.transparent_color)
            except tk.TclError:
                pass
            canvas_bg = self.transparent_color
        else:
            # Fallback mode (no pynput installed): a uniform window fade.
            # Not 100% invisible, but reliably clickable everywhere.
            self.transparent_color = "#141414"
            self.overlay.config(bg=self.transparent_color)
            try:
                self.overlay.attributes("-alpha", self.DEFAULT_ALPHA)
            except tk.TclError:
                pass
            canvas_bg = self.transparent_color

        self.canvas = tk.Canvas(
            self.overlay,
            bg=canvas_bg,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)

        if not HAVE_PYNPUT:
            # No global hook available - fall back to normal Tk bindings.
            self.canvas.bind("<ButtonPress-1>", lambda e: self.on_press(e.x, e.y))
            self.canvas.bind("<B1-Motion>", lambda e: self.on_drag(e.x, e.y))
            self.canvas.bind("<ButtonRelease-1>", lambda e: self.on_release(e.x, e.y))

        self.overlay.bind("<Control-z>", lambda e: self.undo())
        self.overlay.bind("<Control-y>", lambda e: self.redo())
        self.overlay.bind("<Escape>", lambda e: self.exit_app())

    # ------------------------------------------------------------------
    # Toolbar (small floating control panel)
    # ------------------------------------------------------------------
    def _build_toolbar(self):
        self.toolbar = tk.Toplevel(self.root)
        self.toolbar.overrideredirect(True)
        self.toolbar.attributes("-topmost", True)
        self.toolbar.geometry("+30+30")
        self.toolbar.config(bg="#1e1e1e")

        frame = tk.Frame(self.toolbar, bg="#1e1e1e", padx=10, pady=10)
        frame.pack()

        # drag handle
        handle = tk.Label(
            frame, text="\u2637 drag", bg="#1e1e1e", fg="#888888",
            cursor="fleur", font=("Segoe UI", 10),
        )
        handle.grid(row=0, column=0, sticky="w", pady=(0, 6))
        handle.bind("<ButtonPress-1>", self._start_move_toolbar)
        handle.bind("<B1-Motion>", self._do_move_toolbar)

        mode_text = "Full transparency" if HAVE_PYNPUT else "Fallback mode"
        mode_color = "#3ad46b" if HAVE_PYNPUT else "#e0a030"
        tk.Label(
            frame, text=mode_text, bg="#1e1e1e", fg=mode_color, font=("Segoe UI", 8)
        ).grid(row=0, column=1, sticky="e", pady=(0, 6))

        # color swatch
        self.color_btn = tk.Button(
            frame, bg=self.color, activebackground=self.color,
            width=14, height=2, relief="flat", command=self.choose_color,
        )
        self.color_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # tool buttons, 2 per row, bigger + plain text labels
        BTN_FONT = ("Segoe UI", 11, "bold")
        for idx, (label, name, tooltip) in enumerate(self.TOOLS_GRID):
            row = 2 + idx // 2
            col = idx % 2
            btn = tk.Button(
                frame, text=label, width=9, height=2, font=BTN_FONT,
                bg="#2b2b2b", fg="white", relief="raised",
                activebackground="#3a3a3a",
                command=self._make_tool_command(name),
            )
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            self.tool_buttons[name] = btn

        last_row = 2 + (len(self.TOOLS_GRID) - 1) // 2

        # Save is separate from the reordered drawing-tool grid above
        save_btn = tk.Button(
            frame, text="Save PNG", width=20, height=1, font=BTN_FONT,
            bg="#2b2b2b", fg="white", relief="raised",
            activebackground="#3a3a3a", command=self.save_image,
        )
        save_btn.grid(row=last_row + 1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        tk.Label(
            frame, text="SIZE", bg="#1e1e1e", fg="#3a7bd5", font=("Segoe UI", 11, "bold")
        ).grid(row=last_row + 2, column=0, columnspan=2, pady=(12, 0))
        self.size_slider = tk.Scale(
            frame, from_=1, to=50, orient="horizontal",
            command=self.set_size, bg="#1e1e1e", fg="white",
            highlightthickness=0, troughcolor="#3a3a3a", length=200,
        )
        self.size_slider.set(self.size)
        self.size_slider.grid(row=last_row + 3, column=0, columnspan=2, sticky="ew")

    def _start_move_toolbar(self, event):
        self._tb_offset = (event.x, event.y)

    def _do_move_toolbar(self, event):
        x = self.toolbar.winfo_pointerx() - self._tb_offset[0]
        y = self.toolbar.winfo_pointery() - self._tb_offset[1]
        self.toolbar.geometry(f"+{x}+{y}")

    def _keep_toolbar_on_top(self):
        try:
            self.toolbar.lift()
        except Exception:
            pass
        self.root.after(200, self._keep_toolbar_on_top)

    def _make_tool_command(self, name):
        if name in self.DRAWING_TOOLS:
            return lambda n=name: self.set_tool(n)
        return {
            "undo": self.undo,
            "redo": self.redo,
            "clear": self.clear_all,
            "save": self.save_image,
            "exit": self.exit_app,
        }[name]

    # ------------------------------------------------------------------
    # Tool selection
    # ------------------------------------------------------------------
    def set_tool(self, name):
        self.tool = name
        self.canvas.config(cursor=self.CURSOR_MAP.get(name, "arrow"))
        self._set_clickthrough(name == "pointer")
        self._highlight_active_tool()

    def _highlight_active_tool(self):
        for name, btn in self.tool_buttons.items():
            if name not in self.DRAWING_TOOLS:
                continue
            if name == self.tool:
                btn.config(relief="sunken", bg="#3a7bd5")
            else:
                btn.config(relief="raised", bg="#2b2b2b")

    def set_size(self, val):
        self.size = max(1, int(float(val)))

    def choose_color(self):
        rgb, hexcolor = colorchooser.askcolor(color=self.color, title="Choose color")
        if hexcolor:
            self.color = hexcolor
            self.color_btn.config(bg=hexcolor, activebackground=hexcolor)

    # ------------------------------------------------------------------
    # Windows-only real click-through for the "pointer / normal cursor" tool
    # ------------------------------------------------------------------
    def _get_root_hwnd(self, hwnd):
        try:
            GA_ROOT = 2
            return ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
        except Exception:
            return hwnd

    def _set_clickthrough(self, enable):
        # Pointer / "normal cursor" mode: let mouse clicks pass through to
        # whatever is beneath the overlay.
        if not HAVE_PYNPUT:
            # Fallback mode only: also fade the overlay almost fully away so
            # the desktop underneath is visible while in this mode.
            try:
                self.overlay.attributes("-alpha", 0.02 if enable else self.DEFAULT_ALPHA)
            except tk.TclError:
                pass

        if not IS_WINDOWS:
            return
        try:
            self.overlay.update_idletasks()
            hwnd = self._get_root_hwnd(self.overlay.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enable:
                style |= (WS_EX_LAYERED | WS_EX_TRANSPARENT)
            else:
                style |= WS_EX_LAYERED
                style &= ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Global mouse hook (used only when pynput is available) - this is
    # what lets drawing keep working even though the overlay's background
    # is a genuine (click-through) transparent color.
    # ------------------------------------------------------------------
    def _start_mouse_hook(self):
        blocked_mouse_messages = {
            0x0201, 0x0202,  # left button down/up
            0x0204, 0x0205,  # right button down/up
            0x0207, 0x0208,  # middle button down/up
            0x020B, 0x020C,  # X button down/up
            0x020A,          # mouse wheel
        }

        def win32_event_filter(msg, data):
            # In drawing modes, prevent mouse actions from reaching the
            # application below the transparent overlay. Keep toolbar clicks
            # and Cursor mode normal.
            if msg in blocked_mouse_messages and self.tool != "pointer":
                try:
                    in_toolbar = self._point_in_toolbar(data.pt.x, data.pt.y)
                except Exception:
                    in_toolbar = False
                if not in_toolbar:
                    # Suppression happens before pynput's normal click
                    # callback, so forward drawing clicks ourselves first.
                    if msg == 0x0201:
                        self.root.after(0, self._handle_hook_press, data.pt.x, data.pt.y)
                    elif msg == 0x0202:
                        self.root.after(0, self._handle_hook_release, data.pt.x, data.pt.y)
                    self.mouse_listener.suppress_event()

        def win32_keyboard_filter(msg, data):
            # Draw mode is intentionally keyboard-isolated as well, so typing
            # cannot affect the application underneath the overlay.
            if msg in (0x0100, 0x0101, 0x0104, 0x0105) and self.tool != "pointer":
                self.keyboard_listener.suppress_event()

        def on_click(x, y, button, pressed):
            if button != _pynput_mouse.Button.left:
                return
            if pressed:
                self.root.after(0, self._handle_hook_press, x, y)
            else:
                self.root.after(0, self._handle_hook_release, x, y)

        def on_move(x, y):
            if self._mouse_down:
                self.root.after(0, self._handle_hook_move, x, y)

        self.mouse_listener = _pynput_mouse.Listener(
            on_click=on_click,
            on_move=on_move,
            win32_event_filter=win32_event_filter if IS_WINDOWS else None,
        )
        self.mouse_listener.daemon = True
        self.mouse_listener.start()

        if IS_WINDOWS:
            self.keyboard_listener = _pynput_keyboard.Listener(
                win32_event_filter=win32_keyboard_filter,
            )
            self.keyboard_listener.daemon = True
            self.keyboard_listener.start()

    def _point_in_toolbar(self, x, y):
        try:
            tx = self.toolbar.winfo_rootx()
            ty = self.toolbar.winfo_rooty()
            tw = self.toolbar.winfo_width()
            th = self.toolbar.winfo_height()
            return tx <= x <= tx + tw and ty <= y <= ty + th
        except Exception:
            return False

    def _handle_hook_press(self, x, y):
        if self.tool == "pointer" or self._point_in_toolbar(x, y):
            return
        self._mouse_down = True
        self.on_press(x, y)

    def _handle_hook_move(self, x, y):
        if self.tool == "pointer" or not self._mouse_down:
            return
        self.on_drag(x, y)

    def _handle_hook_release(self, x, y):
        was_down = self._mouse_down
        self._mouse_down = False
        if self.tool == "pointer" or not was_down:
            return
        self.on_release(x, y)

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------
    def on_press(self, x, y):
        self.start_x, self.start_y = x, y
        self.drag_data = {"x": x, "y": y}

        if self.tool == "pencil":
            item = self.canvas.create_line(
                x, y, x, y, fill=self.color, width=self.size,
                capstyle="round", joinstyle="round", smooth=True,
            )
            self.current_points = [x, y]
            self.current_item = item

        elif self.tool == "highlighter":
            item = self.canvas.create_line(
                x, y, x, y, fill=self.color, width=self.size * 3,
                capstyle="round", joinstyle="round", smooth=True,
                stipple="gray50",
            )
            self.current_points = [x, y]
            self.current_item = item

        elif self.tool == "line":
            item = self.canvas.create_line(
                x, y, x, y, fill=self.color, width=self.size, capstyle="round",
            )
            self.current_item = item

        elif self.tool == "circle":
            item = self.canvas.create_oval(
                x, y, x, y, outline=self.color, width=self.size,
            )
            self.current_item = item

        elif self.tool == "eraser":
            self.erase_at(x, y)

        elif self.tool == "text":
            self.add_text(x, y)

        elif self.tool == "select":
            self.select_at(x, y)

    def on_drag(self, x, y):
        if self.tool in ("pencil", "highlighter") and self.current_item is not None:
            self.current_points.extend([x, y])
            self.canvas.coords(self.current_item, *self.current_points)

        elif self.tool in ("line", "circle") and self.current_item is not None:
            self.canvas.coords(self.current_item, self.start_x, self.start_y, x, y)

        elif self.tool == "eraser":
            self.erase_at(x, y)

        elif self.tool == "select" and self.selected_item is not None:
            dx = x - self.drag_data["x"]
            dy = y - self.drag_data["y"]
            self.canvas.move(self.selected_item, dx, dy)
            if self.selection_box is not None:
                self.canvas.move(self.selection_box, dx, dy)
            self.drag_data = {"x": x, "y": y}

    def on_release(self, x, y):
        if self.tool in ("pencil", "highlighter", "line", "circle") and self.current_item is not None:
            item = self.current_item
            self.current_item = None
            self.current_points = []
            # drop degenerate zero-length clicks
            coords = self.canvas.coords(item)
            if len(coords) < 4 or (coords[:2] == coords[-2:] and len(coords) == 4):
                if len(set(coords)) <= 2:
                    self.canvas.delete(item)
                    return
            action = {"kind": "existence", "item": item, "snapshot": self._snapshot(item)}
            self._push_history(action)

        elif self.tool == "select":
            if self.selection_box is not None:
                self.canvas.delete(self.selection_box)
                self.selection_box = None
            if self.selected_item is not None:
                new_coords = self.canvas.coords(self.selected_item)
                if new_coords != self.selected_orig_coords:
                    action = {
                        "kind": "move",
                        "item": self.selected_item,
                        "from": self.selected_orig_coords,
                        "to": new_coords,
                    }
                    self._push_history(action)
            self.selected_item = None
            self.selected_orig_coords = None

    # ------------------------------------------------------------------
    # Tool behaviours
    # ------------------------------------------------------------------
    def erase_at(self, x, y):
        r = max(14, self.size * 2)
        found = list(self.canvas.find_overlapping(x - r, y - r, x + r, y + r))
        if not found:
            # Nothing directly under the brush box - also grab the single
            # nearest item if it's within a slightly generous tolerance.
            # This makes it much easier to erase things with an odd or
            # thin bounding box, like a short line or a text label.
            found = list(self.canvas.find_closest(x, y, halo=r))
        for item in found:
            if "selection_box" in self.canvas.gettags(item):
                continue
            snapshot = self._snapshot(item)
            self.canvas.delete(item)
            action = {"kind": "existence", "item": None, "snapshot": snapshot}
            self._push_history(action)

    def add_text(self, x, y):
        entry = tk.Entry(self.overlay, font=("Arial", max(10, self.size * 3)))
        entry.place(x=x, y=y)
        entry.focus_set()

        def finish(event=None):
            text = entry.get()
            entry.destroy()
            if text:
                item = self.canvas.create_text(
                    x, y, text=text, fill=self.color,
                    font=("Arial", max(10, self.size * 3)), anchor="nw",
                )
                action = {"kind": "existence", "item": item, "snapshot": self._snapshot(item)}
                self._push_history(action)

        entry.bind("<Return>", finish)
        entry.bind("<Escape>", lambda e: entry.destroy())

    def select_at(self, x, y):
        found = [
            i for i in self.canvas.find_overlapping(x - 4, y - 4, x + 4, y + 4)
            if "selection_box" not in self.canvas.gettags(i)
        ]
        if not found:
            self.selected_item = None
            self.selected_orig_coords = None
            return
        item = found[-1]
        self.selected_item = item
        self.selected_orig_coords = self.canvas.coords(item)
        bbox = self.canvas.bbox(item)
        if bbox:
            pad = 4
            self.selection_box = self.canvas.create_rectangle(
                bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad,
                outline="#00aaff", dash=(4, 2), tags="selection_box",
            )

    # ------------------------------------------------------------------
    # Snapshot / recreate helpers (needed for undo/redo of add & erase)
    # ------------------------------------------------------------------
    def _snapshot(self, item):
        t = self.canvas.type(item)
        coords = self.canvas.coords(item)
        cfg = {}
        if t == "line":
            cfg = {
                "fill": self.canvas.itemcget(item, "fill"),
                "width": self.canvas.itemcget(item, "width"),
                "stipple": self.canvas.itemcget(item, "stipple"),
                "capstyle": self.canvas.itemcget(item, "capstyle"),
                "joinstyle": self.canvas.itemcget(item, "joinstyle"),
                "smooth": self.canvas.itemcget(item, "smooth"),
            }
        elif t == "text":
            cfg = {
                "fill": self.canvas.itemcget(item, "fill"),
                "text": self.canvas.itemcget(item, "text"),
                "font": self.canvas.itemcget(item, "font"),
                "anchor": self.canvas.itemcget(item, "anchor"),
            }
        elif t == "oval":
            cfg = {
                "outline": self.canvas.itemcget(item, "outline"),
                "width": self.canvas.itemcget(item, "width"),
                "fill": self.canvas.itemcget(item, "fill"),
            }
        return {"type": t, "coords": coords, "cfg": cfg}

    def _recreate(self, snap):
        t, coords, cfg = snap["type"], snap["coords"], snap["cfg"]
        if t == "line":
            return self.canvas.create_line(
                *coords, fill=cfg["fill"], width=cfg["width"], stipple=cfg["stipple"],
                capstyle=cfg["capstyle"], joinstyle=cfg["joinstyle"], smooth=cfg["smooth"],
            )
        elif t == "text":
            return self.canvas.create_text(
                *coords, fill=cfg["fill"], text=cfg["text"],
                font=cfg["font"], anchor=cfg.get("anchor", "nw"),
            )
        elif t == "oval":
            return self.canvas.create_oval(
                *coords, outline=cfg["outline"], width=cfg["width"], fill=cfg["fill"],
            )
        return None

    # ------------------------------------------------------------------
    # Undo / Redo / Clear
    # ------------------------------------------------------------------
    def _push_history(self, action):
        self.history.append(action)
        self.redo_stack.clear()

    def _toggle_existence(self, action):
        if action["item"] is not None:
            self.canvas.delete(action["item"])
            action["item"] = None
        else:
            action["item"] = self._recreate(action["snapshot"])

    def undo(self):
        if not self.history:
            return
        action = self.history.pop()
        kind = action["kind"]
        if kind == "existence":
            self._toggle_existence(action)
        elif kind == "move":
            self.canvas.coords(action["item"], *action["from"])
        elif kind == "clear":
            action["items"] = [self._recreate(s) for s in action["snapshots"]]
        self.redo_stack.append(action)

    def redo(self):
        if not self.redo_stack:
            return
        action = self.redo_stack.pop()
        kind = action["kind"]
        if kind == "existence":
            self._toggle_existence(action)
        elif kind == "move":
            self.canvas.coords(action["item"], *action["to"])
        elif kind == "clear":
            for i in action["items"]:
                self.canvas.delete(i)
            action["items"] = []
        self.history.append(action)

    def clear_all(self):
        items = [i for i in self.canvas.find_all() if "selection_box" not in self.canvas.gettags(i)]
        if not items:
            return
        snapshots = [self._snapshot(i) for i in items]
        for i in items:
            self.canvas.delete(i)
        action = {"kind": "clear", "snapshots": snapshots, "items": []}
        self._push_history(action)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def save_image(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("PostScript", "*.ps")],
        )
        if not path:
            return

        is_ps_request = path.lower().endswith(".ps")
        ps_path = path if is_ps_request else path + "._tmp.ps"
        self.canvas.postscript(file=ps_path, colormode="color")

        if is_ps_request:
            messagebox.showinfo("Saved", f"Saved to {ps_path}")
            return

        try:
            from PIL import Image
            img = Image.open(ps_path)
            img.save(path, "png")
            os.remove(ps_path)
            messagebox.showinfo("Saved", f"Saved to {path}")
        except ImportError:
            messagebox.showwarning(
                "Pillow not found",
                f"Saved raw PostScript to:\n{ps_path}\n\n"
                "Install Pillow (pip install pillow) to export directly to PNG.",
            )
        except Exception as e:
            messagebox.showerror("Error saving image", str(e))

    # ------------------------------------------------------------------
    def exit_app(self):
        if self.mouse_listener is not None:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass
        if self.keyboard_listener is not None:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass
        for w in (self.overlay, self.toolbar):
            try:
                w.destroy()
            except Exception:
                pass
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ScreenAnnotator()
    app.run()