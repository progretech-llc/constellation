"""Discover local memory-system metadata, without opening any memory store."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from config import load_config

PROVIDERS = {'hindsight': 'Hindsight', 'mem0': 'Mem0', 'zep': 'Zep',
             'chroma': 'Chroma', 'qdrant': 'Qdrant', 'letta': 'Letta'}


def discover_memory(config, *, home=None, run=subprocess.run, which=shutil.which):
    home = home or Path.home()
    services, warnings = {}, []
    for scope in (['--user'], []):
        try:
            result = run(['systemctl', *scope, 'list-units', '--type=service', '--all', '--output=json', '--no-pager'],
                         capture_output=True, text=True, timeout=5, check=True)
            for unit in json.loads(result.stdout):
                for provider in PROVIDERS:
                    if unit.get('unit') in (f'{provider}.service', f'{provider}-server.service'):
                        state = 'running service' if unit.get('active') == 'active' and unit.get('sub') == 'running' else 'service not running'
                        if services.get(provider) != 'running service':
                            services[provider] = state
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            warnings.append('User service status unavailable.' if scope else 'System service status unavailable.')
    systems = []
    for provider, label in PROVIDERS.items():
        directory = None
        candidates = [home / '.local/share' / provider, home / '.config' / provider, home / f'.{provider}']
        command = which(provider)
        configured = provider == 'hindsight' and config['memory']['provider'] in {'hindsight', 'hindsight-api'}
        if configured:
            command = config['memory'].get('cli') or command
            for root in config['roots']:
                if root['label'].casefold() in ('hindsight', 'mempalace'):
                    candidates.insert(0, Path(root['path']).expanduser())
            if command and Path(command).is_file():
                for parent in list(Path(command).resolve().parents)[:4]:
                    if (parent / 'config/client.json').is_file():
                        candidates.insert(0, parent)
                        break
        for candidate in candidates:
            if candidate.is_dir():
                directory = candidate.resolve()
                break
        executable = bool(command and Path(command).expanduser().is_file() and os.access(Path(command).expanduser(), os.X_OK))
        if provider not in services and not directory and not executable and not configured:
            continue
        status = services.get(provider) or ('configured memory source' if configured else
                                           'installed command' if executable else 'configuration/data directory found')
        reader = configured and (config['memory']['provider'] == 'hindsight-api' or
                                 (executable and directory is not None and (directory / 'config/client.json').is_file()))
        systems.append({'provider': provider, 'label': label, 'path': str(directory) if directory else '',
                        'status': status, 'records_supported': reader})
    return {'systems': systems, 'warnings': warnings}


if __name__ == '__main__':
    print(json.dumps(discover_memory(load_config())))
