#!/usr/bin/env python3
"""Native GTK controls for the Constellation by ProgreTech wallpaper."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

HERE = Path(__file__).resolve().parent
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
CONFIG_PATH = CONFIG_HOME / "factory-observatory" / "wallpaper.json"
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
SCENE_PATH = STATE_HOME / "factory-observatory" / "scene.json"
DEFAULT = {
    "enabled": True,
    "paused": False,
    "foreground": True,
    "rotation_speed": 0.85,
    "glow": 0.82,
    "rays": 0.72,
    "density": 0.72,
    "links": True,
    "labels": True,
}


def settings() -> dict:
    try:
        loaded = json.loads(CONFIG_PATH.read_text())
        return {**DEFAULT, **{key: loaded[key] for key in DEFAULT if key in loaded}}
    except (OSError, ValueError, TypeError):
        return dict(DEFAULT)


def save_settings(values: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile("w", dir=CONFIG_PATH.parent, prefix=".wallpaper-", suffix=".json", delete=False) as stream:
        temporary = Path(stream.name)
        os.fchmod(stream.fileno(), 0o600)
        json.dump(values, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, CONFIG_PATH)


class ControlWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="Constellation by ProgreTech")
        self.set_default_size(530, 690)
        self.values = settings()
        self._loading = True
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)
        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Constellation by ProgreTech"))
        outer.append(header)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_start(28)
        content.set_margin_end(28)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        outer.append(content)

        intro = Gtk.Label(label="Explore your memory constellation", xalign=0)
        intro.add_css_class("title-2")
        content.append(intro)
        detail = Gtk.Label(label="Configured directory roots become solar systems. Files named in reviewed activity become stars.", xalign=0, wrap=True)
        detail.add_css_class("dim-label")
        content.append(detail)
        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.add_css_class("dim-label")
        content.append(self.status)
        self._refresh_status()

        self._switch(content, "Show wallpaper", "enabled")
        self._switch(content, "Show custom foreground image", "foreground")
        self._switch(content, "Pause rotation", "paused")
        self._scale(content, "Rotation · degrees per second", "rotation_speed", 0, 5, 2)
        self._scale(content, "Nebula glow", "glow", 0, 1, 2)
        self._scale(content, "Light rays", "rays", 0, 1, 2)
        self._scale(content, "Galaxy star density", "density", 0, 1, 2)
        self._switch(content, "Agent-to-file light trails", "links")
        self._switch(content, "Directory and agent labels", "labels")
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        refresh = Gtk.Button(label="Refresh memory now")
        refresh.connect("clicked", self._refresh_memory)
        buttons.append(refresh)
        inspect = Gtk.Button(label="Open interactive map")
        inspect.connect("clicked", self._open_map)
        buttons.append(inspect)
        content.append(buttons)
        self._loading = False

    def _switch(self, parent: Gtk.Box, title: str, key: str) -> None:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        label = Gtk.Label(label=title, xalign=0, hexpand=True)
        toggle = Gtk.Switch(active=bool(self.values[key]), valign=Gtk.Align.CENTER)
        toggle.connect("notify::active", lambda widget, _property: self._set(key, widget.get_active()))
        row.append(label)
        row.append(toggle)
        parent.append(row)

    def _scale(self, parent: Gtk.Box, title: str, key: str, low: float, high: float, digits: int) -> None:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row.append(Gtk.Label(label=title, xalign=0))
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, low, high, 0.05)
        scale.set_digits(digits)
        scale.set_draw_value(True)
        scale.set_value(float(self.values[key]))
        scale.set_hexpand(True)
        scale.connect("value-changed", lambda widget: self._set(key, round(widget.get_value(), 2)))
        row.append(scale)
        parent.append(row)

    def _set(self, key: str, value) -> None:
        if self._loading:
            return
        self.values[key] = value
        save_settings(self.values)

    def _refresh_status(self) -> None:
        try:
            scene = json.loads(SCENE_PATH.read_text())
            age = max(0, int(time.time()) - int(scene["generated_at"]))
            counts = scene["counts"]
            self.status.set_text(f"{counts['files']} remembered files · {counts['directories']} directories · {counts['agents']} linked agents · refreshed {age // 60} min ago")
        except (OSError, KeyError, TypeError, ValueError):
            self.status.set_text("No valid memory scene yet. Use Refresh memory now to build one.")

    def _refresh_memory(self, _button: Gtk.Button) -> None:
        python = HERE / ".venv/bin/python"
        if not python.exists():
            self.status.set_text("Python environment is missing. See README.md.")
            return
        result = subprocess.run([str(python), str(HERE / "wallpaper_scene.py")], capture_output=True, text=True, timeout=40, check=False)
        if result.returncode:
            self.status.set_text("Memory refresh failed. The existing scene was retained; check the factory memory CLI.")
        else:
            self._refresh_status()

    def _open_map(self, _button: Gtk.Button) -> None:
        subprocess.Popen([str(HERE / "launcher.sh")], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class ControlApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.progretech.Constellation")

    def do_activate(self):
        window = self.props.active_window or ControlWindow(self)
        window.present()


if __name__ == "__main__":
    app = ControlApp()
    raise SystemExit(app.run())
