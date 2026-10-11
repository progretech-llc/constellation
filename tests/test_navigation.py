"""Navigation metadata and exact MemPalace lookup checks."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


VIEWER = Path(__file__).resolve().parents[1] / 'gnome-extension' / 'memory_viewer.py'
spec = importlib.util.spec_from_file_location('memory_viewer', VIEWER)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class MemoryNavigationTests(unittest.TestCase):
    def test_short_id_resolves_exact_record_before_show(self):
        with tempfile.TemporaryDirectory() as temp:
            cli = Path(temp) / 'fake-mempalace'
            cli.write_text('''#!/usr/bin/env python3
import sys
if 'context' in sys.argv:
    print('[MEMORY a1b2c3d4-1111-2222-3333-444444444444]')
elif 'show' in sys.argv:
    print('Reviewed activity content')
''')
            cli.chmod(0o700)
            full_id, text = viewer.read_memory(str(cli), 'codex', 'ProgreTech', 'a1b2c3d4')
            self.assertEqual(full_id, 'a1b2c3d4-1111-2222-3333-444444444444')
            self.assertIn('Reviewed activity', text)

    def test_ambiguous_or_invalid_memory_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            viewer.resolve_memory_id('/unused', 'codex', 'ProgreTech', 'not-an-id')


if __name__ == '__main__':
    unittest.main()
