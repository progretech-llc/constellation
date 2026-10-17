#!/usr/bin/env python3
"""Export a bounded, local wallpaper scene from shared reviewed activity."""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
import time
from pathlib import Path

from app import _build_scene, _project, ROOT_COLORS, AGENT_COLORS
from memory_map import CONFIG, ROOTS, build_catalog, read_activities, _display_agent
from hindsight_planets import read_recent, validate_directory
from config import CONFIG_PATH
from memory_discovery import PROVIDERS


STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
SCENE_PATH = STATE_HOME / "factory-observatory" / "scene.json"
SETTINGS_PATH = Path.home() / '.config/factory-observatory/wallpaper.json'


def agent_movement_metadata(files: list, nodes: dict) -> list[dict]:
    """Per-agent chronology from the bounded visible catalog, independent of legacy links."""
    indices = {key: index for index, key in enumerate(nodes['id'])}
    files = [item for item in files if 'file:' + item.path in indices]
    result = []
    for key, agent_index in indices.items():
        if not key.startswith('agent:'):
            continue
        agent = key.removeprefix('agent:')
        touched = sorted((item for item in files if agent in item.agent_ranks),
                         key=lambda item: (item.agent_ranks[agent], item.path))
        written = sorted((item for item in files if agent in item.agent_write_ranks),
                         key=lambda item: (item.agent_write_ranks[agent], item.path))
        last_root = written[0].root if written else None
        modified_targets = []
        for item in [item for item in written if item.root == last_root][:7]:
            file_index = indices['file:' + item.path]
            modified_targets.append(file_index)
            parent = nodes.get('orbit_parent', [''] * len(nodes['id']))[file_index]
            if parent.startswith('dir:') and parent in indices:
                modified_targets.append(indices[parent])
        result.append({'agent': agent_index,
                       'targets': [indices['file:' + item.path] for item in touched[:7]],
                       'write_targets': [indices['file:' + item.path] for item in written[:7]],
                       'last_modified_root': indices.get('root:' + last_root) if last_root else None,
                       'modified_targets': list(dict.fromkeys(modified_targets))})
    return result


def prepare_memory_node(nodes: dict, links: dict, config: dict) -> tuple[str, Path | None] | None:
    """Replace the legacy memory slot, never the activity provider or its records."""
    selection = config.get('memory_node')
    if selection is None:
        existing = next(((root['label'], Path(root['path']).expanduser()) for root in config['roots']
                         if root['label'] == 'Hindsight'), None)
        if not existing and config['memory']['provider'] not in {'hindsight', 'hindsight-api'}:
            return None
        path = str(existing[1]) if existing else ''
        cli = Path(config['memory'].get('cli', '')).expanduser()
        if not path and cli.is_file():
            path = next((str(parent) for parent in list(cli.resolve().parents)[:4]
                         if (parent / 'config/client.json').is_file()), '')
        selection = {'provider': 'hindsight', 'path': path}
    provider = selection['provider']
    label = PROVIDERS[provider]
    legacy = [i for i, kind in enumerate(nodes['kind'])
              if kind == 'Directory system' and nodes['root'][i] in {'Hindsight', 'MemPalace'}]
    xyz = tuple(nodes[key][legacy[0]] for key in ('bx', 'by', 'bz')) if legacy else (0, -4.5, 0)
    if provider == 'hindsight' and len(legacy) == 1 and nodes['root'][legacy[0]] == 'Hindsight':
        index = legacy[0]
        path = selection.get('path') or nodes['path'][index]
        nodes['path'][index] = path
        return 'Hindsight', Path(path) if path else None
    removed = {i for i, root in enumerate(nodes['root']) if root in {'Hindsight', 'MemPalace'}}
    retained = [i for i in range(len(nodes['id'])) if i not in removed]
    remap = {old: new for new, old in enumerate(retained)}
    kept_links = [i for i, (source, target) in enumerate(zip(links['source_idx'], links['target_idx']))
                  if source in remap and target in remap]
    for key in nodes:
        nodes[key] = [nodes[key][i] for i in retained]
    for key in links:
        links[key] = [links[key][i] for i in kept_links]
    links['source_idx'] = [remap[index] for index in links['source_idx']]
    links['target_idx'] = [remap[index] for index in links['target_idx']]
    px, py, depth = _project(*xyz, 0.35)
    values = {'id': 'root:Hindsight' if provider == 'hindsight' else 'memory-system:' + provider,
              'orbit_parent': 'host', 'x': px, 'y': py, 'depth': depth,
              'bx': xyz[0], 'by': xyz[1], 'bz': xyz[2], 'size': 19, 'color': '#a18dff', 'alpha': 0.92,
              'name': label if provider == 'hindsight' else label + ' · system',
              'kind': 'Directory system', 'detail': 'Selected memory system', 'action': '', 'memory': '',
              'path': selection.get('path', ''), 'root': label, 'memory_project': ''}
    for key in nodes:
        nodes[key].append(values[key])
    path = selection.get('path', '')
    return ('Hindsight', Path(path)) if provider == 'hindsight' and path else None


