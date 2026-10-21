import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from native_activity import read_sessions, visible_sessions, overlay


class NativeActivityTests(unittest.TestCase):
    def test_metadata_discards_transcripts_and_keeps_native_owner(self):
        rows = [{'startedBy': 'mak', 'agent': 'Codex', 'folder': '/projects/demo',
                 'state': 'stopped', 'lastActive': '2026-10-20T23:00:00Z',
                 'name': 'private task title', 'answer': 'private response'}, None]
        result = read_sessions(lambda *a, **kw: SimpleNamespace(stdout=json.dumps({'harnesses': rows})))
        self.assertEqual(result, [{'author': 'mak', 'folder': '/projects/demo',
                                  'state': 'stopped', 'updated_at': '2026-10-20T23:00:00Z'}])

    def test_context_targets_do_not_become_verified_writes(self):
        scene = {'nodes': [dict(id='root:Projects', kind='Directory system', path='/projects',
                                x=0, y=0, z=0, root='Projects', color='#fff'),
                           dict(id='agent:lyra', kind='Agent', color='#fff')],
                 'links': [], 'agent_activity': [{'agent': 1, 'targets': [], 'write_targets': []}]}
        row = dict(author='lyra', folder='/projects/demo', state='stopped', updated_at='2026-10-20T23:00:00Z')
        result = overlay(scene, [row])
        self.assertEqual(result['nodes'][2]['path'], '/projects/demo')
        self.assertEqual(result['nodes'][1]['session_state'], 'stopped')
        self.assertEqual(result['agent_activity'][0]['targets'], [2])
        self.assertEqual(result['agent_activity'][0]['write_targets'], [])

    def test_private_and_outside_folders_stay_out(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good, private, outside = root/'demo', root/'private', root.parent/'elsewhere'
            good.mkdir(); private.mkdir()
            rows = [dict(author='mak', folder=str(x)) for x in [good, private, outside]]
            with patch('memory_map.SENSITIVE_SEGMENT', __import__('re').compile('private')):
                result = visible_sessions({'roots': [{'path': str(root)}]}, rows)
            self.assertEqual([x['folder'] for x in result], [str(good)])


if __name__ == '__main__':
    unittest.main()
