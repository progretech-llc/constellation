#!/usr/bin/env python3
"""Show one reviewed MemPalace entry through the configured identity-bound CLI."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


SHORT_ID = re.compile(r"[0-9a-f]{8}")
FULL_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
CONTEXT_HEADER = re.compile(r"^\[MEMORY ([0-9a-f-]{36})\]$", re.M)


def resolve_memory_id(cli: str, agent: str, project: str, memory_id: str) -> str:
    if FULL_ID.fullmatch(memory_id):
        return memory_id
    if not SHORT_ID.fullmatch(memory_id):
        raise ValueError("Invalid memory ID")
    result = subprocess.run(
        [cli, "--agent", agent, "context", "Activity", "--project", project, "--limit", "2000"],
        capture_output=True, text=True, timeout=20, check=True,
    )
    matches = [full for full in CONTEXT_HEADER.findall(result.stdout) if full.startswith(memory_id)]
    if len(matches) != 1:
        raise LookupError("The exact memory entry is unavailable or ambiguous in the authorized project context")
    return matches[0]


def read_memory(cli: str, agent: str, project: str, memory_id: str) -> tuple[str, str]:
    if not Path(cli).is_file() or not Path(cli).is_absolute():
        raise ValueError("Configured MemPalace CLI is unavailable")
    if not re.fullmatch(r"[a-z0-9-]{1,40}", agent) or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", project):
        raise ValueError("Invalid MemPalace identity or project")
    full_id = resolve_memory_id(cli, agent, project, memory_id)
    result = subprocess.run([cli, "--agent", agent, "show", full_id],
                            capture_output=True, text=True, timeout=20, check=True)
    return full_id, result.stdout


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("Usage: memory_viewer.py CLI AGENT PROJECT MEMORY_ID")
    try:
        full_id, content = read_memory(*sys.argv[1:])
    except (ValueError, LookupError, OSError, subprocess.SubprocessError) as error:
        full_id, content = "unavailable", f"Could not open the memory entry.\n\n{error}"

    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, Gtk

    class MemoryWindow(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="com.progretech.ConstellationMemory", flags=Gio.ApplicationFlags.NON_UNIQUE)

        def do_activate(self):
            window = Gtk.ApplicationWindow(application=self, title=f"Constellation · MemPalace {full_id}")
            window.set_default_size(850, 650)
            scroll = Gtk.ScrolledWindow()
            text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                left_margin=18, right_margin=18, top_margin=16, bottom_margin=16,
                                wrap_mode=Gtk.WrapMode.WORD_CHAR)
            text.get_buffer().set_text(content)
            scroll.set_child(text)
            window.set_child(scroll)
            window.present()

    MemoryWindow().run([])


if __name__ == "__main__":
    main()
