"""Recommend solar systems from reviewed paths, without walking folder contents."""
from __future__ import annotations

import json
import re
from pathlib import Path

from memory_map import (BLOCKED_NAMES, BLOCKED_SEGMENTS, BLOCKED_SUFFIXES, CONFIG,
                        LINE_NUMBER, PATH, SENSITIVE_SEGMENT, read_activities)


def _allowed(path: Path) -> bool:
    return (path.is_absolute() and path.name not in BLOCKED_NAMES and
            path.suffix.lower() not in BLOCKED_SUFFIXES and
            not any(part in BLOCKED_SEGMENTS or part.startswith('.') or
                    SENSITIVE_SEGMENT.search(part) for part in path.parts))


def _folder(candidate: str, galaxy: Path | None, home: Path) -> Path | None:
    raw = Path(LINE_NUMBER.sub('', candidate.rstrip('.:').strip('`"\'')))
    if not _allowed(raw):
        return None
    try:
        path = raw.resolve(strict=True)
        if not _allowed(path):
            return None
        directory = path if path.is_dir() else path.parent if path.is_file() else None
        if directory is None:
            return None
        # Prefer a project root to dozens of src/test/build subfolders. Inspect
        # only ancestors of referenced paths; never recurse through a drive.
        for parent in (directory, *directory.parents):
            if parent in (galaxy, home, Path('/')):
                break
            if (parent / '.git').exists():
                return parent
        for anchor in (galaxy, home):
            if anchor and directory != anchor and directory.is_relative_to(anchor):
                return anchor / directory.relative_to(anchor).parts[0]
        return directory if directory not in (Path('/'), home, galaxy) else None
    except (OSError, RuntimeError, ValueError):
        return None


def recommend_folders(activities: list, config: dict, home: Path | None = None) -> list[dict]:
    home = (home or Path.home()).resolve()
    galaxy = Path(config['galaxy']['path']).expanduser().resolve() if config.get('galaxy') else None
    groups = {}
    seen_records = set()
    configured_agents = set(config.get('agents', []))
    for rank, activity in enumerate(activities[:2000]):
        if activity.memory_id in seen_records:
            continue
        seen_records.add(activity.memory_id)
        author = config.get('agent_aliases', {}).get(activity.author, activity.author)
        if configured_agents and author not in configured_agents:
            author = config.get('unlisted_agent')
            if not author:
                continue
        referenced = set()
        for text in [*activity.steps, *activity.evidence]:
            # Include quoted paths containing spaces as well as the normal extractor.
            candidates = re.findall(r'["\'`](/[^"\'`\n]+)["\'`]', text) + PATH.findall(text)
            for candidate in candidates:
                folder = _folder(candidate, galaxy, home)
                if folder:
                    referenced.add(folder)
        for folder in referenced:
            item = groups.setdefault(folder, {'path': str(folder), 'label': folder.name,
                                              'activity_count': 0, 'agents': set(), 'newest_rank': rank})
            item['activity_count'] += 1
            item['agents'].add(author)
    ordered = sorted(groups.values(), key=lambda item: (-item['activity_count'], -len(item['agents']),
                                                       item['newest_rank'], item['path']))[:5]
    return [{**item, 'agents': sorted(item['agents'])} for item in ordered]


def main() -> None:
    activities = read_activities()
    result = {'recommendations': recommend_folders(activities, CONFIG),
              'activities_checked': len(activities),
              'project': CONFIG['memory'].get('project', 'configured JSON activity')}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
