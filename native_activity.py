"""Read native Harness metadata only, never prompts, answers or private memory."""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time

_cache = None
_at = 0


def read_sessions(run=subprocess.run):
    global _cache, _at
    if run is subprocess.run and _cache is not None and time.monotonic() - _at < 10:
        return _cache
    result = run(['harness', 'ps', '--all', '--json'], capture_output=True, text=True,
                 timeout=10, check=True)
    if len(result.stdout) > 2_000_000:
        raise ValueError('Native session metadata exceeds limit')
    rows = json.loads(result.stdout).get('harnesses', [])
    if not isinstance(rows, list):
        raise ValueError('Invalid native session metadata')
    safe = []
    for row in rows[:1000]:
        if not isinstance(row, dict):
            continue
        owner = str(row.get('startedBy', '')).lower()
        author = owner if owner in {'lyra', 'mak', 'imagen'} else {
            'claude code': 'claude', 'openclaw': 'main', 'hermes': 'imagen',
            'codex': 'codex', 'opencode': 'opencode'}.get(str(row.get('agent', '')).lower())
        state, folder, updated = row.get('state'), row.get('folder'), row.get('lastActive')
        if (not author or not isinstance(folder, str) or not Path(folder).is_absolute()
                or state not in {'working', 'idle', 'starting', 'stopped', 'unknown', 'needs the person', 'failed', 'closed', 'gone'}
                or not isinstance(updated, str) or not re.fullmatch(r'[0-9T:Z.+-]{10,40}', updated)):
            continue
        safe.append({'author': author, 'folder': folder, 'state': state, 'updated_at': updated})
    safe.sort(key=lambda row: row['updated_at'], reverse=True)
    if run is subprocess.run:
        _cache, _at = safe, time.monotonic()
    return safe


def visible_sessions(config, rows):
    from memory_map import BLOCKED_SEGMENTS, SENSITIVE_SEGMENT
    roots = [Path(x['path']).expanduser().resolve() for x in config['roots']]
    seen, result = set(), []
    for row in rows:
        path = Path(row['folder']).resolve()
        if (not path.is_dir() or not any(path.is_relative_to(root) for root in roots)
                or any(part.lower() in BLOCKED_SEGMENTS or SENSITIVE_SEGMENT.search(part) or part.lower() == 'records'
                       for part in path.parts)):
            continue
        key = (row['author'], str(path))
        if key in seen:
            continue
        seen.add(key)
        result.append({**row, 'folder': str(path)})
    return result[:100]


def overlay(scene, rows):
    """Expose project context targets without claiming that a session wrote files."""
    nodes = scene['nodes']
    agents = {n['id'].removeprefix('agent:'): i for i, n in enumerate(nodes) if n['kind'] == 'Agent'}
    activity = {x['agent']: x for x in scene['agent_activity']}
    for row in rows:
        agent = agents.get(row['author'])
        if agent is None:
            continue
        path = Path(row['folder'])
        roots = [(i, n) for i, n in enumerate(nodes) if n['kind'] == 'Directory system'
                 and n.get('path') and path.is_relative_to(Path(n['path']))]
        if not roots:
            continue
        _, root = max(roots, key=lambda pair: len(pair[1]['path']))
        target = next((i for i, n in enumerate(nodes) if n.get('path') == str(path)), None)
        if target is None:
            phase = int(hashlib.sha256(str(path).encode()).hexdigest()[:8], 16) / 0xffffffff * math.tau
            target = len(nodes)
            nodes.append({**root, 'id': 'dir:'+str(path), 'kind': 'Remembered directory',
                          'name': path.name, 'path': str(path), 'orbit_parent': root['id'],
                          'x': root['x']+0.9*math.cos(phase), 'y': root['y']+0.9*math.sin(phase),
                          'action': 'session context', 'memory': '', 'memory_author': '', 'memory_rank': 0})
        entry = activity[agent]
        if len(entry.get('context_targets', [])) >= 7:
            continue
        entry['targets'] = list(dict.fromkeys([*entry.get('context_targets', []), target, *entry['targets']]))[:7]
        entry.setdefault('context_targets', []).append(target)
        scene['links'].append({'from': agent, 'to': target, 'color': nodes[agent]['color']})
        if 'session_state' not in nodes[agent]:
            nodes[agent].update(session_state=row['state'], session_updated_at=row['updated_at'])
        nodes[agent]['alpha'] = 0.96
    scene['source'] = 'reviewed-memory-and-native-session-metadata'
    scene['native_session_count'] = sum(row['author'] in agents for row in rows)
    return scene
