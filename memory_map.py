"""Read bounded activity from reviewed JSON summaries or an identity-bound Hindsight CLI.

This module never opens Hindsight's database or another role's receipt files.
"""

from __future__ import annotations

import re
import json
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from config import load_config, root_entries


CONFIG = load_config()
MEMORY = CONFIG["memory"]
LIST_LIMIT = 2000
SEARCH_LIMIT = 700
MAX_ACTIVITIES = 2000
MAX_FILES = min(1000, max(1, int(CONFIG.get("max_files", 160))))
MAX_DIRECTORIES = min(200, max(1, int(CONFIG.get("max_directories", 48))))
MAX_LINKS_PER_AGENT = 7
MIN_FILES_PER_AGENT = 4

ROOTS = root_entries(CONFIG)


def _display_agent(author: str) -> str:
    """Map scene nodes only; Activity.author and memory IDs keep original provenance."""
    agent = CONFIG['agent_aliases'].get(author, author)
    if agent in (CONFIG.get('display_agents') or []):
        return agent
    if CONFIG['agents'] and agent not in CONFIG['agents'] and CONFIG['unlisted_agent']:
        return CONFIG['unlisted_agent']
    return agent

HEADER = re.compile(r"^([0-9a-f]{8}) \[([^/]+)/([^\]]+)\] (.+)$")
PATH = re.compile(r"(?<![A-Za-z0-9:/])/(?:[^\s\"'<>|),;\]]+)")
QUOTED_PATH = re.compile(r"([`\"'])(/[^\r\n]*?)\1")
LINE_NUMBER = re.compile(r":\d+(?::\d+)?$")
BLOCKED_SEGMENTS = {".ssh", ".config", ".local", ".git", "private-backup", "private", "credentials", "secrets"}
BLOCKED_NAMES = {".env", "id_rsa", "id_ed25519", "hindsight.db"}
BLOCKED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".sqlite", ".db", ".env"}
SENSITIVE_SEGMENT = re.compile(r"(?:credential|secret|password|token|private.key)", re.I)
WRITE = re.compile(r"\b(create(?:d)?|generat(?:ed|e)|wrote|added|saved|exported|produc(?:ed|e))\b", re.I)
CHANGE = re.compile(r"\b(edit(?:ed)?|updat(?:ed|e)|modif(?:ied|y)|patch(?:ed)?|chang(?:ed|e)|revis(?:ed|e))\b", re.I)
NEGATED_CLAUSE = re.compile(r"\b(?:no|not|never|without|didn't|wasn't|weren't|hasn't|haven't)\b[^.;\n]*", re.I)
READ = re.compile(r"\b(read|opened|inspected|viewed|loaded|reviewed|checked|accessed|examined)\b", re.I)


@dataclass
class Activity:
    memory_id: str
    author: str
    project: str
    steps: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class FileReference:
    path: str
    directory: str
    root: str
    agents: dict[str, str] = field(default_factory=dict)
    memory_ids: list[str] = field(default_factory=list)
    memory_projects: list[str] = field(default_factory=list)
    newest_rank: int = 10**9
    agent_ranks: dict[str, int] = field(default_factory=dict)
    agent_write_ranks: dict[str, int] = field(default_factory=dict)


def _project_allowed(project: str) -> bool:
    selected = MEMORY.get("project", "")
    return project == selected or (MEMORY.get("include_subprojects", False) and project.startswith(selected + "-"))


def _parse_cli_output(output: str) -> list[Activity]:
    activities: list[Activity] = []
    current: Activity | None = None
    section: str | None = None
    valid = False
    provenance_ok = False
    for line in output.splitlines():
        match = HEADER.match(line)
        if match:
            if current and valid and provenance_ok and current.author and _project_allowed(current.project):
                activities.append(current)
            current = Activity(memory_id=match.group(1), author="", project="")
            section = None
            valid = match.group(2) == "project" and match.group(3) == "active" and match.group(4).startswith("Activity:")
            provenance_ok = False
            continue
        if not current:
            continue
        if line.startswith("  author: agent/"):
            current.author = line.removeprefix("  author: agent/").strip()
        elif line.startswith("  project: "):
            current.project = line.removeprefix("  project: ").strip()
        elif line.startswith("  provenance_type: "):
            provenance_ok = line.removeprefix("  provenance_type: ").strip() == "structured-agent-activity"
        elif line.strip() == "Technical steps:":
            section = "steps"
        elif line.strip() == "Evidence:":
            section = "evidence"
        elif line.strip() in {"Teaching references:", "This activity report is agent-authored; reusable lessons need evidence review."}:
            section = None
        elif line.startswith("- ") and section == "steps":
            current.steps.append(line[2:])
        elif line.startswith("- ") and section == "evidence":
            current.evidence.append(line[2:])
    if current and valid and provenance_ok and current.author and _project_allowed(current.project):
        activities.append(current)
    return activities[:MAX_ACTIVITIES]


