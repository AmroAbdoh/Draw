"""Tkinter overlay and toolbar UI for the screen annotator."""

import tkinter as tk
from tkinter import colorchooser


class AnnotatorUIMixin:
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

        frame = tk.Frame(self.toolbar, bg="#1e1e1e", padx=10, pady=10)
        frame.pack()

        handle = tk.Label(
            frame, text="\u2637 drag", bg="#1e1e1e", fg="#888888",
            cursor="fleur", font=("Segoe UI", 10),
        )
        handle.grid(row=0, column=0, sticky="w", pady=(0, 6))
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
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        btn_font = ("Segoe UI", 11, "bold")
        for idx, (label, name, tooltip) in enumerate(self.TOOLS_GRID):
            row = 2 + idx // 2
            col = idx % 2
            btn = tk.Button(
                frame, text=label, width=9, height=2, font=btn_font,
                bg="#2b2b2b", fg="white", relief="raised",
                activebackground="#3a3a3a",
                command=self._make_tool_command(name),
            )
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            self.tool_buttons[name] = btn

        last_row = 2 + (len(self.TOOLS_GRID) - 1) // 2
        save_btn = tk.Button(
            frame, text="Save PNG", width=20, height=1, font=btn_font,
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
        rgb, hexcolor = colorchooser.askcolor(color=self.color, title="Choose color")
        if hexcolor:
            self.color = hexcolor
            self.color_btn.config(bg=hexcolor, activebackground=hexcolor)
            self.save_user_settings()