# Factory Observatory

A local Bokeh map of ProgreTech's **reviewed shared MemPalace activity**. The
default view rotates a projected spatial scatter graph: directory systems contain
remembered files, agents sit near the center, and moving lights trace each agent's
latest visible file references. If two agents name the same file, both can link to
it. The colors evoke the galaxy metaphor without pretending this is a literal
galaxy or a complete filesystem audit.

The graph reads MemPalace with the `codex` identity through its supported CLI. It
uses shared ProgreTech structured activities and never reads another role's
private memory or MemPalace database directly. Only existing files explicitly
named in reviewed technical steps or evidence can appear. The broad directory
systems are fixed visual anchors; no workstation-wide scan runs. Agent action
colors are inferred from activity wording, so “created,” “modified,” “accessed,”
and “referenced” are **approximate remembered actions**, not verified file events.
The newest available records take priority, but older search results are ranked
by relevance rather than exact time. Agents with no usable file references remain
visible without links. Current safe roots are Rend, PycharmProjects, Pictures,
and selected PT_CONTEXT project, artifact, and deliverable folders. Sensitive
paths, hidden files, credential-like names, and missing files are excluded.

## Run

Python 3.10+ and the factory's local MemPalace CLI are required. From this repo:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

This writes and opens a self-contained snapshot at
`build/factory-observatory.html`. To refresh from memory every two minutes while
the page stays open:

```sh
.venv/bin/python app.py --serve
```

The server binds only to `127.0.0.1:8765`. `--no-open` avoids opening a browser;
`--refresh-seconds 300` changes the interval. If MemPalace retrieval fails, the
app reports the failure instead of showing invented or stale data. Pan, zoom,
pause, rotate, hover, and select nodes in the page. The earlier synthetic layout
prototype remains available with `.venv/bin/python demo_app.py`.

On Ubuntu, `./install-user.sh` adds **Factory Observatory** to the current
user's application menu. Its launcher starts the local server or reopens the
existing view. Remove `~/.local/share/applications/factory-observatory.desktop`
to uninstall the launcher; this does not delete the source or memory.

## Status and scope

This is a browser-based desktop visualization prototype. GNOME wallpaper/window
embedding and packaging still need desktop validation. MemPalace is advisory;
Git and factory task records remain the authority for code and task state. There
is no file watcher, remote storage connector, or access-control inference here.
The visualization adapts to the existing ProgreTech charter and folder structure;
it does not adopt the MAPS framework.

This repository remains a private prototype. An open-source license and public
release have not been selected.
