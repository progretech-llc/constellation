#!/usr/bin/env python3
"""Export a bounded, local wallpaper scene from shared reviewed activity."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

from app import _build_scene
from memory_map import build_catalog, read_activities


STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
SCENE_PATH = STATE_HOME / "factory-observatory" / "scene.json"


def make_scene() -> dict:
    activities = read_activities()
    files, active_agents = build_catalog(activities)
    nodes, _, links, _ = _build_scene(files, active_agents)
    compact_nodes = [
        {
            "x": round(nodes["bx"][index], 4),
            "y": round(nodes["by"][index], 4),
            "z": round(nodes["bz"][index], 4),
            "name": nodes["name"][index],
            "kind": nodes["kind"][index],
            "color": nodes["color"][index],
            "action": nodes["action"][index],
            "alpha": nodes["alpha"][index],
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
        "counts": {"activities": len(activities), "files": len(files), "directories": len({item.directory for item in files}), "agents": len(active_agents)},
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