def add_memory_planets(nodes: dict, links: dict, memory_root=None) -> dict[str, str]:
    if CONFIG['memory']['provider'] != 'hindsight':return {}
    if (CONFIG.get('memory_node') or {}).get('provider', 'hindsight') != 'hindsight':
        return {}
    root = memory_root or next(((label, path) for label, path in ROOTS if label == 'Hindsight'), None)
    if root is None:
        return {}
    if root[1] is None:
        return {}
    try:
        count = int(json.loads(SETTINGS_PATH.read_text()).get('memory_planets', 20))
    except (OSError, ValueError, TypeError):
        count = 20
    count = max(1, min(100, count))
    records = read_recent(str(Path(CONFIG['memory']['cli']).expanduser()), CONFIG['memory']['agent'], count)
    root_label, root_path = root
    validate_directory(str(root_path))
    root_id = 'root:' + root_label
    root_index = nodes['id'].index(root_id)
    center = tuple(nodes[key][root_index] for key in ('bx', 'by', 'bz'))
    agents = {item.removeprefix('agent:'): i for i, item in enumerate(nodes['id']) if item.startswith('agent:')}
    authors = {}
    for index, record in enumerate(records):
        ring, slot = divmod(index, 16)
        slots = min(16, len(records) - ring * 16)
        angle = slot * 2 * math.pi / slots + ring * 0.4
        radius = 0.72 + ring * 0.48
        xyz = (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle),
               center[2] + 0.18 * math.sin(angle + ring))
        px, py, depth = _project(*xyz, 0.35)
        root_color = ROOT_COLORS.get(root_label, '#a18dff')
        color = AGENT_COLORS.get(record.author, root_color) if record.author_type == 'agent' and record.author in agents else root_color
        key = 'memory:' + record.short_id
        values = {'id': key, 'orbit_parent': root_id, 'x': px, 'y': py, 'depth': depth,
                  'bx': xyz[0], 'by': xyz[1], 'bz': xyz[2], 'size': 6.2, 'color': color,
                  'alpha': 0.95, 'name': record.title, 'kind': 'Memory planet',
                  'detail': record.title + ' · author: ' + record.author,
                  'action': '', 'memory': record.short_id, 'path': str(root_path),
                  'root': root_label, 'memory_project': record.project}
        for column in nodes:
            nodes[column].append(values[column])
        authors[key] = record.author
        if record.author_type == 'agent' and record.author in agents:
            source_index = agents[record.author]
            for column, value in {'xs': [nodes['x'][source_index], px], 'ys': [nodes['y'][source_index], py],
                                  'source_idx': source_index, 'target_idx': len(nodes['id']) - 1,
                                  'color': color, 'alpha': 0.24, 'size': 0.8}.items():
                links[column].append(value)
    return authors


