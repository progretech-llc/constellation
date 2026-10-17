"""Recommendations rank reviewed activity without content scans or source writes."""
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.galaxy = self.base / 'galaxy'
        self.galaxy.mkdir()
        self.config = {'memory': {'provider': 'json', 'directory': str(self.base / 'memory')},
                       'roots': [{'label': 'Galaxy child', 'path': str(self.galaxy / 'existing')}],
                       'galaxy': {'label': 'Galaxy', 'path': str(self.galaxy)}, 'agents': ['worker', 'codex']}
        path = self.base / 'sources.json'
        path.write_text(json.dumps(self.config))
        previous = os.environ.get('CONSTELLATION_CONFIG')
        os.environ['CONSTELLATION_CONFIG'] = str(path)
        self.addCleanup(lambda: os.environ.pop('CONSTELLATION_CONFIG', None) if previous is None else os.environ.__setitem__('CONSTELLATION_CONFIG', previous))
        import config, memory_map
        importlib.reload(config)
        self.memory_map = importlib.reload(memory_map)
        import folder_recommendations
        self.recommend = importlib.reload(folder_recommendations).recommend_folders

    def activity(self, key, paths, author='worker'):
        return self.memory_map.Activity(key, author, 'Example', [f'Modified "{p}"' for p in paths], [str(p) for p in paths])

    def test_top_five_count_distinct_activities_group_repo_and_keep_unconfigured_folders(self):
        activities = []
        for index in range(7):
            folder = self.galaxy / f'repo{index}'
            (folder / '.git').mkdir(parents=True)
            (folder / 'src').mkdir()
            file = folder / 'src' / 'main.py'
            file.write_text('example')
            for count in range(index + 1):
                activities.append(self.activity(f'{index}-{count}', [file, file]))
        before = json.dumps(self.config)
        result = self.recommend(activities, self.config, home=self.base / 'home')
        self.assertEqual([x['label'] for x in result], ['repo6', 'repo5', 'repo4', 'repo3', 'repo2'])
        self.assertEqual(result[0]['activity_count'], 7)
        self.assertEqual(result[0]['agents'], ['worker'])
        self.assertEqual(json.dumps(self.config), before)

    def test_sensitive_missing_private_and_symlink_paths_excluded(self):
        blocked = self.galaxy / 'credentials'
        blocked.mkdir()
        secret = blocked / 'example.txt'
        secret.write_text('synthetic')
        alias = self.galaxy / 'alias.txt'
        alias.symlink_to(secret)
        activities = [self.activity('one', [secret, alias, self.galaxy / 'missing', self.galaxy])]
        self.assertEqual(self.recommend(activities, self.config, home=self.base / 'home'), [])

    def test_spaces_distinct_agents_ties_and_unknown_author_filter(self):
        first = self.galaxy / 'First folder'
        second = self.galaxy / 'Second'
        first.mkdir()
        second.mkdir()
        events = [self.activity('one', [second]), self.activity('two', [first]),
                  self.activity('three', [first], 'codex'), self.activity('four', [second]),
                  self.activity('ignore', [second], 'unconfigured')]
        result = self.recommend(events, self.config, home=self.base / 'home')
        self.assertEqual(result[0]['path'], str(first))
        self.assertEqual(result[0]['activity_count'], 2)
        self.assertEqual(result[0]['agents'], ['codex', 'worker'])
        self.assertEqual(result[1]['activity_count'], 2)

    def test_duplicate_records_count_once_and_missing_source_is_an_error(self):
        folder = self.galaxy / 'Projects'
        folder.mkdir()
        activity = self.activity('one', [folder])
        result = self.recommend([activity, activity], self.config, home=self.base / 'home')
        self.assertEqual(result[0]['activity_count'], 1)
        with self.assertRaises(RuntimeError):
            self.memory_map.read_activities()
