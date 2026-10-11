"""Read bounded, shared MemPalace activity through the identity-bound CLI.

This module consumes the CLI's text output and keeps only reviewed project
activity. It never opens MemPalace's database or another role's receipt files.
"""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


MEMORY_CLI = "/home/edwin/Rend/bin/mempalace"
MEMORY_AGENT = "codex"
LIST_LIMIT = 2000
SEARCH_LIMIT = 700
MAX_ACTIVITIES = 2000
MAX_FILES = 160
MAX_DIRECTORIES = 48
MAX_LINKS_PER_AGENT = 7
MIN_FILES_PER_AGENT = 4

ROOTS = (
    ("Rend", Path("/home/edwin/Rend")),
    ("Repositories", Path("/home/edwin/PycharmProjects")),
    ("Pictures", Path("/home/edwin/Pictures")),
    ("Job artifacts", Path("/mnt/pt-context/job-artifacts")),
    ("Deliverables", Path("/mnt/pt-context/deliverables")),
    ("PT_CONTEXT", Path("/mnt/pt-context/projects")),
)

HEADER = re.compile(r"^([0-9a-f]{8}) \[([^/]+)/([^\]]+)\] (.+)$")
PATH = re.compile(r"(?<![A-Za-z0-9])(?:/home/edwin|/mnt/pt-context)/[^\s\"'<>|),;\]]+")
LINE_NUMBER = re.compile(r":\d+(?::\d+)?$")
BLOCKED_SEGMENTS = {".ssh", ".config", ".local", ".git", "private-backup", "private", "credentials", "secrets", "agents"}
BLOCKED_NAMES = {".env", "id_rsa", "id_ed25519", "mempalace.db"}
BLOCKED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".sqlite", ".db"}
SENSITIVE_SEGMENT = re.compile(r"(?:credential|secret|password|token|private.key)", re.I)
WRITE = re.compile(r"\b(create(?:d)?|generat(?:ed|e)|wrote|added|saved|exported|produc(?:ed|e))\b", re.I)
CHANGE = re.compile(r"\b(edit(?:ed)?|updat(?:ed|e)|modif(?:ied|y)|patch(?:ed)?|chang(?:ed|e)|revis(?:ed|e))\b", re.I)
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
    newest_rank: int = 10**9


def _project_allowed(project: str) -> bool:
    return project == "ProgreTech" or project.startswith("ProgreTech-")


def _parse_cli_output(output: str) -> list[Activity]:
    activities: list[Activity] = []
    current: Activity | None = None
    section: str | None = None
    valid = False
    for line in output.splitlines():
        match = HEADER.match(line)
        if match:
            if current and valid and current.author and _project_allowed(current.project):
                activities.append(current)
            current = Activity(memory_id=match.group(1), author="", project="")
            section = None
            valid = match.group(2) == "project" and match.group(3) == "active" and match.group(4).startswith("Activity:")
            continue
        if not current:
            continue
        if line.startswith("  author: agent/"):
            current.author = line.removeprefix("  author: agent/").strip()
        elif line.startswith("  project: "):
            current.project = line.removeprefix("  project: ").strip()
        elif line.startswith("  provenance_type: "):
            valid = valid and line.removeprefix("  provenance_type: ").strip() == "structured-agent-activity"
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
    if current and valid and current.author and _project_allowed(current.project):
        activities.append(current)
    return activities[:MAX_ACTIVITIES]


def read_activities() -> list[Activity]:
    recent = subprocess.run(
        [MEMORY_CLI, "--agent", MEMORY_AGENT, "list", "--limit", str(LIST_LIMIT)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    shared = subprocess.run(
        [MEMORY_CLI, "--agent", MEMORY_AGENT, "search", "Activity", "--scope", "project", "--project", "ProgreTech", "--provenance-type", "structured-agent-activity", "--limit", str(SEARCH_LIMIT)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if recent.returncode or shared.returncode:
        raise RuntimeError("MemPalace CLI retrieval failed; the map was not regenerated")
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


def _classify(step: str) -> str:
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
    if not (_root_for(resolved) or (resolved.is_relative_to(Path("/mnt/pt-context")) and root == "Rend")):
        return None
    return str(raw_path), str(raw_path.parent), root


def _paths(text: str) -> list[tuple[str, str, str]]:
    found = []
    for candidate in PATH.findall(text):
        safe = _safe_file(candidate)
        if safe:
            found.append(safe)
    return found


def build_catalog(activities: list[Activity]) -> tuple[list[FileReference], list[str]]:
    files: dict[str, FileReference] = {}
    agents: list[str] = []
    for rank, activity in enumerate(activities):
        if activity.author not in agents:
            agents.append(activity.author)
        seen_this_activity: set[tuple[str, str]] = set()
        for text, action in [(step, _classify(step)) for step in activity.steps] + [(evidence, "referenced") for evidence in activity.evidence]:
            for path, directory, root in _paths(text):
                marker = (path, activity.author)
                if marker in seen_this_activity and action == "referenced":
                    continue
                seen_this_activity.add(marker)
                item = files.setdefault(path, FileReference(path, directory, root))
                item.newest_rank = min(item.newest_rank, rank)
                if activity.memory_id not in item.memory_ids:
                    item.memory_ids.append(activity.memory_id)
                previous = item.agents.get(activity.author)
                priority = {"referenced": 0, "accessed": 1, "created": 2, "modified": 3}
                if previous is None or priority[action] > priority[previous]:
                    item.agents[activity.author] = action
    newest = sorted(files.values(), key=lambda item: (item.newest_rank, item.path))
    kept_directories: set[str] = set()
    selected: list[FileReference] = []
    selected_paths: set[str] = set()
    # Reserve a few remembered files for each original author before filling
    # the scene by recency. A busy agent must not erase quieter agents.
    for agent in agents:
        count = 0
        for item in newest:
            if agent not in item.agents:
                continue
            if item.path not in selected_paths:
                selected.append(item)
                selected_paths.add(item.path)
                kept_directories.add(item.directory)
            count += 1
            if count >= MIN_FILES_PER_AGENT:
                break
    for item in newest:
        if item.path in selected_paths:
            continue
        if item.directory not in kept_directories and len(kept_directories) >= MAX_DIRECTORIES:
            continue
        selected.append(item)
        selected_paths.add(item.path)
        kept_directories.add(item.directory)
        if len(selected) >= MAX_FILES:
            break
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
