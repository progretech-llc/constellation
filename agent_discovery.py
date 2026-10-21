"""Bounded local metadata discovery. Never connect to a gateway or start an agent."""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from config import load_config

AGENT_ID = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}')
MAX_CONFIG_BYTES = 1_000_000
CLIENTS = (
    ('Hermes', 'hermes', '.hermes/config.yaml'),
    ('Goose', 'goose', '.config/goose/config.yaml'),
    ('OpenCode', 'opencode', '.config/opencode/opencode.json'),
    ('Codex', 'codex', '.codex/config.toml'),
    ('Claude Code', 'claude', '.claude.json'),
)


def valid_id(value) -> bool:
    return isinstance(value, str) and AGENT_ID.fullmatch(value) is not None


def read_client_config(path: Path) -> dict:
    if path.stat().st_size > MAX_CONFIG_BYTES:
        raise ValueError('Configuration exceeds discovery size limit')
    text = path.read_text()
    if path.suffix == '.json':
        data = json.loads(text)
    elif path.suffix == '.toml':
        import tomllib
        data = tomllib.loads(text)
    else:
        import yaml
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise ValueError('Invalid YAML configuration') from error
    if not isinstance(data, dict):
        raise ValueError('Invalid configuration object')
    return data


def memory_bindings(data: dict) -> list[dict]:
    """Extract only explicit factory-memory MCP identities; discard all other fields."""
    found = []
    for group in ('mcp_servers', 'mcpServers', 'mcp', 'extensions'):
        entries = data.get(group, {})
        if not isinstance(entries, dict):
            continue
        for server in list(entries.values())[:100]:
            if not isinstance(server, dict) or server.get('enabled') is False:
                continue
            command = server.get('command', server.get('cmd', []))
            if isinstance(command, str):
                command = shlex.split(command)
            args = server.get('args', [])
            if not isinstance(command, list) or not isinstance(args, list):
                continue
            argv = command + args
            if not all(isinstance(arg, str) for arg in argv) or not argv:
                continue
            if Path(argv[0]).name != 'factory-memory-mcp':
                continue
            if '--agent' not in argv or argv.index('--agent') + 1 >= len(argv):
                continue
            agent = argv[argv.index('--agent') + 1]
            if not valid_id(agent):
                continue
            project = ''
            if '--project' in argv and argv.index('--project') + 1 < len(argv):
                candidate = argv[argv.index('--project') + 1]
                if valid_id(candidate):
                    project = candidate
            item = {'id': agent, 'project': project}
            if item not in found:
                found.append(item)
    return found


def configured_candidates(config: dict, scene: dict | None = None) -> list[dict]:
    agents = {}
    if config.get('discover_agents'):
        return [{'id': agent, 'name': agent.replace('-', ' ').title(), 'sources': ['Current installation']} for agent in config.get('agents', [])]
    for agent in [*config.get('agents', []), *(config.get('display_agents') or []),
                  *(scene or {}).get('available_agents', [])]:
        if valid_id(agent):
            agents[agent] = {'id': agent, 'name': agent.replace('-', ' ').title(), 'sources': ['Saved configuration']}
    for node in (scene or {}).get('nodes', [])[:5000]:
        if node.get('kind') != 'Agent' or not str(node.get('id', '')).startswith('agent:'):
            continue
        agent = node['id'].removeprefix('agent:')
        if valid_id(agent):
            item = agents.setdefault(agent, {'id': agent, 'name': str(node.get('name', agent))[:80], 'sources': []})
            item['sources'].append('Current galaxy')
    return list(agents.values())


