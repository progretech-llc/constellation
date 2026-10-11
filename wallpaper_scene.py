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

from app import _agent_color, _build_scene, _project, ROOT_COLORS
from memory_map import CONFIG, build_catalog, read_activities
from mempalace_planets import read_recent


STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
SCENE_PATH = STATE_HOME / "factory-observatory" / "scene.json"


def add_memory_planets(nodes: dict, links: dict) -> dict[str, str]:
    """Add titles and IDs only; full MemPalace content stays in the CLI viewer."""
    root = next((item for item in CONFIG['roots'] if item.get('type') == 'mempalace'), None)
    if root is None:
        return {}
    source = CONFIG['memory']
    records = read_recent(source['cli'], source['agent'], root['max_memories'])
    root_id = 'root:' + root['label']
    root_index = nodes['id'].index(root_id)
    center = tuple(nodes[key][root_index] for key in ('bx', 'by', 'bz'))
    agent_indices = {item.removeprefix('agent:'): i for i, item in enumerate(nodes['id']) if item.startswith('agent:')}
    authors = {}
    for index, record in enumerate(records):
        ring, slot = divmod(index, 16)
        slots = min(16, len(records) - ring * 16)
        angle = slot * 2 * math.pi / slots + ring * 0.4
        radius = 0.72 + ring * 0.48
        xyz = (center[0] + radius * math.cos(angle),
               center[1] + radius * math.sin(angle), center[2] + 0.18 * math.sin(angle + ring))
        px, py, depth = _project(*xyz, 0.35)
        color = (_agent_color(record.author) if record.author_type == 'agent' and
                 record.author in agent_indices else ROOT_COLORS[root['label']])
        key = 'memory:' + record.short_id
        values = {'id': key, 'orbit_parent': root_id, 'x': px, 'y': py, 'depth': depth,
                  'bx': xyz[0], 'by': xyz[1], 'bz': xyz[2], 'size': 6.2, 'color': color,
                  'alpha': 0.95, 'name': record.title, 'kind': 'Memory planet',
                  'detail': record.title + ' · author: ' + record.author,
                  'action': '', 'memory': record.short_id, 'path': root['path'],
                  'root': root['label'], 'memory_project': record.project}
        for column in nodes:
            nodes[column].append(values[column])
        authors[key] = record.author
        if record.author_type == 'agent' and record.author in agent_indices:
            source_index = agent_indices[record.author]
            target_index = len(nodes['id']) - 1
            for column, value in {'xs': [nodes['x'][source_index], px], 'ys': [nodes['y'][source_index], py],
                                  'source_idx': source_index, 'target_idx': target_index,
                                  'color': color, 'alpha': 0.24, 'size': 0.8}.items():
                links[column].append(value)
    return authors


def make_scene() -> dict:
    activities = read_activities()
    files, active_agents = build_catalog(activities)
    nodes, _, links, _ = _build_scene(files, active_agents)
    planet_authors = add_memory_planets(nodes, links)
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
            "color": nodes["color"][index],
            "action": nodes["action"][index],
            "alpha": nodes["alpha"][index],
            "path": nodes["path"][index],
            "root": nodes["root"][index],
            "memory": nodes["memory"][index].split(", ")[0],
            "memory_project": nodes["memory_project"][index],
            "memory_author": planet_authors.get(nodes["id"][index], ""),
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
            "browser_script": str(Path(__file__).with_name('memory_browser.py')) if planet_authors else "",
        },
        "counts": {"activities": len(activities), "files": len(files), "directories": len({item.directory for item in files}), "agents": len(active_agents), "memory_planets": len(planet_authors)},
        "nodes": compact_nodes,
        "links": compact_links,
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
