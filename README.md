# Factory Observatory

A GNOME 50/Wayland wallpaper and local inspection app for ProgreTech's **reviewed
shared MemPalace activity**. The desktop background is a procedurally drawn,
automatically rotating galaxy: directory systems form large lights, remembered
files become orbiting points, active agents sit near the center, and pulses travel
along recent agent-to-file links. Star dust, nebula glow, and simulated light rays
provide the galaxy appearance. The interactive Bokeh map remains available for
hovering and inspecting paths.

The scene reads MemPalace with the `codex` identity through its supported CLI. It
uses shared ProgreTech structured activities and does not read another role's
private memory or database directly. Only existing files explicitly named in
reviewed technical steps or evidence can appear; there is no workstation-wide
scan. Action colors are inferred from wording, so they are approximate remembered
actions rather than verified file events. Newest `list` records take priority;
older `search` results are relevance-ranked, not a precise timeline. Agents with
no usable file references remain unlinked. Current file roots are Rend,
PycharmProjects, Pictures, and selected PT_CONTEXT folders. Hidden, missing, and
credential-like paths are excluded.

## Install on Ubuntu GNOME 50

Python 3.10+, GNOME Shell 50, GJS, GTK 4 Python bindings, and a user systemd
session are required. In the repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./install-user.sh
```

The installer creates a **Factory Observatory** menu entry that opens the native
GTK controls, installs a user GNOME Shell extension in the background layer, and
enables a user timer that refreshes the memory scene every two minutes. The
wallpaper starts rotating automatically. The controls offer pause, rotation
speed, nebula glow, rays, star density, link trails, labels, a manual memory
refresh, and an **Open interactive map** button. The shell extension watches the
local settings/scene files; no browser needs to remain open. It leaves GNOME's
static wallpaper setting alone.

To inspect the local units and extension:

```sh
systemctl --user status factory-observatory-scene.timer
systemctl --user status factory-observatory-scene.service
gnome-extensions info factory-observatory@progretech.com
```

The extension and scene files are local to the current user. Disable the
wallpaper in the controls or use
`gnome-extensions disable factory-observatory@progretech.com`. The renderer marks
missing or stale memory scenes rather than presenting them as live. Its use of
GNOME Shell's background group is an integration point to revalidate after a
Shell upgrade.

## Interactive map and preview

The Bokeh view can also be opened directly with `.venv/bin/python app.py --serve`.
It binds to `127.0.0.1:8765`; `--no-open` avoids opening a browser. A standalone
snapshot is generated with `.venv/bin/python app.py --no-open`. The earlier
synthetic layout study remains in `demo_app.py`.

The desktop renderer's exact Cairo scene can be exported for review:

```sh
.venv/bin/python wallpaper_scene.py
gjs -m gnome-extension/render-preview.js ~/.local/state/factory-observatory/scene.json /tmp/factory-galaxy.png 1920 1080
```

The GNOME renderer is intentionally noninteractive so desktop icons and windows
remain usable. Use the Bokeh map for per-file details. MemPalace is advisory;
Git and factory task records remain authorities for code and task state. Remote
storage connectors and file-operation verification are not implemented.

This repository remains a private prototype. An open-source license and public
release have not been selected.