def discover(config: dict, *, home: Path | None = None, run=subprocess.run,
             which=shutil.which, activity_reader=None, include_history=None, probe_runtime=True) -> dict:
    home = home or Path.home()
    if include_history is None:
        include_history = not config.get('discover_agents', False)
    candidates = {item['id']: item for item in configured_candidates(config)} if include_history else {}
    sources, warnings = [], []

    def add(agent, name, source):
        agent = config.get('agent_aliases', {}).get(agent, agent)
        if not valid_id(agent):
            return
        item = candidates.setdefault(agent, {'id': agent, 'name': name[:80], 'sources': []})
        if source not in item['sources']:
            item['sources'].append(source)

    if config.get('native_harness'):
        try:
            from native_activity import read_sessions
            for row in read_sessions(run=run):
                add(row['author'], row['author'].title(), 'Native Harness · recorded owner')
        except (OSError, ValueError, subprocess.SubprocessError):
            warnings.append('Native Harness metadata unavailable; other sources were still checked.')

    # List service metadata only. No environments, command lines, ports or tokens.
    services = {}
    try:
        if not probe_runtime:
            raise OSError()
        result = run(['systemctl', '--user', 'list-units', '--type=service', '--all', '--output=json', '--no-pager'],
                     capture_output=True, text=True, timeout=5, check=True)
        for unit in json.loads(result.stdout):
            name = unit.get('unit', '')
            if re.fullmatch(r'[a-zA-Z0-9@_.-]{1,160}\.service', name) and 'gateway' in name.lower():
                state = 'running' if unit.get('active') == 'active' and unit.get('sub') == 'running' else 'not running'
                services[name] = state
                sources.append({'name': name, 'kind': 'gateway service', 'status': state})
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        if probe_runtime: warnings.append('Local service status unavailable.')

    # Desktop launches need not have the gateway CLI on PATH. Read roster
    # metadata only, never sessions, memory stores or credential fields.
    openclaw_config = home / '.openclaw/openclaw.json'
    if openclaw_config.is_file():
        try:
            data = read_client_config(openclaw_config).get('agents', {})
            entries = data.get('entries', data.get('list', []))
            if not entries and 'entries' not in data and 'list' not in data:
                entries = [{'id': 'main', 'name': 'OpenClaw'}]
            if isinstance(entries, dict):
                entries = [{**value, 'id': key} for key, value in list(entries.items())[:100]
                           if isinstance(value, dict)]
            if not isinstance(entries, list):
                raise ValueError('Invalid OpenClaw roster')
            for entry in entries[:100]:
                if isinstance(entry, dict) and valid_id(entry.get('id')):
                    add(entry['id'], str(entry.get('name') or entry['id']).replace('-', ' ').title(),
                        'OpenClaw · configured agent')
            sources.append({'name': 'OpenClaw', 'kind': 'agent roster',
                            'status': f'{len(entries)} configured agents · local metadata'})
        except (OSError, ValueError, TypeError, AttributeError):
            warnings.append('OpenClaw roster metadata unavailable.')

    profiles = home / '.hermes/profiles'
    profile_count = 0
    if profiles.is_dir():
        try:
            for profile in sorted(profiles.iterdir())[:100]:
                if valid_id(profile.name) and profile.is_dir() and (profile / 'config.yaml').is_file():
                    add(profile.name, profile.name.replace('-', ' ').title(), 'Hermes · configured profile')
                    profile_count += 1
            sources.append({'name': 'Hermes profiles', 'kind': 'agent roster',
                            'status': f'{profile_count} configured profiles · not live-agent status'})
        except OSError:
            warnings.append('Hermes profile metadata unavailable.')

    if probe_runtime and which('openclaw'):
        try:
            result = run(['openclaw', 'agents', 'list', '--json'], capture_output=True, text=True,
                         timeout=25, check=True)
            roster = json.loads(result.stdout)
            if not isinstance(roster, list):
                raise ValueError('Invalid roster')
            for entry in roster[:100]:
                agent = entry.get('id')
                if not valid_id(agent):
                    continue
                name = str(entry.get('identityName') or entry.get('name') or agent)[:80]
                # OpenClaw's default ID can differ from its known shared identity.
                # Only reconcile a name already present in the saved roster.
                if agent == 'main' and name.lower() in config.get('agents', []):
                    agent = name.lower()
                add(agent, name, 'OpenClaw · configured agent')
            sources.append({'name': 'OpenClaw', 'kind': 'agent roster',
                            'status': f'{len(roster)} configured agents'})
        except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
            warnings.append('OpenClaw roster unavailable; other sources were still checked.')

    for name, executable, relative in CLIENTS:
        path = home / relative
        if not include_history and not which(executable):
            continue
        if not which(executable) and not path.is_file():
            continue
        bindings = []
        status = 'installed client; no explicit display identity found'
        if name == 'Hermes' and profile_count:
            status = f'{profile_count} configured profiles discovered'
        if path.is_file():
            try:
                bindings = memory_bindings(read_client_config(path))
            except (OSError, ValueError, TypeError, ImportError):
                status = 'client found; identity configuration unavailable'
                warnings.append(f'{name} identity metadata could not be read.')
        if not include_history and path.is_file() and name in {'Codex', 'OpenCode', 'Claude Code'} and not bindings:
            add(executable, name, f'{name} · configured client')
        if bindings:
            status = 'configured client; shared-memory identity found'
            for binding in bindings:
                detail = f"{name} · configured client"
                if binding['project']:
                    detail += f" · {binding['project']}"
                add(binding['id'], binding['id'].replace('-', ' ').title(), detail)
        sources.append({'name': name, 'kind': 'local client', 'status': status})

    try:
        if not include_history:
            return {'agents': sorted(candidates.values(), key=lambda item: item['id']), 'sources': sources, 'warnings': warnings}
        if activity_reader is None:
            from memory_map import read_activities
            activity_reader = read_activities
        activities = activity_reader()
        for activity in activities[:2000]:
            add(activity.author, activity.author.replace('-', ' ').title(), 'Reviewed activity · configured memory source')
        sources.append({'name': 'Shared reviewed memory', 'kind': 'recorded activity',
                        'status': f'{len(activities)} activities checked'})
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        warnings.append('Reviewed activity unavailable; configured agents remain selectable.')
    return {'agents': sorted(candidates.values(), key=lambda item: item['id']),
            'sources': sources, 'warnings': warnings}


if __name__ == '__main__':
    print(json.dumps(discover(load_config())))
