"""Navigation metadata and exact Hindsight lookup checks."""

import importlib.util
import os
import tempfile
import json
import queue
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch


VIEWER = Path(__file__).resolve().parents[1] / 'gnome-extension' / 'memory_viewer.py'
spec = importlib.util.spec_from_file_location('memory_viewer', VIEWER)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class MemoryNavigationTests(unittest.TestCase):
    def test_api_planet_browser_opens_exact_shared_record_and_keeps_author_boundary(self):
        from memory_browser import serve
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / 'sources.json'
            config.write_text(json.dumps({'memory': {'provider': 'hindsight-api',
                'api_url': 'http://127.0.0.1:8888', 'bank_id': 'shared'},
                'roots': [{'label': 'Project', 'path': str(root)}]}))
            records = [{'memory_id': key, 'title': title, 'author': author, 'project': 'Example',
                        'technical_steps': [], 'evidence': []} for key, title, author in
                       [('exact-id', '<Reviewed shared memory>', 'worker'),
                        ('other-id', 'Other author', 'other')]]
            opened = queue.Queue()
            with patch('hindsight_api.read_shared_documents', return_value=records) as read, \
                 patch('memory_browser.webbrowser.open', side_effect=opened.put):
                thread = threading.Thread(target=serve, args=('', '', 'exact-id'),
                    kwargs={'api_config': config, 'idle_seconds': 0.5}, daemon=True)
                thread.start()
                try:
                    url = opened.get(timeout=3)
                    with urlopen(url, timeout=3) as response:
                        body = response.read().decode()
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                        self.assertIn('&lt;Reviewed shared memory&gt;', body)
                        self.assertNotIn('Other author', body)
                    with self.assertRaises(HTTPError) as rejected:
                        urlopen(url.replace('exact-id', 'other-id'), timeout=3)
                    self.assertEqual(rejected.exception.code, 404)
                    rejected.exception.close()
                    read.assert_called_once()
                finally:
                    thread.join(timeout=3)
                self.assertFalse(thread.is_alive())

    def test_short_id_resolves_exact_record_before_show(self):
        with tempfile.TemporaryDirectory() as temp:
            cli = Path(temp) / 'fake-hindsight'
            cli.write_text('''#!/usr/bin/env python3
import sys
if '--json' in sys.argv:
    import json
    print(json.dumps({'memory_id':'a1b2c3d4-1111-2222-3333-444444444444','scope':'project','project_id':'ProgreTech'}))
elif 'show' in sys.argv:
    print('Reviewed activity content')
''')
            cli.chmod(0o700)
            full_id, text = viewer.read_memory(str(cli), 'codex', 'ProgreTech', 'a1b2c3d4')
            self.assertEqual(full_id, 'a1b2c3d4-1111-2222-3333-444444444444')
            self.assertIn('Reviewed activity', text)

    def test_private_records_do_not_become_planets(self):
        from hindsight_planets import parse_list
        text='a1b2c3d4 [agent/active] Private note\n  author: agent/rend\n  owner: rend\n'
        self.assertEqual(parse_list(text),[])

    def test_ambiguous_or_invalid_memory_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            viewer.resolve_memory_id('/unused', 'codex', 'ProgreTech', 'not-an-id')


if __name__ == '__main__':
    unittest.main()
