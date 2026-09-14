"""Tkinter overlay and toolbar UI for the screen annotator."""

import os
import sys
import tkinter as tk
from tkinter import colorchooser

from PIL import Image, ImageOps, ImageTk


class AnnotatorUIMixin:
    TOOL_LABELS = {
        "pencil": "Pen", "highlighter": "Highlight", "eraser": "Eraser",
        "pointer": "Cursor", "rectangle": "Rectangle", "select": "Move",
        "circle": "Circle", "undo": "Undo", "redo": "Redo",
        "clear": "Clear", "hide": "Hide",
    }

    def _load_tool_icons(self):
        icon_dir = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(__file__)), "icons")
        icon_files = {
            "pencil": "pen.png",
            "highlighter": "highlighter.png",
            "eraser": "eraser.png",
            "pointer": "cursor.png",
            "rectangle": "rectangle.png",
            "select": "move.png",
            "circle": "circle.png",
            "undo": "undo.png",
            "redo": "undo.png",
            "clear": "clear.png",
            "hide": "hide.png",
            "line" : "line.png"
        }
        self.tool_icons = {}
        for name, filename in icon_files.items():
            path = os.path.join(icon_dir, filename)
            if not os.path.exists(path):
                continue
            try:
                # Load the icon exactly as it is on disk - no recoloring,
                # no alpha reconstruction. This is intentionally the
                # simplest possible path: resize it and use it as-is.
                # If the icon's own colors are hard to see against the
                # dark toolbar, that's a much easier follow-up fix than
                # the garbled/blank icons the recoloring code was causing.
                icon = Image.open(path).convert("RGBA")
                icon.thumbnail((20, 20), Image.Resampling.LANCZOS)
                if name == "redo":
                    icon = ImageOps.mirror(icon)
                self.tool_icons[name] = ImageTk.PhotoImage(icon)
            except Exception as e:
                print(f"[screen_annotator] could not load icon '{filename}': {e}")

    def _build_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)

        sw = self.overlay.winfo_screenwidth()
        sh = self.overlay.winfo_screenheight()
        self.overlay.geometry(f"{sw}x{sh}+0+0")

        self.DEFAULT_ALPHA = 0.55

        if self.HAVE_PYNPUT:
            self.transparent_color = "#010101"
            self.overlay.config(bg=self.transparent_color)
            try:
                self.overlay.attributes("-transparentcolor", self.transparent_color)
            except tk.TclError:
                pass
            canvas_bg = self.transparent_color
        else:
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

        if not self.HAVE_PYNPUT:
            self.canvas.bind("<ButtonPress-1>", lambda e: self.on_press(e.x, e.y))
            self.canvas.bind("<B1-Motion>", lambda e: self.on_drag(e.x, e.y))
            self.canvas.bind("<ButtonRelease-1>", lambda e: self.on_release(e.x, e.y))

        self.overlay.bind("<Control-z>", lambda e: self.undo())
        self.overlay.bind("<Control-y>", lambda e: self.redo())
        self.overlay.bind("<Escape>", lambda e: self.exit_app())

    def _build_toolbar(self):
        self.toolbar = tk.Toplevel(self.root)
        self.toolbar.overrideredirect(True)
        self.toolbar.attributes("-topmost", True)
        self.toolbar.geometry("+30+30")
        self.toolbar.config(bg="#1e1e1e")

        frame = tk.Frame(self.toolbar, bg="#1e1e1e", padx=8, pady=6)
        frame.pack()
        self._load_tool_icons()

        handle = tk.Label(
            frame, text="\u2637 drag", bg="#1e1e1e", fg="#888888",
            cursor="fleur", font=("Segoe UI", 9),
        )
        handle.grid(row=0, column=0, sticky="w", pady=(0, 3))
        handle.bind("<ButtonPress-1>", self._start_move_toolbar)
        handle.bind("<B1-Motion>", self._do_move_toolbar)

        mode_text = "Full transparency" if self.HAVE_PYNPUT else "Fallback mode"
        mode_color = "#3ad46b" if self.HAVE_PYNPUT else "#e0a030"
        self.color_btn = tk.Button(
            frame, bg=self.color, activebackground=self.color,
            width=3, height=1, relief="flat", bd=1, command=self.choose_color,
        )
        self.color_btn.grid(row=0, column=1, sticky="e", padx=(8, 0), pady=(0, 4))

        tk.Label(
            frame, text=mode_text, bg="#1e1e1e", fg=mode_color, font=("Segoe UI", 7)
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 3))

        btn_font = ("Segoe UI", 9, "bold")
        BTN_W, BTN_H = 100, 48  # fixed pixel size for every tool button
        for idx, (label, name, tooltip) in enumerate(self.TOOLS_GRID):
            row = 2 + idx // 2
            col = idx % 2
            icon = self.tool_icons.get(name)
            display_label = "" if icon else self.TOOL_LABELS.get(name, label)

            # A Button's width/height mean "characters" normally, but
            # silently switch to "pixels" the moment an image is attached -
            # even with compound="top". That mismatch is what made icon
            # buttons and text buttons come out different sizes. Wrapping
            # each button in a fixed-pixel holder frame sidesteps the whole
            # units problem and guarantees every button is identical.
            holder = tk.Frame(frame, width=BTN_W, height=BTN_H, bg="#1e1e1e")
            holder.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            holder.grid_propagate(False)

            btn = tk.Button(
                holder, text=display_label, font=btn_font,
                bg="#2b2b2b", fg="white", relief="raised",
                activebackground="#3a3a3a",
                image=icon, compound="none" if icon else "none",
                command=self._make_tool_command(name),
            )
            btn.pack(fill="both", expand=True)
            if icon:
                self._add_tooltip(btn, self.TOOL_LABELS.get(name, label))
            self.tool_buttons[name] = btn

        last_row = 2 + (len(self.TOOLS_GRID) - 1) // 2
        save_btn = tk.Button(
            frame, text="Save PNG", width=16, height=1, font=btn_font,
            bg="#2b2b2b", fg="white", relief="raised",
            activebackground="#3a3a3a", command=self.save_image,
        )
        save_btn.grid(row=last_row + 1, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        tk.Label(
            frame, text="SIZE", bg="#1e1e1e", fg="#3a7bd5", font=("Segoe UI", 9, "bold")
        ).grid(row=last_row + 2, column=0, columnspan=2, pady=(5, 0))
        self.size_slider = tk.Scale(
            frame, from_=1, to=50, orient="horizontal",
            command=self.set_size, bg="#1e1e1e", fg="white",
            highlightthickness=0, troughcolor="#3a3a3a", length=160,
        )
        self.size_slider.set(self.size)
        self.size_slider.grid(row=last_row + 3, column=0, columnspan=2, sticky="ew")

    def _add_tooltip(self, widget, text):
        widget.bind("<Enter>", lambda event: self._show_tooltip(widget, text))
        widget.bind("<Leave>", lambda event: self._hide_tooltip())

    def _show_tooltip(self, widget, text):
        self._hide_tooltip()
        self.tooltip = tk.Toplevel(widget)
        self.tooltip.overrideredirect(True)
        self.tooltip.attributes("-topmost", True)
        tk.Label(
            self.tooltip, text=text, bg="#111111", fg="white",
            padx=6, pady=3, font=("Segoe UI", 8),
        ).pack()
        x = widget.winfo_rootx() + widget.winfo_width() + 6
        y = widget.winfo_rooty()
        self.tooltip.geometry(f"+{x}+{y}")

    def _hide_tooltip(self):
        tooltip = getattr(self, "tooltip", None)
        if tooltip is not None:
            tooltip.destroy()
            self.tooltip = None

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
            "hide": self.hide_app,
        }[name]

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
        if hasattr(self, "settings_ready") and self.settings_ready:
            self.save_user_settings()

    def _adjust_size(self, direction):
        new_size = min(50, max(1, self.size + direction))
        self.size_slider.set(new_size)

    def choose_color(self):
        self._tool_before_color = self.tool
        self.set_tool("pointer")
        self._show_color_popup()

    def _show_color_popup(self):
        # Close any existing popup first
        existing = getattr(self, "_color_popup", None)
        if existing is not None:
            try:
                existing.destroy()
            except Exception:
                pass

        popup = tk.Toplevel(self.toolbar)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.config(bg="#1e1e1e")
        self._color_popup = popup

        x = self.color_btn.winfo_rootx() + self.color_btn.winfo_width() + 8
        y = self.color_btn.winfo_rooty()
        popup.geometry(f"+{x}+{y}")

        frame = tk.Frame(popup, bg="#1e1e1e", padx=8, pady=8,
                          highlightthickness=1, highlightbackground="#3a3a3a")
        frame.pack()

        tk.Label(frame, text="COLOR", bg="#1e1e1e", fg="#3a7bd5",
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))

        swatches = [
            "#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#00c7be",
            "#30b0ff", "#007aff", "#5856d6", "#af52de", "#ff2d55",
            "#ffffff", "#8e8e93", "#48484a", "#1c1c1e", "#000000",
        ]
        cols = 5
        for i, hexcolor in enumerate(swatches):
            r, c = i // cols, i % cols
            sw = tk.Button(
                frame, bg=hexcolor, activebackground=hexcolor,
                width=3, height=1, relief="flat", bd=0,
                highlightthickness=1, highlightbackground="#3a3a3a",
                command=lambda hc=hexcolor: self._apply_color(hc),
            )
            sw.grid(row=1 + r, column=c, padx=2, pady=2)

        hex_row = 1 + (len(swatches) + cols - 1) // cols
        tk.Label(frame, text="Hex:", bg="#1e1e1e", fg="white",
                 font=("Segoe UI", 8)).grid(row=hex_row, column=0, sticky="w", pady=(8, 0))

        hex_var = tk.StringVar(value=self.color)
        entry = tk.Entry(frame, textvariable=hex_var, width=10, bg="#2b2b2b",
                          fg="white", insertbackground="white", relief="flat")
        entry.grid(row=hex_row, column=1, columnspan=3, sticky="ew", pady=(8, 0))

        def apply_hex(event=None):
            val = hex_var.get().strip()
            if not val.startswith("#"):
                val = "#" + val
            try:
                popup.winfo_rgb(val)  # validates the color string
                self._apply_color(val)
            except tk.TclError:
                entry.config(bg="#4a2222")

        entry.bind("<Return>", apply_hex)
        tk.Button(frame, text="OK", font=("Segoe UI", 8), bg="#2b2b2b", fg="white",
                  relief="flat", command=apply_hex).grid(row=hex_row, column=4, sticky="ew", pady=(8, 0))

        popup.bind("<FocusOut>", lambda e: self._close_color_popup())
        popup.focus_set()

    def _apply_color(self, hexcolor):
        self.color = hexcolor
        self.color_btn.config(bg=hexcolor, activebackground=hexcolor)
        self.save_user_settings()
        self._close_color_popup()

    def _close_color_popup(self):
        popup = getattr(self, "_color_popup", None)
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass
            self._color_popup = None

        prev_tool = getattr(self, "_tool_before_color", None)
        if prev_tool is not None:
            self.set_tool(prev_tool)
            self._tool_before_color = None