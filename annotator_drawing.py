"""Drawing tools, selection, history, and image export."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox


class AnnotatorDrawingMixin:
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
            self.current_item = self.canvas.create_line(
                x, y, x, y, fill=self.color, width=self.size, capstyle="round",
            )

        elif self.tool == "circle":
            self.current_item = self.canvas.create_oval(
                x, y, x, y, outline=self.color, width=self.size,
            )

        elif self.tool == "rectangle":
            self.current_item = self.canvas.create_rectangle(
                x, y, x, y, outline=self.color, width=self.size,
            )

        elif self.tool == "eraser":
            self.erase_at(x, y)
        elif self.tool == "text":
            self.add_text(x, y)
        elif self.tool == "select":
            self.select_at(x, y)

    def on_drag(self, x, y):
        if self.tool in ("pencil", "highlighter") and self.current_item is not None:
            if self.current_points:
                last_x, last_y = self.current_points[-2:]
                if (x - last_x) ** 2 + (y - last_y) ** 2 < 4:
                    return
            self.current_points.extend([x, y])
            self.canvas.coords(self.current_item, *self.current_points)
        elif self.tool in ("line", "circle", "rectangle") and self.current_item is not None:
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
        if self.tool in ("pencil", "highlighter", "line", "circle", "rectangle") and self.current_item is not None:
            item = self.current_item
            self.current_item = None
            self.current_points = []
            coords = self.canvas.coords(item)
            if len(coords) < 4 or (coords[:2] == coords[-2:] and len(coords) == 4):
                if len(set(coords)) <= 2:
                    self.canvas.delete(item)
                    return
            self._push_history({"kind": "existence", "item": item, "snapshot": self._snapshot(item)})

        elif self.tool == "select":
            if self.selection_box is not None:
                self.canvas.delete(self.selection_box)
                self.selection_box = None
            if self.selected_item is not None:
                new_coords = self.canvas.coords(self.selected_item)
                if new_coords != self.selected_orig_coords:
                    self._push_history({
                        "kind": "move",
                        "item": self.selected_item,
                        "from": self.selected_orig_coords,
                        "to": new_coords,
                    })
            self.selected_item = None
            self.selected_orig_coords = None

    def erase_at(self, x, y):
        radius = max(14, self.size * 2)
        found = list(self.canvas.find_overlapping(
            x - radius, y - radius, x + radius, y + radius
        ))
        if not found:
            found = list(self.canvas.find_closest(x, y, halo=radius))
        for item in found:
            if "selection_box" in self.canvas.gettags(item):
                continue
            snapshot = self._snapshot(item)
            self.canvas.delete(item)
            self._push_history({"kind": "existence", "item": None, "snapshot": snapshot})

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
                self._push_history({
                    "kind": "existence", "item": item, "snapshot": self._snapshot(item)
                })

        entry.bind("<Return>", finish)
        entry.bind("<Escape>", lambda e: entry.destroy())

    def select_at(self, x, y):
        found = [
            item for item in self.canvas.find_overlapping(x - 4, y - 4, x + 4, y + 4)
            if "selection_box" not in self.canvas.gettags(item)
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

    def _snapshot(self, item):
        item_type = self.canvas.type(item)
        coords = self.canvas.coords(item)
        if item_type == "line":
            config = {
                "fill": self.canvas.itemcget(item, "fill"),
                "width": self.canvas.itemcget(item, "width"),
                "stipple": self.canvas.itemcget(item, "stipple"),
                "capstyle": self.canvas.itemcget(item, "capstyle"),
                "joinstyle": self.canvas.itemcget(item, "joinstyle"),
                "smooth": self.canvas.itemcget(item, "smooth"),
            }
        elif item_type == "text":
            config = {
                "fill": self.canvas.itemcget(item, "fill"),
                "text": self.canvas.itemcget(item, "text"),
                "font": self.canvas.itemcget(item, "font"),
                "anchor": self.canvas.itemcget(item, "anchor"),
            }
        elif item_type == "oval":
            config = {
                "outline": self.canvas.itemcget(item, "outline"),
                "width": self.canvas.itemcget(item, "width"),
                "fill": self.canvas.itemcget(item, "fill"),
            }
        elif item_type == "rectangle":
            config = {
                "outline": self.canvas.itemcget(item, "outline"),
                "width": self.canvas.itemcget(item, "width"),
                "fill": self.canvas.itemcget(item, "fill"),
            }
        else:
            config = {}
        return {"type": item_type, "coords": coords, "cfg": config}

    def _recreate(self, snapshot):
        item_type = snapshot["type"]
        coords = snapshot["coords"]
        config = snapshot["cfg"]
        if item_type == "line":
            return self.canvas.create_line(
                *coords, fill=config["fill"], width=config["width"],
                stipple=config["stipple"], capstyle=config["capstyle"],
                joinstyle=config["joinstyle"], smooth=config["smooth"],
            )
        if item_type == "text":
            return self.canvas.create_text(
                *coords, fill=config["fill"], text=config["text"],
                font=config["font"], anchor=config.get("anchor", "nw"),
            )
        if item_type == "oval":
            return self.canvas.create_oval(
                *coords, outline=config["outline"], width=config["width"],
                fill=config["fill"],
            )
        if item_type == "rectangle":
            return self.canvas.create_rectangle(
                *coords, outline=config["outline"], width=config["width"],
                fill=config["fill"],
            )
        return None

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
        if action["kind"] == "existence":
            self._toggle_existence(action)
        elif action["kind"] == "move":
            self.canvas.coords(action["item"], *action["from"])
        elif action["kind"] == "clear":
            action["items"] = [self._recreate(s) for s in action["snapshots"]]
        self.redo_stack.append(action)

    def redo(self):
        if not self.redo_stack:
            return
        action = self.redo_stack.pop()
        if action["kind"] == "existence":
            self._toggle_existence(action)
        elif action["kind"] == "move":
            self.canvas.coords(action["item"], *action["to"])
        elif action["kind"] == "clear":
            for item in action["items"]:
                self.canvas.delete(item)
            action["items"] = []
        self.history.append(action)

    def clear_all(self):
        items = [
            item for item in self.canvas.find_all()
            if "selection_box" not in self.canvas.gettags(item)
        ]
        if not items:
            return
        snapshots = [self._snapshot(item) for item in items]
        for item in items:
            self.canvas.delete(item)
        self._push_history({"kind": "clear", "snapshots": snapshots, "items": []})

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
        except Exception as error:
            messagebox.showerror("Error saving image", str(error))