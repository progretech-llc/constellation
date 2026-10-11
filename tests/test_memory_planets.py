"""Optional MemPalace system checks with synthetic, non-private records."""
import importlib
import json
import os
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from mempalace_planets import MemoryPlanet, parse_list
import memory_browser
from memory_browser import render_page


class MemoryPlanetTests(unittest.TestCase):
    def test_system_requires_database_and_bounded_planet_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            configuration = base / 'sources.json'
            data = {'memory': {'provider': 'mempalace', 'cli': '/cli', 'agent': 'codex', 'project': 'Example'},
                    'roots': [{'label': 'MemPalace', 'path': str(base), 'type': 'mempalace', 'max_memories': 20}]}
            from config import load_config
            configuration.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'mempalace.db'):
                load_config(configuration)
            (base / 'mempalace.db').write_bytes(b'fixture')
            for invalid in (0, 101, True, '20'):
                data['roots'][0]['max_memories'] = invalid
                configuration.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, 'max_memories'):
                    load_config(configuration)

    def test_parser_keeps_recent_active_titles_without_interpreting_body_as_metadata(self):
        output = '''abcd1234 [project/active] First memory
  author: agent/codex
  project: Example
  Some body text

feed5678 [agent/superseded] Old memory
  author: agent/rend
  owner: rend
  Other body
'''
        rows = parse_list(output)
        self.assertEqual([(row.short_id, row.title, row.author) for row in rows],
                         [('abcd1234', 'First memory', 'codex')])

    def test_browser_view_is_read_only_escaped_and_author_scoped(self):
        selected = MemoryPlanet('abcd1234', '<script>unsafe</script>', 'codex', 'agent', 'Example',
                                'project', 'Content <private>')
        other = MemoryPlanet('feed5678', 'Rend only', 'rend', 'agent', 'Example', 'project', 'other')
        page = render_page([selected, other], selected)
        self.assertIn('&lt;script&gt;unsafe&lt;/script&gt;', page)
        self.assertIn('Content &lt;private&gt;', page)
        self.assertNotIn('Rend only', page)
        self.assertNotIn('<script>', page)

    def test_browser_serves_selected_author_only_on_loopback(self):
        selected = MemoryPlanet('abcd1234', 'Selected', 'codex', 'agent', 'Example', 'project', 'Safe details')
        other = MemoryPlanet('feed5678', 'Another author', 'rend', 'agent', 'Example', 'project', 'Other details')
        opened = queue.Queue()
        with patch.object(memory_browser, 'read_recent', return_value=[selected, other]), \
             patch.object(memory_browser.webbrowser, 'open', side_effect=opened.put):
            thread = threading.Thread(target=memory_browser.serve,
                                      args=('/fake/cli', 'codex', 'abcd1234'),
                                      kwargs={'idle_seconds': 0.4}, daemon=True)
            thread.start()
            url = opened.get(timeout=2)
            with urlopen(url, timeout=2) as response:
                page = response.read().decode()
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertIn('Safe details', page)
            self.assertNotIn('Another author', page)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def test_scene_has_configured_planets_without_raw_memory_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            palace = base / 'mempalace'
            palace.mkdir()
            (palace / 'mempalace.db').write_bytes(b'fixture')
            cli = base / 'mempalace-cli'
            cli.write_text('fixture')
            configuration = base / 'sources.json'
            configuration.write_text(json.dumps({
                'memory': {'provider': 'mempalace', 'cli': str(cli), 'agent': 'codex', 'project': 'Example'},
                'roots': [{'label': 'MemPalace', 'path': str(palace), 'type': 'mempalace', 'max_memories': 2}],
                'agents': ['codex', 'rend'], 'host_name': 'Test Host'}))
            previous = os.environ.get('CONSTELLATION_CONFIG')
            os.environ['CONSTELLATION_CONFIG'] = str(configuration)
            try:
                import config, memory_map, app, wallpaper_scene
                importlib.reload(config)
                importlib.reload(memory_map)
                importlib.reload(app)
                scene_module = importlib.reload(wallpaper_scene)
                records = [MemoryPlanet('abcd1234', 'Latest task', 'codex', 'agent', 'Example',
                                        'project', 'Never persist this body'),
                           MemoryPlanet('feed5678', 'Earlier task', 'unknown', 'agent', 'Example',
                                        'project', 'Another private body')]
                with patch.object(scene_module, 'read_activities', return_value=[]), \
                     patch.object(scene_module, 'read_recent', return_value=records) as read:
                    scene = scene_module.make_scene()
                read.assert_called_once_with(str(cli), 'codex', 2)
                planets = [node for node in scene['nodes'] if node['kind'] == 'Memory planet']
                self.assertEqual(len(planets), 2)
                self.assertEqual(planets[0]['name'], 'Latest task')
                self.assertEqual(planets[0]['orbit_parent'], 'root:MemPalace')
                self.assertEqual(planets[0]['color'], app._agent_color('codex'))
                self.assertEqual(planets[1]['color'], app.ROOT_COLORS['MemPalace'])
                self.assertNotIn('Never persist this body', json.dumps(scene))
            finally:
                if previous is None:
                    os.environ.pop('CONSTELLATION_CONFIG', None)
                else:
                    os.environ['CONSTELLATION_CONFIG'] = previous


if __name__ == '__main__':
    unittest.main()