def make_scene() -> dict:
    activities = read_activities()
    files, active_agents = build_catalog(activities)
    nodes, _, links, _ = _build_scene(files, active_agents)
    memory_root = prepare_memory_node(nodes, links, CONFIG)
    planet_authors = add_memory_planets(nodes, links, memory_root)
    visible_file_ids = set(nodes['id'])
    files = [item for item in files if 'file:' + item.path in visible_file_ids]
    activity_authors = {(item.memory_id, item.project): item.author for item in activities}
    file_authors = {"file:" + item.path: activity_authors.get(
        (item.memory_ids[0], item.memory_projects[0]), "") for item in files if item.memory_ids}
    planet_ranks = {key: index + 1 for index, key in enumerate(planet_authors)}
    compact_nodes = [
        {
            "x": round(nodes["bx"][index], 4),
            "id": nodes["id"][index],
            "orbit_parent": nodes["orbit_parent"][index],
            "y": round(nodes["by"][index], 4),
            "z": round(nodes["bz"][index], 4),
            "name": nodes["name"][index],
            "kind": nodes["kind"][index],
            "display_role": 'shared-worker' if nodes['id'][index] == 'agent:factory-worker' else '',
            "color": nodes["color"][index],
            "action": nodes["action"][index],
            "alpha": nodes["alpha"][index],
            "path": nodes["path"][index],
            "root": nodes["root"][index],
            "memory": nodes["memory"][index].split(", ")[0],
            "memory_project": nodes["memory_project"][index],
            "memory_author": planet_authors.get(nodes["id"][index], file_authors.get(nodes["id"][index], "")),
            "display_agent": _display_agent(file_authors[nodes["id"][index]]) if nodes["id"][index] in file_authors else "",
            "memory_rank": planet_ranks.get(nodes["id"][index], 0),
        }
        for index in range(len(nodes["name"]))
    ]
    compact_links = [
        {"from": links["source_idx"][index], "to": links["target_idx"][index], "color": links["color"][index]}
        for index in range(len(links["color"]))
    ]
    return {
        "schema": "factory-observatory-wallpaper/v1",
        "generated_at": int(time.time()),
        "source": "configured-reviewed-memory",
        "galaxy": ({"label": CONFIG["galaxy"]["label"],
                    "path": str(Path(CONFIG["galaxy"]["path"]).expanduser())}
                   if CONFIG.get("galaxy") else {}),
        "memory_source": {
            "provider": CONFIG["memory"]["provider"],
            "cli": str(Path(CONFIG["memory"].get("cli", "")).expanduser()) if CONFIG["memory"].get("cli") else "",
            "agent": CONFIG["memory"].get("agent", ""),
            "browser_script": str(Path(__file__).with_name("memory_browser.py")),
            "config_path": str(CONFIG_PATH),
        },
        "counts": {"activities": len(activities), "files": len(files), "directories": len({item.directory for item in files}), "agents": sum(node['kind'] == 'Agent' for node in compact_nodes), "memory_planets": len(planet_authors)},
        "nodes": compact_nodes,
        "links": compact_links,
        "agent_activity": agent_movement_metadata(files, nodes),
        "available_agents": list(dict.fromkeys([*CONFIG.get('agents', []), *active_agents])),
        "memory_node": CONFIG.get('memory_node') or {'provider': 'hindsight'
                          if memory_root or 'root:Hindsight' in nodes['id'] else None},
    }


def write_scene(path: Path = SCENE_PATH) -> dict:
    scene = make_scene()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=".scene-", suffix=".json", delete=False) as stream:
        temporary = Path(stream.name)
        os.fchmod(stream.fileno(), 0o600)
        json.dump(scene, stream, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true", help="refresh every two minutes for the wallpaper")
    args = parser.parse_args()
    while True:
        try:
            scene = write_scene()
            counts = scene["counts"]
            print(f"Wallpaper scene refreshed: {counts['files']} files, {counts['directories']} directories, {counts['agents']} linked agents", flush=True)
        except Exception as error:
            print(f"Wallpaper scene refresh failed: {type(error).__name__}: {error}", flush=True)
            if not args.loop:
                raise SystemExit(1) from error
        if not args.loop:
            return
        time.sleep(120)


if __name__ == "__main__":
    main()
