"""User-owned Constellation source configuration; no factory paths are built in."""
from __future__ import annotations

import json
import os
import socket
import re
from pathlib import Path

CONFIG_PATH = Path(os.environ.get('CONSTELLATION_CONFIG', Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'constellation' / 'sources.json'))


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.is_file():
        raise RuntimeError(f'Missing source configuration: {path}. Run ./install-user.sh or copy config.example.json.')
    data = json.loads(path.read_text())
    memory = data.get('memory', {})
    if 'ui_url' in memory:
        from hindsight_api import validate_web_url
        validate_web_url(memory['ui_url'])
    if memory.get('provider')=='mempalace':
        memory['provider']='hindsight'
        if str(memory.get('cli','')).endswith('/mempalace'):memory['cli']=str(memory['cli'])[:-9]+'hindsight'
    if memory.get('provider') not in {'json', 'hindsight', 'hindsight-api'}:
        raise ValueError('memory.provider must be json, hindsight or hindsight-api')
    if memory['provider'] == 'hindsight-api':
        from hindsight_api import validate_source
        validate_source(memory)
    if memory['provider'] == 'json' and not memory.get('directory'):
        raise ValueError('memory.directory is required for json provider')
    if memory['provider'] == 'hindsight' and not all(memory.get(key) for key in ('cli', 'agent', 'project')):
        raise ValueError('memory.cli, memory.agent and memory.project are required for hindsight provider')
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
    data.setdefault('host_name', socket.gethostname())
    if not isinstance(data['host_name'], str) or not data['host_name'].strip() or len(data['host_name']) > 80:
        raise ValueError('host_name must be 1 to 80 characters')
    galaxy = data.get('galaxy')
    if galaxy is not None and (not isinstance(galaxy, dict) or
            not isinstance(galaxy.get('label'), str) or not galaxy['label'].strip() or
            not isinstance(galaxy.get('path'), str) or not Path(galaxy['path']).expanduser().is_absolute()):
        raise ValueError('galaxy needs a nonempty label and absolute directory path')
    if galaxy and any(Path(entry['path']).expanduser() == Path(galaxy['path']).expanduser() for entry in roots):
        raise ValueError('Choose child directories as solar-system roots instead of repeating the galaxy path')
    data.setdefault('center_agent', '')  # accepted for older configurations; no agent is fixed at center
    data.setdefault('agents', [])
    aliases = data.setdefault('agent_aliases', {})
    fallback = data.setdefault('unlisted_agent', '')
    if not isinstance(data['agents'], list) or any(not isinstance(agent, str) or not agent for agent in data['agents']):
        raise ValueError('agents must be a list of nonempty agent IDs')
    if not isinstance(aliases, dict) or any(not isinstance(old, str) or not old or not isinstance(new, str) or not new for old, new in aliases.items()):
        raise ValueError('agent_aliases must map nonempty agent IDs to nonempty agent IDs')
    if not isinstance(fallback, str) or (fallback and (not data['agents'] or fallback not in data['agents'])):
        raise ValueError('unlisted_agent must be one of the configured agents')
    selected = data.get('display_agents')
    if selected is not None and (not isinstance(selected, list) or len(selected) > 100 or
            any(not isinstance(agent, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}', agent)
                for agent in selected) or len(selected) != len(set(selected))):
        raise ValueError('display_agents must be null or up to 100 unique agent IDs')
    memory_node = data.get('memory_node')
    if memory_node is not None:
        if (not isinstance(memory_node, dict) or
                memory_node.get('provider') not in {'hindsight', 'mem0', 'zep', 'chroma', 'qdrant', 'letta'} or
                not isinstance(memory_node.get('path', ''), str) or
                (memory_node.get('path') and not Path(memory_node['path']).is_absolute())):
            raise ValueError('memory_node must name one supported provider and an optional absolute path')
    if type(data.get('native_harness', False)) is not bool:
        raise ValueError('native_harness must be a boolean')
    if type(data.get('discover_agents', False)) is not bool:
        raise ValueError('discover_agents must be a boolean')
    if data.get('discover_agents'):
        from agent_discovery import discover
        found = discover(data, include_history=False, probe_runtime=False)
        data['agents'] = [item['id'] for item in found['agents']]
        if data.get('display_agents') is not None:
            data['display_agents'] = [agent for agent in data['display_agents'] if agent in data['agents']]
        if data.get('unlisted_agent') not in data['agents']:
            data['unlisted_agent'] = ''
    return data


def root_entries(config: dict) -> tuple[tuple[str, Path], ...]:
    return tuple((item['label'], Path(item['path']).expanduser()) for item in config['roots'])
