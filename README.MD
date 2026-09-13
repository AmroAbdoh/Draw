# Screen Draw

A lightweight Windows desktop app for drawing directly on top of your screen —
draw, highlight, and mark up anything on your desktop, in any app, without
switching windows.

## Features

- **Draw anywhere** — a full-screen overlay sits on top of everything else
- **Full transparency** — see your desktop through the overlay while you draw
  (falls back to a semi-transparent mode automatically if `pynput` isn't
  available)
- **Tools:** Pencil, Highlighter, Eraser, Line, Rectangle, Circle
- **Select / Move** — click and drag an existing drawing to reposition it
- **Cursor mode** — instantly turn off drawing and interact with your desktop
  normally, without closing the app
- **Undo / Redo**
- **Clear** — wipe everything and start over
- **Adjustable brush size**
- **Save your drawing as a PNG**
- **Hide to system tray** instead of closing
- Remembers your last-used color and size between sessions

## Requirements

- Windows 10/11
- Python 3.10+ (built and tested on 3.13)
- Dependencies:
  ```
  pip install pynput pillow
  ```
  (`pynput` is optional but strongly recommended — without it the app runs in
  a semi-transparent fallback mode instead of a fully see-through overlay)

## Running it

```
python screen_annotator.py
```

## Building a standalone .exe

A PyInstaller spec file is included, preconfigured with the icon assets
bundled in:

```
pip install pyinstaller
pyinstaller ScreenAnnotator.spec
```

The finished executable will be at `dist\ScreenAnnotator.exe`.

## Project structure

```
screen_annotator.py     # entry point
annotator_ui.py          # toolbar and overlay window UI
annotator_drawing.py      # drawing tools and canvas logic
annotator_input.py        # mouse input handling (including the pynput hook)
annotator_config.py       # app configuration / defaults
annotator_settings.py     # saving and loading user preferences
annotator_tray.py         # system tray integration
icons/                    # toolbar icon assets
ScreenAnnotator.spec      # PyInstaller build configuration
```

## Notes

- The "full transparency" mode relies on a Windows-specific technique
  (a transparent color key) combined with a global mouse hook to keep drawing
  working despite it. Some antivirus tools flag global mouse hooks — this is
  expected behavior for this kind of overlay app, not malicious code.
- This app is Windows-only due to its use of `ctypes`/`user32` APIs for
  click-through support.

## License

No license has been added yet — add one (e.g. MIT) if you want others to be
able to reuse this code.