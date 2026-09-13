"""Persistent user settings for the screen annotator."""

import json
import os


def _settings_path():
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    folder = os.path.join(base, "ScreenAnnotator")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")


def load_settings():
    try:
        with open(_settings_path(), "r", encoding="utf-8") as file:
            settings = json.load(file)
        return {
            "color": settings.get("color", "#ff2d55"),
            "size": max(1, min(50, int(settings.get("size", 4)))),
        }
    except (OSError, ValueError, TypeError):
        return {"color": "#ff2d55", "size": 4}


def save_settings(color, size):
    try:
        with open(_settings_path(), "w", encoding="utf-8") as file:
            json.dump({"color": color, "size": int(size)}, file)
    except OSError:
        pass