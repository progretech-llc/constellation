"""End-to-end source checks using a disposable, synthetic activity directory."""
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ConfiguredSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'Projects'
        self.root.mkdir()
        self.file = self.root / 'report.md'
        self.file.write_text('test')
        self.memory = self.base / 'memory'
        self.memory.mkdir()
        self.config = self.base / 'sources.json'
        os.environ['CONSTELLATION_CONFIG'] = str(self.config)
        self.config.write_text(json.dumps({
            'memory': {'provider': 'json', 'directory': str(self.memory)},
            'roots': [{'label': 'Projects', 'path': str(self.root)}],
            'host_name': 'Test Workstation', 'galaxy': {'label': 'Test galaxy', 'path': str(self.base)},
            'center_agent': 'lead', 'agents': ['lead', 'worker']
        }))
        import config
        import memory_map
        importlib.reload(config)
        self.map = importlib.reload(memory_map)

    def tearDown(self):
        os.environ.pop('CONSTELLATION_CONFIG', None)
        self.temp.cleanup()

    def test_json_activity_creates_one_file_and_agent_link(self):
        (self.memory / '001.json').write_text(json.dumps({
            'memory_id': 'reviewed-1', 'author': 'worker', 'project': 'Example',
            'technical_steps': [f'Created {self.file}'], 'evidence': [str(self.file)]
        }))
        activities = self.map.read_activities()
        files, agents = self.map.build_catalog(activities)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].agents['worker'], 'created')
        self.assertEqual(agents, ['worker'])
        self.assertEqual(self.map.recent_links(files, agents)[0][1], str(self.file))

    def test_host_is_center_and_agents_link_to_remembered_files(self):
        activities = [self.map.Activity('reviewed-1', 'worker', 'Example', [f'Created {self.file}'])]
        files, agents = self.map.build_catalog(activities)
        import app
        app = importlib.reload(app)
        nodes, _, links, _ = app._build_scene(files, agents)
        by_id = {key: index for index, key in enumerate(nodes['id'])}
        self.assertEqual(nodes['kind'][by_id['host']], 'Host')
        self.assertEqual(nodes['name'][by_id['host']], 'Test Workstation')
        self.assertEqual(nodes['path'][by_id['host']], str(self.base))
        self.assertEqual(nodes['orbit_parent'][by_id['root:Projects']], 'host')
        self.assertEqual(nodes['orbit_parent'][by_id['agent:worker']], 'host')
        self.assertEqual(nodes['orbit_parent'][by_id['file:' + str(self.file)]], 'root:Projects')
        self.assertEqual(links['source_idx'], [by_id['agent:worker']])
        self.assertEqual(links['target_idx'], [by_id['file:' + str(self.file)]])
        (self.memory / '001.json').write_text(json.dumps({
            'memory_id': 'reviewed-1', 'author': 'worker', 'project': 'Example',
            'technical_steps': [f'Created {self.file}'], 'evidence': []
        }))
        import wallpaper_scene
        scene = importlib.reload(wallpaper_scene).make_scene()
        self.assertEqual(scene['galaxy'], {'label': 'Test galaxy', 'path': str(self.base)})
        self.assertEqual(scene['nodes'][0]['name'], 'Test Workstation')
        self.assertEqual(scene['links'][0]['from'], by_id['agent:worker'])

    def test_outside_root_and_sensitive_paths_are_excluded(self):
        outside = self.base / 'outside.md'
        outside.write_text('private')
        secret_dir = self.root / '.ssh'
        secret_dir.mkdir()
        secret = secret_dir / 'id_rsa'
        secret.write_text('do not read')
        self.assertEqual(self.map._paths(f'Opened {outside}'), [])
        self.assertEqual(self.map._paths(f'Opened {secret}'), [])

    def test_only_reviewed_hindsight_activity_is_parsed(self):
        self.map.MEMORY['project'] = 'Example'
        output = '''a1b2c3d4 [project/active] Activity: example
  author: agent/worker
  project: Example
  provenance_type: structured-agent-activity
  Technical steps:
- Created /tmp/report.md
  Evidence:
- /tmp/report.md
'''
        self.assertEqual(len(self.map._parse_cli_output(output)), 1)
        self.assertEqual(self.map._parse_cli_output(output.replace('structured-agent-activity', 'other')), [])
        self.assertEqual(self.map._parse_cli_output(output.replace('  provenance_type: structured-agent-activity\n', '')), [])

    def test_hindsight_uses_configured_identity_and_project(self):
        self.map.MEMORY.update({'provider': 'hindsight', 'cli': '/example/hindsight',
                                'agent': 'my-agent', 'project': 'Example'})
        output = '''a1b2c3d4 [project/active] Activity: example
  author: agent/worker
  project: Example
  provenance_type: structured-agent-activity
  Technical steps:
- Created /tmp/report.md
  Evidence:
- /tmp/report.md
'''
        with patch.object(self.map.subprocess, 'run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = output
            activities = self.map.read_activities()
        self.assertEqual(len(activities), 1)
        self.assertEqual(run.call_args_list[0].args[0][:4], ['/example/hindsight', '--agent', 'my-agent', 'list'])
        self.assertIn('Example', run.call_args_list[1].args[0])

    def test_file_cap_replaces_older_nodes(self):
        second = self.root / 'second.md'
        second.write_text('test')
        self.map.MAX_FILES = 1
        activities = [self.map.Activity('new', 'worker', 'Example', [f'Created {self.file}']),
                      self.map.Activity('old', 'worker', 'Example', [f'Created {second}'])]
        files, _ = self.map.build_catalog(activities)
        self.assertEqual([item.path for item in files], [str(self.file)])

    def test_retired_authors_can_share_one_display_node_without_rewriting_memory(self):
        self.map.CONFIG['agent_aliases'] = {'old-designer': 'worker'}
        self.map.CONFIG['unlisted_agent'] = 'worker'
        activities = [self.map.Activity('legacy-1', 'old-designer', 'Example', [f'Modified {self.file}']),
                      self.map.Activity('legacy-2', 'unknown-old-role', 'Example', [f'Opened {self.file}'])]
        files, agents = self.map.build_catalog(activities)
        self.assertEqual([activity.author for activity in activities], ['old-designer', 'unknown-old-role'])
        self.assertEqual(agents, ['worker'])
        self.assertEqual(files[0].agents, {'worker': 'modified'})
        self.assertEqual(files[0].memory_ids, ['legacy-1', 'legacy-2'])


if __name__ == '__main__':
    unittest.main()
