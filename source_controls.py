"""Save folder display controls without replacing memory or other source settings."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from config import load_config


def editable_values(data: dict) -> dict:
    return {"roots": data["roots"], "max_files": data.get("max_files", 160),
            "max_directories": data.get("max_directories", 48)}


def save_folder_controls(path: Path, roots: list[dict], max_files: int,
                         max_directories: int, expected: dict) -> dict:
    """Validate a draft, preserve unrelated keys, and atomically replace the config.

    Missing existing roots may be offline mounts and can remain configured.
    Newly selected paths must be available directories. No folder is modified.
    """
    original = path.read_bytes()
    current = json.loads(original)
    if editable_values(current) != expected:
        raise ValueError("Folder settings changed elsewhere. Reload folders before applying.")
    if not 1 <= len(roots) <= 12:
        raise ValueError("Keep between 1 and 12 folders in the galaxy.")
    if type(max_files) is not int or not 1 <= max_files <= 1000:
        raise ValueError("Remembered file limit must be between 1 and 1,000.")
    if type(max_directories) is not int or not 1 <= max_directories <= 200:
        raise ValueError("Remembered subfolder limit must be between 1 and 200.")
    cleaned, seen = [], set()
    existing = {Path(root['path']).expanduser().resolve() for root in current['roots']}
    galaxy = current.get('galaxy', {}).get('path')
    galaxy_path = Path(galaxy).expanduser().resolve() if galaxy else None
    for root in roots:
        label = root['label'].strip()
        folder = Path(root['path']).expanduser()
        if not label or len(label) > 80:
            raise ValueError("Give each folder a name of 1 to 80 characters.")
        if not folder.is_absolute():
            raise ValueError("Choose an absolute folder path.")
        resolved = folder.resolve()
        if resolved in seen:
            raise ValueError("Each folder can appear only once, including linked paths.")
        if resolved == galaxy_path:
            raise ValueError("Choose a child folder instead of the central galaxy folder.")
        if resolved not in existing and not folder.is_dir():
            raise ValueError(f"Folder is unavailable: {folder}")
        seen.add(resolved)
        cleaned.append({'label': label, 'path': str(folder)})
    updated = {**current, 'roots': cleaned, 'max_files': max_files,
               'max_directories': max_directories}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.folders-',
                                         suffix='.json', delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump(updated, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        load_config(temporary)
        if path.read_bytes() != original:
            raise ValueError("Configuration changed while saving. Reload folders and retry.")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return updated