def read_activities() -> list[Activity]:
    if MEMORY["provider"] == "json":
        return _read_json_activities()
    if MEMORY['provider'] == 'hindsight-api':
        from hindsight_api import read_shared_documents
        return [Activity(row['memory_id'], row['author'], row['project'],
                         row['technical_steps'][:12], row['evidence'][:12])
                for row in read_shared_documents(MEMORY)]
    cli = str(Path(MEMORY["cli"]).expanduser())
    agent = MEMORY["agent"]
    project = MEMORY["project"]
    recent = subprocess.run(
        [cli, "--agent", agent, "list", "--limit", str(LIST_LIMIT)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    shared = subprocess.run(
        [cli, "--agent", agent, "search", "Activity", "--scope", "project", "--project", project, "--provenance-type", "structured-agent-activity", "--limit", str(SEARCH_LIMIT)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if recent.returncode or shared.returncode:
        raise RuntimeError("Hindsight CLI retrieval failed; the map was not regenerated")
    if recent.stdout.strip() == "No memories." and shared.stdout.strip() == "No matching memories.":
        return []
    seen: set[str] = set()
    activities: list[Activity] = []
    for activity in _parse_cli_output(recent.stdout) + _parse_cli_output(shared.stdout):
        if activity.memory_id in seen:
            continue
        seen.add(activity.memory_id)
        activities.append(activity)
    return activities[:MAX_ACTIVITIES]


def _read_json_activities() -> list[Activity]:
    """Read a small local directory of reviewed event summaries, never transcripts."""
    directory = Path(MEMORY["directory"]).expanduser()
    if not directory.is_dir():
        raise RuntimeError(f"Memory directory does not exist: {directory}")
    activities = []
    for path in sorted(directory.glob("*.json"), reverse=True)[:100]:
        if path.is_symlink() or path.stat().st_size > 1_000_000:
            continue
        records = json.loads(path.read_text())
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict) or not isinstance(record.get("author"), str):
                continue
            steps = record.get("technical_steps", [])
            evidence = record.get("evidence", [])
            if not isinstance(steps, list) or not isinstance(evidence, list):
                continue
            activities.append(Activity(str(record.get("memory_id", f"{path.stem}-{index}")), record["author"],
                                       str(record.get("project", "")),
                                       [s for s in steps[:12] if isinstance(s, str)],
                                       [s for s in evidence[:12] if isinstance(s, str)]))
            if len(activities) >= MAX_ACTIVITIES:
                return activities
    return activities


def _classify(step: str) -> str:
    # A denial of output creation is not evidence of a write.
    step = NEGATED_CLAUSE.sub(" ", step)
    if CHANGE.search(step):
        return "modified"
    if WRITE.search(step):
        return "created"
    if READ.search(step):
        return "accessed"
    return "referenced"


def _root_for(path: Path) -> str | None:
    for label, root in ROOTS:
        if path == root or path.is_relative_to(root):
            return label
    return None


def _safe_file(candidate: str) -> tuple[str, str, str] | None:
    raw = LINE_NUMBER.sub("", candidate.rstrip(".:").strip("`\"'"))
    raw_path = Path(raw)
    if not raw_path.is_absolute() or any(segment in BLOCKED_SEGMENTS or segment.startswith(".") or SENSITIVE_SEGMENT.search(segment) for segment in raw_path.parts):
        return None
    if raw_path.name in BLOCKED_NAMES or raw_path.suffix.lower() in BLOCKED_SUFFIXES:
        return None
    root = _root_for(raw_path)
    if not root:
        return None
    try:
        resolved = raw_path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_file() or any(segment in BLOCKED_SEGMENTS or segment.startswith(".") or SENSITIVE_SEGMENT.search(segment) for segment in resolved.parts):
        return None
    configured_root = next(path for label, path in ROOTS if label == root)
    if not resolved.is_relative_to(configured_root.resolve()):
        return None
    return str(raw_path), str(raw_path.parent), root


def _paths(text: str) -> list[tuple[str, str, str]]:
    found = []
    # A standalone evidence path or explicit quotation can contain spaces.
    standalone = text.strip()
    if standalone.startswith("/") and "\n" not in standalone:
        safe = _safe_file(standalone)
        if safe:
            return [safe]
    for match in QUOTED_PATH.finditer(text):
        safe = _safe_file(match.group(2))
        if safe and safe not in found:
            found.append(safe)
    # Do not reinterpret a rejected quoted path as a shorter, unrelated file.
    for candidate in PATH.findall(QUOTED_PATH.sub(" ", text)):
        safe = _safe_file(candidate)
        if safe and safe not in found:
            found.append(safe)
    return found


def build_catalog(activities: list[Activity]) -> tuple[list[FileReference], list[str]]:
    files: dict[str, FileReference] = {}
    agents: list[str] = []
    for rank, activity in enumerate(activities):
        display_agent = _display_agent(activity.author)
        if display_agent not in agents:
            agents.append(display_agent)
        seen_this_activity: set[tuple[str, str]] = set()
        for text, action in [(step, _classify(step)) for step in activity.steps] + [(evidence, "referenced") for evidence in activity.evidence]:
            for path, directory, root in _paths(text):
                marker = (path, display_agent)
                if marker in seen_this_activity and action == "referenced":
                    continue
                seen_this_activity.add(marker)
                item = files.setdefault(path, FileReference(path, directory, root))
                item.newest_rank = min(item.newest_rank, rank)
                item.agent_ranks[display_agent] = min(item.agent_ranks.get(display_agent, rank), rank)
                if action in {'created', 'modified'}:
                    item.agent_write_ranks[display_agent] = min(item.agent_write_ranks.get(display_agent, rank), rank)
                if activity.memory_id not in item.memory_ids:
                    item.memory_ids.append(activity.memory_id)
                    item.memory_projects.append(activity.project)
                previous = item.agents.get(display_agent)
                priority = {"referenced": 0, "accessed": 1, "created": 2, "modified": 3}
                if previous is None or priority[action] > priority[previous]:
                    item.agents[display_agent] = action
    newest = sorted(files.values(), key=lambda item: (item.newest_rank, item.path))
    kept_directories: set[str] = set()
    selected: list[FileReference] = []
    selected_paths: set[str] = set()
    # Reserve a few remembered files for each original author before filling
    # the scene by recency. A busy agent must not erase quieter agents.
    for agent in agents:
        if len(selected) >= MAX_FILES:
            break
        count = 0
        for item in newest:
            if agent not in item.agents:
                continue
            if item.directory not in kept_directories and len(kept_directories) >= MAX_DIRECTORIES:
                continue
            if item.path not in selected_paths:
                if len(selected) >= MAX_FILES:
                    break
                selected.append(item)
                selected_paths.add(item.path)
                kept_directories.add(item.directory)
            count += 1
            if count >= MIN_FILES_PER_AGENT:
                break
    # Keep a few remembered files visible in each configured system even when
    # newer activity in busier roots fills the global file cap.
    for root, _ in ROOTS:
        if len(selected) >= MAX_FILES:
            break
        if any(item.root == root for item in selected):
            continue
        count = 0
        for item in newest:
            if item.root != root or item.path in selected_paths:
                continue
            if item.directory not in kept_directories and len(kept_directories) >= MAX_DIRECTORIES:
                continue
            selected.append(item)
            selected_paths.add(item.path)
            kept_directories.add(item.directory)
            count += 1
            if count >= 3 or len(selected) >= MAX_FILES:
                break
    for item in newest:
        if len(selected) >= MAX_FILES:
            break
        if item.path in selected_paths:
            continue
        if item.directory not in kept_directories and len(kept_directories) >= MAX_DIRECTORIES:
            continue
        selected.append(item)
        selected_paths.add(item.path)
        kept_directories.add(item.directory)
    selected.sort(key=lambda item: (item.newest_rank, item.path))
    active_agents = [agent for agent in agents if any(agent in item.agents for item in selected)]
    return selected, active_agents


def recent_links(files: list[FileReference], agents: list[str]) -> list[tuple[str, str, str]]:
    counts: defaultdict[str, int] = defaultdict(int)
    links = []
    for item in files:
        for agent, action in item.agents.items():
            if agent not in agents or counts[agent] >= MAX_LINKS_PER_AGENT:
                continue
            links.append((agent, item.path, action))
            counts[agent] += 1
    return links
