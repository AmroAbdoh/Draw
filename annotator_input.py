"""Global input and Windows click-through behavior."""

import ctypes
import tkinter as tk


class AnnotatorInputMixin:
    def _get_root_hwnd(self, hwnd):
        try:
            return ctypes.windll.user32.GetAncestor(hwnd, 2)
        except Exception:
            return hwnd

    def _set_clickthrough(self, enable):
        if not self.HAVE_PYNPUT:
            try:
                self.overlay.attributes(
                    "-alpha", 0.02 if enable else self.DEFAULT_ALPHA
                )
            except tk.TclError:
                pass

        if not self.IS_WINDOWS:
            return
        try:
            self.overlay.update_idletasks()
            hwnd = self._get_root_hwnd(self.overlay.winfo_id())
            style_flag = -20
            layered = 0x00080000
            transparent = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(hwnd, style_flag)
            if enable:
                style |= layered | transparent
            else:
                style |= layered
                style &= ~transparent
            ctypes.windll.user32.SetWindowLongW(hwnd, style_flag, style)
        except Exception:
            pass

    def _start_mouse_hook(self):
        blocked_mouse_messages = {
            0x0201, 0x0202,
            0x0204, 0x0205,
            0x0207, 0x0208,
            0x020B, 0x020C,
            0x020A,
        }

        def win32_event_filter(msg, data):
            if msg in blocked_mouse_messages and self.tool != "pointer":
                try:
                    in_toolbar = self._point_in_toolbar(data.pt.x, data.pt.y)
                except Exception:
                    in_toolbar = False
                if not in_toolbar:
                    if msg == 0x0201:
                        self.root.after(0, self._handle_hook_press, data.pt.x, data.pt.y)
                    elif msg == 0x0202:
                        self.root.after(0, self._handle_hook_release, data.pt.x, data.pt.y)
                    elif msg == 0x020A:
                        wheel_delta = ctypes.c_short(data.mouseData >> 16).value
                        self.root.after(
                            0,
                            self._adjust_size,
                            1 if wheel_delta > 0 else -1,
                        )
                    self.mouse_listener.suppress_event()

        def win32_keyboard_filter(msg, data):
            if msg in (0x0100, 0x0101, 0x0104, 0x0105) and self.tool != "pointer":
                self.keyboard_listener.suppress_event()

        def on_click(x, y, button, pressed):
            if button != self._pynput_mouse.Button.left:
                return
            if pressed:
                self.root.after(0, self._handle_hook_press, x, y)
            else:
                self.root.after(0, self._handle_hook_release, x, y)

        def on_move(x, y):
            if self._mouse_down:
                self._queue_mouse_move(x, y)

        self.mouse_listener = self._pynput_mouse.Listener(
            on_click=on_click,
            on_move=on_move,
            win32_event_filter=win32_event_filter if self.IS_WINDOWS else None,
        )
        self.mouse_listener.daemon = True
        self.mouse_listener.start()

        if self.IS_WINDOWS:
            self.keyboard_listener = self._pynput_keyboard.Listener(
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

    def _queue_mouse_move(self, x, y):
        with self._move_lock:
            self._pending_move = (x, y)
            if self._move_callback_pending:
                return
            self._move_callback_pending = True
        self.root.after_idle(self._process_mouse_move)

    def _process_mouse_move(self):
        while True:
            with self._move_lock:
                point = self._pending_move
                self._pending_move = None
            if point is None:
                with self._move_lock:
                    if self._pending_move is None:
                        self._move_callback_pending = False
                        return
                    continue
            self._handle_hook_move(*point)
            with self._move_lock:
                if self._pending_move is None:
                    self._move_callback_pending = False
                    return

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