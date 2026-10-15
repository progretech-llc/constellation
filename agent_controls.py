"""Agent visibility and local gateway discovery panel."""
import json
import time
from pathlib import Path

from gi.repository import Gio, GLib, Gtk

from agent_discovery import configured_candidates
from config import load_config
from source_controls import save_agent_controls


class AgentPanel(Gtk.Box):
    def __init__(self, config_path, scene_path, refresh):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.config_path, self.scene_path, self.refresh = config_path, scene_path, refresh
        for edge in ('start', 'end', 'top', 'bottom'):
            getattr(self, f'set_margin_{edge}')(24)
        title = Gtk.Label(label='Agents in your galaxy', xalign=0)
        title.add_css_class('title-2')
        self.append(title)
        self.append(Gtk.Label(label='Choose which agent nodes and connections to display. '
                              'This does not start or stop agents. Clients sharing one memory identity appear once.',
                              xalign=0, wrap=True))
        self.status = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.append(self.status)
        self.scan = Gtk.Button(label='Scan for gateways', halign=Gtk.Align.START)
        self.scan.connect('clicked', self._scan)
        self.append(self.scan)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.items = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.set_child(self.items)
        self.append(scroll)
        choices = Gtk.Box(spacing=8)
        for text, callback in [('Select all', lambda: self._select(set(self.candidates))),
                               ('Select none', lambda: self._select(set())),
                               ('Automatic', self._automatic)]:
            button = Gtk.Button(label=text)
            button.connect('clicked', lambda _button, call=callback: call())
            choices.append(button)
        self.append(choices)
        actions = Gtk.Box(spacing=8)
        self.apply = Gtk.Button(label='Apply agent selection')
        self.apply.add_css_class('suggested-action')
        self.apply.connect('clicked', self._apply)
        actions.append(self.apply)
        reload_button = Gtk.Button(label='Reload agents')
        reload_button.connect('clicked', lambda _button: self._load())
        actions.append(reload_button)
        self.append(actions)
        self.sources = []
        self._load()

    def _load(self):
        try:
            data = load_config(self.config_path)
            try:
                scene = json.loads(self.scene_path.read_text())
            except (OSError, ValueError):
                scene = {}
            self.candidates = {item['id']: item for item in configured_candidates(data, scene)}
            self.default_ids = set(data['agents']) | set(scene.get('available_agents', [])) | {
                node['id'].removeprefix('agent:') for node in scene.get('nodes', [])
                if node.get('kind') == 'Agent' and node.get('id', '').startswith('agent:')}
            self.expected = data.get('display_agents')
            self.automatic = self.expected is None
            self.selection = set(self.default_ids if self.automatic else self.expected)
            self.apply.set_sensitive(True)
            self._render()
            self.status.set_text('Automatic roster is active.' if self.automatic else
                                 'Selection loaded. Check agents, then apply to update the galaxy.')
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            self.candidates, self.selection, self.default_ids = {}, set(), set()
            self.apply.set_sensitive(False)
            self.status.set_text('Could not load agent settings. Fix the source configuration, then reload.')

    def _render(self):
        child = self.items.get_first_child()
        while child:
            self.items.remove(child)
            child = self.items.get_first_child()
        self.checks = {}
        for agent, item in sorted(self.candidates.items()):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            name = 'Shared worker · black hole' if agent == 'factory-worker' else item['name']
            check = Gtk.CheckButton(label=f"{name} · {agent}")
            check.set_active(agent in self.selection)
            check.connect('toggled', self._toggled, agent)
            self.checks[agent] = check
            box.append(check)
            detail = Gtk.Label(label='; '.join(item['sources']), xalign=0, wrap=True)
            detail.add_css_class('dim-label')
            box.append(detail)
            if agent == 'factory-worker':
                box.append(Gtk.Label(label='Shared identity for clients without a named role. '
                    'Recorded activity, not a live-worker status. Fixed black hole with inward-only file lights.',
                    xalign=0, wrap=True))
            self.items.append(box)
        if self.sources:
            label = Gtk.Label(label='Detected gateways and clients', xalign=0)
            label.add_css_class('heading')
            self.items.append(label)
            for source in self.sources:
                self.items.append(Gtk.Label(label=f"{source['name']} · {source['kind']} · {source['status']}",
                                            xalign=0, wrap=True))

    def _toggled(self, check, agent):
        self.automatic = False
        if check.get_active():
            self.selection.add(agent)
        else:
            self.selection.discard(agent)
        self.status.set_text(f'{len(self.selection)} agents selected in this draft. Apply to save.')

    def _select(self, agents):
        self.automatic = False
        self.selection = set(agents)
        self._render()
        self.status.set_text(f'{len(self.selection)} agents selected in this draft. Apply to save.')

    def _automatic(self):
        self.selection = set(self.default_ids)
        self.automatic = True
        self._render()
        self.status.set_text('Draft: automatic roster includes configured agents and new active memory authors. Apply to save.')

    def _scan(self, _button):
        self.scan.set_sensitive(False)
        self.status.set_text('Checking local gateways, configured clients and shared reviewed activity…')
        try:
            process = Gio.Subprocess.new(['/usr/bin/python3', str(Path(__file__).with_name('agent_discovery.py'))],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
            def finished(proc, result):
                self.scan.set_sensitive(True)
                try:
                    _ok, output, _error = proc.communicate_utf8_finish(result)
                    if not proc.get_successful():
                        raise ValueError('Scan failed')
                    data = json.loads(output)
                    for item in data['agents']:
                        previous = self.candidates.get(item['id'])
                        if previous:
                            item['sources'] = list(dict.fromkeys(previous['sources'] + item['sources']))
                        self.candidates[item['id']] = item
                    self.sources = data['sources']
                    self._render()
                    self.status.set_text(f"Scan finished at {time.strftime('%H:%M')}. "
                                         'New discoveries are unchecked; select the ones to show. ' +
                                         ' '.join(data['warnings']))
                except (GLib.Error, ValueError, KeyError, TypeError):
                    self.status.set_text('Scan failed. Your selection is retained; try again.')
            process.communicate_utf8_async(None, None, finished)
        except GLib.Error:
            self.scan.set_sensitive(True)
            self.status.set_text('Could not start gateway discovery. Your selection is retained.')

    def _apply(self, _button):
        try:
            saved = save_agent_controls(self.config_path, None if self.automatic else sorted(self.selection), self.expected)
        except (OSError, ValueError, TypeError, RuntimeError):
            self.status.set_text('Agent selection was not saved. Settings may have changed elsewhere; reload and retry.')
            return
        self.expected = saved.get('display_agents')
        self.refresh(self.status, 'Agent selection saved. ')
