"""Folder edits preserve source identity and reject destructive/stale replacements."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from source_controls import editable_values, save_folder_controls


class FolderControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.first, self.second = self.base / 'one', self.base / 'two'
        self.first.mkdir()
        self.second.mkdir()
        self.marker = self.first / 'keep.txt'
        self.marker.write_text('preserve')
        self.path = self.base / 'sources.json'
        self.data = {'memory': {'provider': 'hindsight', 'cli': '/example/hindsight',
                               'agent': 'codex', 'project': 'Example'},
                     'roots': [{'label': 'One', 'path': str(self.first)}],
                     'custom_future_setting': {'preserve': True}}
        self.path.write_text(json.dumps(self.data))
        self.expected = copy.deepcopy(editable_values(self.data))

    def save(self, roots, **kwargs):
        return save_folder_controls(self.path, roots, kwargs.get('files', 160),
                                    kwargs.get('directories', 48), self.expected)

    def test_add_rename_remove_preserves_source_and_files(self):
        saved = self.save([{'label': 'Renamed', 'path': str(self.first)},
                           {'label': 'Two', 'path': str(self.second)}], files=32, directories=8)
        self.expected = editable_values(saved)
        saved = self.save([saved['roots'][1]], files=32, directories=8)
        self.assertEqual(saved['memory'], self.data['memory'])
        self.assertEqual(saved['custom_future_setting'], {'preserve': True})
        self.assertEqual(self.marker.read_text(), 'preserve')
        self.assertEqual(len(saved['roots']), 1)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_invalid_drafts_leave_original_bytes_unchanged(self):
        original = self.path.read_bytes()
        invalid = [[], [{'label': '', 'path': str(self.first)}],
                   [{'label': 'One', 'path': str(self.first)}, {'label': 'One', 'path': str(self.second)}],
                   [{'label': 'Missing', 'path': str(self.base / 'missing')}]]
        for roots in invalid:
            with self.subTest(roots=roots), self.assertRaises(ValueError):
                self.save(roots)
            self.assertEqual(self.path.read_bytes(), original)
        for limits in ({'files': 0}, {'files': 1001}, {'directories': 201}):
            with self.assertRaises(ValueError):
                self.save(self.data['roots'], **limits)
            self.assertEqual(self.path.read_bytes(), original)

    def test_alias_duplicate_and_galaxy_parent_are_rejected(self):
        alias = self.base / 'alias'
        alias.symlink_to(self.first)
        with self.assertRaises(ValueError):
            self.save(self.data['roots'] + [{'label': 'Alias', 'path': str(alias)}])
        self.data['galaxy'] = {'label': 'Galaxy', 'path': str(self.base)}
        self.path.write_text(json.dumps(self.data))
        with self.assertRaises(ValueError):
            self.save([{'label': 'Parent', 'path': str(self.base)}])

    def test_concurrent_source_updates_preserved_folder_conflicts_rejected(self):
        self.data['memory']['project'] = 'Other'
        self.path.write_text(json.dumps(self.data))
        saved = self.save(self.data['roots'])
        self.assertEqual(saved['memory']['project'], 'Other')
        saved['roots'][0]['label'] = 'External change'
        self.path.write_text(json.dumps(saved))
        original = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'changed elsewhere'):
            self.save(self.expected['roots'])
        self.assertEqual(self.path.read_bytes(), original)

    def test_existing_offline_mount_is_retained(self):
        self.data['roots'].append({'label': 'Offline', 'path': str(self.base / 'unmounted')})
        self.path.write_text(json.dumps(self.data))
        self.expected = editable_values(self.data)
        self.assertEqual(len(self.save(self.data['roots'])['roots']), 2)
