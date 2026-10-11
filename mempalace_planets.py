"""Recent, identity-visible MemPalace records for the optional solar system.

The configured CLI enforces private-memory visibility. This module never opens
the database; the directory check only verifies the configured installation.
"""

from __future__ import annotations

import re
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


HEADER = re.compile(r"(?m)^([0-9a-f]{8}) \[([^/\]\n]+)/([^\]\n]+)\] ([^\n]+)$")
AUTHOR = re.compile(r"(?m)^  author: ([^/\n]+)/([^\n]+)$")
PROJECT = re.compile(r"(?m)^  project: ([^\n]+)$")
AGENT = re.compile(r"[a-z0-9-]{1,40}")


@dataclass(frozen=True)
class MemoryPlanet:
    short_id: str
    title: str
    author: str
    author_type: str
    project: str
    scope: str
    raw: str


def parse_list(output: str) -> list[MemoryPlanet]:
    matches = list(HEADER.finditer(output))
    records = []
    for index, match in enumerate(matches):
        if match.group(3) != "active":
            continue
        block = output[match.start():matches[index + 1].start() if index + 1 < len(matches) else len(output)].strip()
        # Metadata is emitted immediately after the header by the supported CLI.
        metadata = "\n".join(block.splitlines()[1:9])
        author = AUTHOR.search(metadata)
        if not author:
            continue
        project = PROJECT.search(metadata)
        records.append(MemoryPlanet(match.group(1), match.group(4).strip(), author.group(2).strip(),
                                    author.group(1), project.group(1).strip() if project else "",
                                    match.group(2), block))
    return records


def read_recent(cli: str, agent: str, limit: int) -> list[MemoryPlanet]:
    executable = Path(cli).expanduser()
    if not executable.is_absolute() or not executable.is_file() or not AGENT.fullmatch(agent):
        raise ValueError("Configure an absolute MemPalace CLI path and an authorized agent identity")
    bounded = max(1, min(5000, int(limit)))
    result = subprocess.run([str(executable), "--agent", agent, "list", "--limit", str(bounded)],
                            capture_output=True, text=True, timeout=40, check=True)
    return parse_list(result.stdout)


def validate_directory(path: str) -> Path:
    directory = Path(path).expanduser()
    database = directory / "mempalace.db"
    if not directory.is_absolute() or not database.is_file() or not os.access(database, os.R_OK):
        raise ValueError("A MemPalace solar system needs the directory containing an accessible mempalace.db")
    return directory
