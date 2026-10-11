#!/usr/bin/env python3
"""Choose the local memory source, directory systems, and central agent."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from config import CONFIG_PATH, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--memory-dir', type=Path, help='Directory of reviewed JSON activity files')
    source.add_argument('--mempalace-cli', type=Path, help='Path to your authorized MemPalace CLI')
    parser.add_argument('--agent', help='Your own MemPalace identity (with --mempalace-cli)')
    parser.add_argument('--project', help='MemPalace project (with --mempalace-cli)')
    parser.add_argument('--root', action='append', metavar='LABEL=PATH', help='Solar system directory; repeat to replace all roots')
    parser.add_argument('--center-agent', help='Agent ID to place at the center')
    parser.add_argument('--agents', nargs='+', help='Known agent IDs to show even when quiet')
    parser.add_argument('--alias', action='append', metavar='OLD=NEW', help='Display an old author under a current agent; repeatable')
    parser.add_argument('--unlisted-agent', help='Display other unlisted authors under this configured agent')
    args = parser.parse_args()
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text())
    else:
        memory_dir = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'constellation' / 'memory'
        data = {'memory': {'provider': 'json', 'directory': str(memory_dir)},
                'roots': [{'label': 'Home', 'path': str(Path.home())}], 'center_agent': '', 'agents': []}
    if args.memory_dir:
        directory = args.memory_dir.expanduser().resolve()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        data['memory'] = {'provider': 'json', 'directory': str(directory)}
    if args.mempalace_cli:
        if not args.agent or not args.project:
            parser.error('--mempalace-cli requires --agent and --project')
        cli = args.mempalace_cli.expanduser().resolve()
        if not cli.is_file() or not os.access(cli, os.X_OK):
            parser.error(f'MemPalace CLI is not executable: {cli}')
        data['memory'] = {'provider': 'mempalace', 'cli': str(cli),
                          'agent': args.agent, 'project': args.project}
    if args.root:
        roots = []
        for value in args.root:
            label, separator, path = value.partition('=')
            if not separator or not label.strip() or not path.strip():
                parser.error('--root must be LABEL=PATH')
            roots.append({'label': label.strip(), 'path': str(Path(path).expanduser().resolve())})
        data['roots'] = roots
    if args.center_agent is not None:
        data['center_agent'] = args.center_agent
    if args.agents is not None:
        data['agents'] = args.agents
    if args.alias:
        aliases = data.setdefault('agent_aliases', {})
        for value in args.alias:
            old, separator, new = value.partition('=')
            if not separator or not old.strip() or not new.strip():
                parser.error('--alias must be OLD=NEW')
            aliases[old.strip()] = new.strip()
    if args.unlisted_agent is not None:
        data['unlisted_agent'] = args.unlisted_agent
    CONFIG_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=CONFIG_PATH.parent, prefix='.sources-', delete=False) as stream:
        temporary = Path(stream.name)
        os.fchmod(stream.fileno(), 0o600)
        json.dump(data, stream, indent=2)
        stream.write('\n')
    try:
        load_config(temporary)
        os.replace(temporary, CONFIG_PATH)
    finally:
        temporary.unlink(missing_ok=True)
    if data['memory']['provider'] == 'json':
        Path(data['memory']['directory']).mkdir(mode=0o700, parents=True, exist_ok=True)
    print(f'Configured {CONFIG_PATH}; refresh with systemctl --user start factory-observatory-scene.service')


if __name__ == '__main__':
    main()
