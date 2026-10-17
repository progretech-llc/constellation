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
from gi.repository import Gio, GLib, Gtk, Pango  # noqa: E402

from config import CONFIG_PATH as SOURCES_PATH, load_config
from source_controls import editable_values, save_folder_controls
from agent_controls import AgentPanel
from memory_controls import MemoryPanel

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
    "memory_planets": 20,
    "agent_mode": "orbiting",
    "solar_rotation": False,
    "solar_rotation_speed": 1.0,
    "solar_clockwise": False,
    "write_lights": False,
    "black_hole_name": "Shared worker",
}


def black_hole_name(value) -> str:
    if not isinstance(value, str):
        return DEFAULT['black_hole_name']
    clean = ''.join(' ' if ord(c) < 32 or ord(c) == 127 else c for c in value)
    return ' '.join(clean.split())[:32] or DEFAULT['black_hole_name']


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
        self.set_default_size(650, 740)
        self.values = settings()
        self._loading = True
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)
        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Constellation by ProgreTech"))
        self.set_titlebar(header)
        power_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        power_bar.set_margin_start(24)
        power_bar.set_margin_end(24)
        power_bar.set_margin_top(12)
        power_bar.set_margin_bottom(12)
        self.power_switch = self._switch(power_bar, 'Galaxy wallpaper', 'enabled')
        self.power_switch.update_property([Gtk.AccessibleProperty.LABEL], ['Galaxy wallpaper on or off'])
        outer.append(power_bar)
        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        tabs = Gtk.Notebook(vexpand=True, scrollable=True)
        outer.append(tabs)
        folders = self._folder_page()
        tabs.append_page(folders, Gtk.Label(label="Folders"))
        self.agent_panel = AgentPanel(SOURCES_PATH, SCENE_PATH, self._refresh_scene)
        tabs.append_page(self.agent_panel, Gtk.Label(label='Agents'))
        self.memory_panel = MemoryPanel(SOURCES_PATH, self._refresh_scene)
        tabs.append_page(self.memory_panel, Gtk.Label(label='Memory Node'))
        tabs.append_page(self._recommendations_page(), Gtk.Label(label="Recommendations"))
        appearance = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        tabs.append_page(appearance, Gtk.Label(label="Appearance"))
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_start(28)
        content.set_margin_end(28)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        appearance.set_child(content)

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

        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        name_box.append(Gtk.Label(label='Black-hole display name', xalign=0))
        name_row = Gtk.Box(spacing=8)
        self.black_hole_entry = Gtk.Entry(text=black_hole_name(self.values['black_hole_name']),
                                         max_length=32, hexpand=True)
        self.black_hole_entry.update_property([Gtk.AccessibleProperty.LABEL], ['Black-hole display name'])
        self.black_hole_entry.connect('activate', self._save_black_hole_name)
        name_row.append(self.black_hole_entry)
        self.black_hole_save = Gtk.Button(label='Save name')
        self.black_hole_save.connect('clicked', self._save_black_hole_name)
        name_row.append(self.black_hole_save)
        name_box.append(name_row)
        self.black_hole_status = Gtk.Label(label='Display only; factory-worker identity and history stay the same. '
            'Up to 32 characters. Leave blank to restore Shared worker.', xalign=0, wrap=True)
        name_box.append(self.black_hole_status)
        content.append(name_box)

        self._switch(content, "Show custom foreground image", "foreground")
        self._switch(content, "Pause all motion", "paused")
        modes = ('orbiting', 'asteroid', 'satellite')
        movement = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        movement.append(Gtk.Label(label='Agent movement', xalign=0))
        selector = Gtk.DropDown.new_from_strings(['Orbiting · original', 'Asteroid · roam between targets',
                                                 'Satellite · latest modified system'])
        selector.set_selected(modes.index(self.values['agent_mode']) if self.values['agent_mode'] in modes else 0)
        selector.update_property([Gtk.AccessibleProperty.LABEL], ['Agent movement'])
        description = Gtk.Label(xalign=0, wrap=True)
        explanations = (
            'Original host orbits, light trails and bouncing lights.',
            'Agents circle near remembered folders, touch file targets, then travel onward. '
            'Agent lines and bouncing lights are hidden in this mode.',
            'Agents orbit their latest visibly modified system, with lines to recently written files and their folders. '
            'Agents without matching activity keep their original orbit.')
        description.set_text(explanations[selector.get_selected()])
        def mode_changed(widget, _property):
            index = widget.get_selected()
            self._set('agent_mode', modes[index])
            description.set_text(explanations[index])
            self._update_light_controls()
        selector.connect('notify::selected', mode_changed)
        movement.append(selector)
        movement.append(description)
        content.append(movement)
        self.write_switch = self._switch(content, 'Write lights · no connecting lines', 'write_lights')
        self.write_switch.connect('notify::active', lambda *_args: self._update_light_controls())
        content.append(Gtk.Label(label='Orbiting and Asteroid: replay recorded writes as one-way lights to tiny file planets. '
            'An arrival briefly lights the file; it does not create a duplicate or indicate a live write. '
            'Replaces the original orbiting lines and bouncing lights while enabled.', xalign=0, wrap=True))
        self._scale(content, "Galaxy rotation · degrees per second", "rotation_speed", 0, 5, 2)
        self._switch(content, 'Rotate solar systems independently', 'solar_rotation')
        self._scale(content, 'Solar-system spin · degrees per second', 'solar_rotation_speed', 0, 10, 2)
        self._switch(content, 'Spin clockwise', 'solar_clockwise')
        content.append(Gtk.Label(label='Counterclockwise by default. Controls folders and files around each system’s center. '
                                 'Galaxy rotation stays separate; Pause freezes both.', xalign=0, wrap=True))
        self._scale(content, "Nebula glow", "glow", 0, 1, 2)
        self._scale(content, "Light rays", "rays", 0, 1, 2)
        self._scale(content, "Galaxy star density", "density", 0, 1, 2)
        self.links_switch = self._switch(content, "Agent connection lines / orbiting lights", "links")
        self.links_status = Gtk.Label(xalign=0, wrap=True)
        content.append(self.links_status)
        self._update_light_controls()
        self._switch(content, "Directory and agent labels", "labels")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.append(Gtk.Label(label="Recent Hindsight planets", xalign=0, hexpand=True))
        planets = Gtk.SpinButton.new_with_range(1, 100, 1)
        planets.set_value(int(self.values['memory_planets']))
        planets.connect('value-changed', lambda widget: self._set('memory_planets', widget.get_value_as_int()))
        row.append(planets)
        content.append(row)
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        refresh = Gtk.Button(label="Refresh memory now")
        refresh.connect("clicked", self._refresh_memory)
        buttons.append(refresh)
        inspect = Gtk.Button(label="Open interactive map")
        inspect.connect("clicked", self._open_map)
        buttons.append(inspect)
        content.append(buttons)
        self._loading = False

    def _save_black_hole_name(self, _widget):
        name = black_hole_name(self.black_hole_entry.get_text())
        try:
            try:
                current = json.loads(CONFIG_PATH.read_text())
            except FileNotFoundError:
                current = {}
            if not isinstance(current, dict):
                raise ValueError('Invalid settings')
            save_settings({**current, 'black_hole_name': name})
        except (OSError, ValueError, TypeError):
            self.black_hole_status.set_text('Name could not be saved. Your draft is retained; try again.')
            return
        self.values['black_hole_name'] = name
        self.black_hole_entry.set_text(name)
        self.black_hole_status.set_text('Display name saved. Agent identity and activity history are unchanged.')

    def _update_light_controls(self):
        mode = self.values['agent_mode']
        self.write_switch.set_sensitive(mode != 'satellite')
        self.links_switch.set_sensitive(mode != 'asteroid' and not (mode == 'orbiting' and self.values['write_lights']))
        if mode == 'asteroid':
            self.links_status.set_text('Asteroid mode hides connection lines and bouncing lights. '
                + ('One-way Write lights are enabled. ' if self.values['write_lights'] else '')
                + 'For connections, choose Satellite or choose Orbiting with Write lights off.')
        elif mode == 'orbiting' and self.values['write_lights']:
            self.links_status.set_text('Write lights replace connection lines and bouncing lights. '
                'Turn Write lights off above to enable this switch.')
        self.links_status.set_visible(not self.links_switch.get_sensitive())
        self.write_switch.set_tooltip_text('Write lights are available in Orbiting and Asteroid modes.'
                                           if mode == 'satellite' else None)

    def _recommendations_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for edge in ('start', 'end', 'top', 'bottom'):
            getattr(page, f'set_margin_{edge}')(24)
        title = Gtk.Label(label='Find your busiest folders', xalign=0)
        title.add_css_class('title-2')
        page.append(title)
        page.append(Gtk.Label(label='Find the top five folders mentioned in recent reviewed activity '
                              'from your configured agents and memory source. Project subfolders are grouped '
                              'under their repository; other paths are grouped under your galaxy or home folder.',
                              xalign=0, wrap=True))
        self.scan_button = Gtk.Button(label='Scan for recommended folders', halign=Gtk.Align.START)
        self.scan_button.add_css_class('suggested-action')
        self.scan_button.connect('clicked', self._scan_folders)
        page.append(self.scan_button)
        self.scan_status = Gtk.Label(label='Scan reads reviewed memory and checks referenced paths. '
                                          'It does not scan file contents or add folders automatically.',
                                    xalign=0, wrap=True)
        page.append(self.scan_status)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.recommendation_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        scroll.set_child(self.recommendation_list)
        page.append(scroll)
        page.append(Gtk.Label(label='Choose Add to draft, then use Apply folder changes on the Folders tab.',
                              xalign=0, wrap=True))
        return page

    def _scan_folders(self, _button: Gtk.Button) -> None:
        self.scan_button.set_sensitive(False)
        self.scan_status.set_text('Checking recent reviewed activity…')
        try:
            process = Gio.Subprocess.new(['/usr/bin/python3', str(HERE / 'folder_recommendations.py')],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
            def finished(proc, result):
                self.scan_button.set_sensitive(True)
                try:
                    _ok, output, _error = proc.communicate_utf8_finish(result)
                    if not proc.get_successful():
                        raise ValueError('retrieval failed')
                    data = json.loads(output)
                    self._show_recommendations(data['recommendations'])
                    count = len(data['recommendations'])
                    self.scan_status.set_text(f"Checked {data['activities_checked']} reviewed activities · "
                                              f"{count} recommendations · {time.strftime('%H:%M')}. " +
                                              ('No eligible existing folders were found.' if not count else
                                               'Ranked by activity count, agent count, then recency.'))
                except (GLib.Error, ValueError, KeyError, TypeError):
                    self.scan_status.set_text('Scan failed. Check the configured memory source and try again. '
                                              'Any previous recommendations below may be out of date.')
            process.communicate_utf8_async(None, None, finished)
        except GLib.Error:
            self.scan_button.set_sensitive(True)
            self.scan_status.set_text('Could not start the scan. Try again after checking the installation.')

    def _show_recommendations(self, recommendations: list[dict]) -> None:
        child = self.recommendation_list.get_first_child()
        while child:
            self.recommendation_list.remove(child)
            child = self.recommendation_list.get_first_child()
        for item in recommendations:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            row.append(Gtk.Label(label=item['label'], xalign=0))
            path = Gtk.Label(label=item['path'], xalign=0, wrap=True, selectable=True)
            path.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            row.append(path)
            count = len(item['agents'])
            activity_word = 'activity' if item['activity_count'] == 1 else 'activities'
            agent_word = 'agent' if count == 1 else 'agents'
            detail = Gtk.Label(label=f"{item['activity_count']} {activity_word} · {count} {agent_word}", xalign=0)
            detail.add_css_class('dim-label')
            row.append(detail)
            add = Gtk.Button(label='Add to draft', halign=Gtk.Align.START)
            add.connect('clicked', lambda button, candidate=item: self._add_recommendation(button, candidate))
            row.append(add)
            self.recommendation_list.append(row)

    def _add_recommendation(self, button: Gtk.Button, item: dict) -> None:
        path = Path(item['path'])
        if not hasattr(self, 'folder_rows') or not self.folder_apply.get_sensitive():
            self.scan_status.set_text('Reload a valid folder configuration on the Folders tab first.')
            return
        if any(Path(row[2]).expanduser().resolve() == path.resolve() for row in self.folder_rows):
            self.scan_status.set_text('That folder is already in your galaxy draft.')
            return
        if len(self.folder_rows) >= 12:
            self.scan_status.set_text('The draft already has 12 folders. Remove one on the Folders tab first.')
            return
        if not path.is_dir():
            self.scan_status.set_text('That folder is no longer available. Scan again for current recommendations.')
            return
        names = {row[1].get_text().strip() for row in self.folder_rows}
        label, suffix = item['label'], 2
        while label in names:
            label = f"{item['label']} {suffix}"
            suffix += 1
        self._append_folder(label, str(path))
        self.scan_status.set_text(f'Added {label} to the draft. Apply folder changes on the Folders tab to save.')

    def _folder_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for edge in ('start', 'end', 'top', 'bottom'):
            getattr(page, f'set_margin_{edge}')(24)
        title = Gtk.Label(label="Folders in your galaxy", xalign=0)
        title.add_css_class('title-2')
        page.append(title)
        page.append(Gtk.Label(label="Add up to 12 folders as solar systems. Rename them below. "
                              "Removing one only hides it from the galaxy; your files stay untouched.",
                              xalign=0, wrap=True))
        self.folder_status = Gtk.Label(xalign=0, wrap=True)
        self.folder_status.set_selectable(True)
        page.append(self.folder_status)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.folder_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.set_child(self.folder_list)
        page.append(scroll)
        self.folder_add = Gtk.Button(label="Add folder…", halign=Gtk.Align.START)
        self.folder_add.connect('clicked', self._choose_folder)
        page.append(self.folder_add)
        self.file_limit = self._limit_control(page, 'Remembered files · maximum', 1000)
        self.directory_limit = self._limit_control(page, 'Remembered subfolders · maximum', 200)
        detail = Gtk.Label(label="These limits apply across the galaxy. Only files and subfolders "
                           "mentioned in reviewed memory appear; adding a folder does not scan its contents.",
                           xalign=0, wrap=True)
        detail.add_css_class('dim-label')
        page.append(detail)
        buttons = Gtk.Box(spacing=10)
        self.folder_apply = Gtk.Button(label="Apply folder changes")
        self.folder_apply.add_css_class('suggested-action')
        self.folder_apply.connect('clicked', self._apply_folders)
        reload_button = Gtk.Button(label="Reload folders")
        reload_button.set_tooltip_text('Discard unapplied folder edits and reload saved settings')
        reload_button.connect('clicked', lambda _button: self._load_folders())
        buttons.append(self.folder_apply)
        buttons.append(reload_button)
        page.append(buttons)
        self._load_folders()
        return page

    def _limit_control(self, parent: Gtk.Box, label: str, maximum: int) -> Gtk.SpinButton:
        row = Gtk.Box(spacing=12)
        caption = Gtk.Label(label=label, xalign=0, hexpand=True)
        row.append(caption)
        spin = Gtk.SpinButton.new_with_range(1, maximum, 1)
        spin.update_property([Gtk.AccessibleProperty.LABEL], [label])
        row.append(spin)
        parent.append(row)
        return spin

    def _load_folders(self) -> None:
        try:
            data = load_config(SOURCES_PATH)
            self.source_expected = editable_values(data)
            self.file_limit.set_value(int(data.get('max_files', 160)))
            self.directory_limit.set_value(int(data.get('max_directories', 48)))
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
            self.folder_status.set_text(f"Could not load folders: {error}")
            self.folder_apply.set_sensitive(False)
            self.folder_add.set_sensitive(False)
            return
        child = self.folder_list.get_first_child()
        while child:
            self.folder_list.remove(child)
            child = self.folder_list.get_first_child()
        self.folder_rows = []
        for root in data['roots']:
            self._append_folder(root['label'], root['path'])
        self.folder_apply.set_sensitive(True)
        self.folder_status.set_text('Folder changes take effect when you select Apply folder changes.')
        self._update_folder_buttons()

    def _append_folder(self, label: str, path: str) -> None:
        row = Gtk.Box(spacing=12)
        fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        name = Gtk.Entry(text=label, hexpand=True, max_length=80)
        name.update_property([Gtk.AccessibleProperty.LABEL], [f'Galaxy name for {path}'])
        fields.append(name)
        location = Gtk.Label(label=path, xalign=0, wrap=True, selectable=True)
        location.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        location.add_css_class('dim-label')
        fields.append(location)
        row.append(fields)
        remove = Gtk.Button(label='Remove', valign=Gtk.Align.CENTER)
        remove.update_property([Gtk.AccessibleProperty.LABEL], [f'Remove {label} from the galaxy'])
        remove.set_tooltip_text('Remove from the galaxy only; no files are deleted')
        row.append(remove)
        item = (row, name, path, remove)
        remove.connect('clicked', lambda _button: self._remove_folder(item))
        self.folder_rows.append(item)
        self.folder_list.append(row)
        self._update_folder_buttons()

    def _update_folder_buttons(self) -> None:
        self.folder_add.set_sensitive(len(self.folder_rows) < 12)
        for _row, _name, _path, remove in self.folder_rows:
            remove.set_sensitive(len(self.folder_rows) > 1)

    def _remove_folder(self, item: tuple) -> None:
        self.folder_list.remove(item[0])
        self.folder_rows.remove(item)
        self._update_folder_buttons()
        self.folder_status.set_text('Folder removed from this draft. Apply to update the galaxy.')

    def _choose_folder(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileChooserNative.new('Add a galaxy folder', self,
                    Gtk.FileChooserAction.SELECT_FOLDER, 'Add folder', 'Cancel')
        self._folder_chooser = chooser
        chooser.connect('response', self._folder_chosen)
        chooser.show()

    def _folder_chosen(self, chooser, response) -> None:
        selected = chooser.get_file() if response == Gtk.ResponseType.ACCEPT else None
        chooser.destroy()
        self._folder_chooser = None
        if selected is None:
            return
        path = selected.get_path()
        if not path or not Path(path).is_dir():
            self.folder_status.set_text('Choose an available local or mounted folder.')
            return
        if len(self.folder_rows) >= 12:
            self.folder_status.set_text('The galaxy supports up to 12 folders.')
            return
        resolved = Path(path).resolve()
        if any(Path(row[2]).expanduser().resolve() == resolved for row in self.folder_rows):
            self.folder_status.set_text('That folder is already in the list.')
            return
        label = Path(path).name or 'Filesystem'
        names = {row[1].get_text().strip() for row in self.folder_rows}
        base, suffix = label, 2
        while label in names:
            label = f'{base} {suffix}'
            suffix += 1
        self._append_folder(label, path)
        self.folder_status.set_text('Folder added to this draft. Apply to update the galaxy.')

    def _apply_folders(self, _button: Gtk.Button) -> None:
        roots = [{'label': name.get_text(), 'path': path}
                 for _row, name, path, _remove in self.folder_rows]
        try:
            saved = save_folder_controls(SOURCES_PATH, roots, self.file_limit.get_value_as_int(),
                                         self.directory_limit.get_value_as_int(), self.source_expected)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
            self.folder_status.set_text(f'Not saved: {error}')
            return
        self.source_expected = editable_values(saved)
        self._refresh_scene(self.folder_status, 'Folders saved. ')

    def _refresh_scene(self, label: Gtk.Label, prefix: str = '') -> None:
        label.set_text(prefix + 'Refreshing the galaxy…')
        try:
            process = Gio.Subprocess.new(['systemctl', '--user', 'start',
                                         'factory-observatory-scene.service'],
                                        Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE)
            def finished(proc, result):
                try:
                    proc.wait_check_finish(result)
                except GLib.Error:
                    label.set_text(prefix + 'Refresh failed; the previous scene is still displayed. '
                                   'Use Refresh memory now on the Appearance tab to retry.')
                else:
                    label.set_text(prefix + 'Galaxy refreshed.')
                    self._refresh_status()
            process.wait_check_async(None, finished)
        except GLib.Error:
            label.set_text(prefix + 'Could not start the refresh. The automatic timer will retry.')

    def _switch(self, parent: Gtk.Box, title: str, key: str) -> Gtk.Switch:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        label = Gtk.Label(label=title, xalign=0, hexpand=True)
        toggle = Gtk.Switch(active=bool(self.values[key]), valign=Gtk.Align.CENTER)
        toggle.connect("notify::active", lambda widget, _property: self._set(key, widget.get_active()))
        row.append(label)
        row.append(toggle)
        parent.append(row)
        return toggle

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
        if key == 'memory_planets':
            subprocess.Popen(['systemctl', '--user', 'start', 'factory-observatory-scene.service'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _refresh_status(self) -> None:
        try:
            scene = json.loads(SCENE_PATH.read_text())
            age = max(0, int(time.time()) - int(scene["generated_at"]))
            counts = scene["counts"]
            self.status.set_text(f"{counts['files']} remembered files · {counts.get('memory_planets', 0)} memory planets · {counts['agents']} displayed agents · refreshed {age // 60} min ago")
        except (OSError, KeyError, TypeError, ValueError):
            self.status.set_text("No valid memory scene yet. Use Refresh memory now to build one.")

    def _refresh_memory(self, _button: Gtk.Button) -> None:
        self._refresh_scene(self.status)

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
