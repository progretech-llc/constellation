"""Choose one displayed memory system without changing the activity backend."""
import json
import time
from pathlib import Path

from gi.repository import Gio, GLib, Gtk

from config import load_config
from memory_discovery import PROVIDERS
from source_controls import save_memory_node


class MemoryPanel(Gtk.Box):
    def __init__(self, config_path, refresh):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.config_path, self.refresh = config_path, refresh
        for edge in ('start', 'end', 'top', 'bottom'):
            getattr(self, f'set_margin_{edge}')(24)
        title = Gtk.Label(label='Memory system in your galaxy', xalign=0)
        title.add_css_class('title-2')
        self.append(title)
        self.append(Gtk.Label(label='Display one memory system at a time. Hindsight is the default. '
                              'This changes the galaxy node, not the memory backend used by your agents.',
                              xalign=0, wrap=True))
        self.status = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.append(self.status)
        self.scan = Gtk.Button(label='Scan for memory systems', halign=Gtk.Align.START)
        self.scan.connect('clicked', self._scan)
        self.append(self.scan)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.items = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        scroll.set_child(self.items)
        self.append(scroll)
        self.append(Gtk.Label(label='Hindsight can display recent shared memory records. Other detected systems '
                              'currently display a system node only; their records are not read or migrated.',
                              xalign=0, wrap=True))
        actions = Gtk.Box(spacing=8)
        self.apply = Gtk.Button(label='Apply memory node')
        self.apply.add_css_class('suggested-action')
        self.apply.connect('clicked', self._apply)
        reload_button = Gtk.Button(label='Reload selection')
        reload_button.connect('clicked', lambda _button: self._load())
        actions.append(self.apply)
        actions.append(reload_button)
        self.append(actions)
        self._load()

    def _load(self):
        try:
            config = load_config(self.config_path)
            self.expected = config.get('memory_node')
            chosen = self.expected or {'provider': 'hindsight', 'path': ''}
            self.selected = chosen['provider']
            path = chosen.get('path', '')
            if not path and self.selected == 'hindsight':
                path = next((root['path'] for root in config['roots'] if root['label'].casefold() == 'hindsight'), '')
            self.systems = {self.selected: {'provider': self.selected, 'label': PROVIDERS[self.selected],
                                          'path': path, 'status': 'saved selection · scan to check availability'}}
            self.apply.set_sensitive(True)
            self._render()
            self.status.set_text('Selection loaded. Scan to find other supported local memory systems.')
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            self.systems = {}
            self.selected = None
            self.apply.set_sensitive(False)
            self.status.set_text('Could not load memory node settings. Fix the source configuration, then reload.')

    def _render(self):
        child = self.items.get_first_child()
        while child:
            self.items.remove(child)
            child = self.items.get_first_child()
        self.checks, group = {}, None
        for provider, item in self.systems.items():
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            check = Gtk.CheckButton(label=item['label'])
            if group:
                check.set_group(group)
            else:
                group = check
            check.set_active(provider == self.selected)
            self.checks[provider] = check
            box.append(check)
            detail = item['status']
            if 'records_supported' in item:
                detail += ' · shared record reader available' if item['records_supported'] else ' · system node only'
            box.append(Gtk.Label(label=detail, xalign=0, wrap=True))
            if item.get('path'):
                location = Gtk.Label(label=item['path'], xalign=0, wrap=True, selectable=True)
                location.add_css_class('dim-label')
                box.append(location)
            self.items.append(box)
        for provider, check in self.checks.items():
            check.connect('toggled', self._toggled, provider)

    def _toggled(self, check, provider):
        if check.get_active():
            self.selected = provider
            self.status.set_text(f'Draft: display {PROVIDERS[provider]}. Apply to save.')

    def _scan(self, _button):
        self.scan.set_sensitive(False)
        self.status.set_text('Checking supported local memory services, commands and directories…')
        try:
            process = Gio.Subprocess.new(['/usr/bin/python3', str(Path(__file__).with_name('memory_discovery.py'))],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
            def finished(proc, result):
                self.scan.set_sensitive(True)
                try:
                    _ok, output, _error = proc.communicate_utf8_finish(result)
                    if not proc.get_successful():
                        raise ValueError('Scan failed')
                    data = json.loads(output)
                    found = {item['provider']: item for item in data['systems']}
                    if self.selected not in found and self.selected in self.systems:
                        previous = {**self.systems[self.selected], 'status': 'not detected in latest scan',
                                    'records_supported': False}
                        found[self.selected] = previous
                    self.systems = found
                    self._render()
                    self.status.set_text(f"Found {len(data['systems'])} supported systems at {time.strftime('%H:%M')}. " +
                                         ' '.join(data['warnings']))
                except (GLib.Error, ValueError, KeyError, TypeError):
                    self.status.set_text('Memory scan failed. The saved selection is unchanged; try again.')
            process.communicate_utf8_async(None, None, finished)
        except GLib.Error:
            self.scan.set_sensitive(True)
            self.status.set_text('Could not start memory discovery. The saved selection is unchanged.')

    def _apply(self, _button):
        try:
            item = self.systems[self.selected]
            selected = {'provider': self.selected, 'path': item.get('path', '')}
            saved = save_memory_node(self.config_path, selected, self.expected)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            self.status.set_text('Memory selection was not saved. Reload the selection and retry.')
            return
        self.expected = saved['memory_node']
        self.refresh(self.status, 'Memory node saved. ')
