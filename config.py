"""User-owned Constellation source configuration; no factory paths are built in."""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path(os.environ.get('CONSTELLATION_CONFIG', Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'constellation' / 'sources.json'))


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.is_file():
        raise RuntimeError(f'Missing source configuration: {path}. Run ./install-user.sh or copy config.example.json.')
    data = json.loads(path.read_text())
    memory = data.get('memory', {})
    if memory.get('provider') not in {'json', 'mempalace'}:
        raise ValueError('memory.provider must be json or mempalace')
    if memory['provider'] == 'json' and not memory.get('directory'):
        raise ValueError('memory.directory is required for json provider')
    if memory['provider'] == 'mempalace' and not all(memory.get(key) for key in ('cli', 'agent', 'project')):
        raise ValueError('memory.cli, memory.agent and memory.project are required for mempalace provider')
    roots = data.get('roots', [])
    if not isinstance(roots, list) or not 1 <= len(roots) <= 12:
        raise ValueError('Configure 1 to 12 directory roots')
    labels = set()
    for entry in roots:
        if not isinstance(entry, dict) or not isinstance(entry.get('label'), str) or not entry.get('path'):
            raise ValueError('Each root needs label and path')
        if entry['label'] in labels or not Path(entry['path']).expanduser().is_absolute():
            raise ValueError('Root labels must be unique and paths absolute')
        labels.add(entry['label'])
    data.setdefault('center_agent', '')
    data.setdefault('agents', [])
    aliases = data.setdefault('agent_aliases', {})
    fallback = data.setdefault('unlisted_agent', '')
    if not isinstance(data['agents'], list) or any(not isinstance(agent, str) or not agent for agent in data['agents']):
        raise ValueError('agents must be a list of nonempty agent IDs')
    if not isinstance(aliases, dict) or any(not isinstance(old, str) or not old or not isinstance(new, str) or not new for old, new in aliases.items()):
        raise ValueError('agent_aliases must map nonempty agent IDs to nonempty agent IDs')
    if not isinstance(fallback, str) or (fallback and (not data['agents'] or fallback not in data['agents'])):
        raise ValueError('unlisted_agent must be one of the configured agents')
    return data


def root_entries(config: dict) -> tuple[tuple[str, Path], ...]:
    return tuple((item['label'], Path(item['path']).expanduser()) for item in config['roots'])
