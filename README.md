# Constellation by ProgreTech

A GNOME 50/Wayland animated wallpaper of Progre watching the factory's memory
constellation. The city, rooftop, low clouds, and Progre are a stationary
foreground; the star field and cluster graph rotate automatically in the open sky.
Directory systems appear as large lights, remembered files as stars, and moving
pulses connect agents to recent files named in shared MemPalace activity. Nebula
glow, spiral dust, and simulated rays give the map its galaxy character. The
existing Bokeh view remains available for hovering and inspecting paths.

The scene uses MemPalace's supported CLI as `codex` and reads shared reviewed
ProgreTech activities. It does not scan the whole workstation or read another
role's private memory. Only existing allowlisted files explicitly named in
reviewed technical steps or evidence can appear. Action colors are inferred from
wording, not verified filesystem events. Newest list records take priority;
older search results are relevance-ranked. Missing, hidden, and credential-like
paths are excluded. Git and task ledgers remain authoritative.

## Install on Ubuntu GNOME 50

Python 3.10+, GJS, GTK 4 Python bindings, GNOME Shell 50, and a user systemd
session are required. In this repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./install-user.sh
```

The installer copies the local Progre foreground into the current user's data
directory, adds **Constellation by ProgreTech** to the application menu, installs
the GNOME background extension, and enables a user timer that refreshes the memory
scene every two minutes. On first installation into an already-running GNOME
Wayland session, log out and back in for Shell to discover the new extension.
The static GNOME wallpaper setting is left unchanged.

The native controls offer automatic-rotation speed, pause, foreground visibility,
nebula glow, rays, star density, link trails, labels, manual memory refresh, and
an **Open interactive map** button. The browser does not need to stay open. The
renderer labels missing or stale memory scenes instead of presenting them as
current. Disable the wallpaper in controls or with
`gnome-extensions disable factory-observatory@progretech.com`.

Check the installed services and extension with:

```sh
systemctl --user status factory-observatory-scene.timer
gnome-extensions info factory-observatory@progretech.com
```

## Interactive map and renderer preview

The Bokeh map can also be opened with `.venv/bin/python app.py --serve`, bound to
`127.0.0.1:8765`. A self-contained snapshot uses `.venv/bin/python app.py
--no-open`. The earlier synthetic layout study remains in `demo_app.py`.

To render the exact Cairo composition for review:

```sh
.venv/bin/python wallpaper_scene.py
gjs -m gnome-extension/render-preview.js ~/.local/state/factory-observatory/scene.json /tmp/constellation.png 1920 1080 assets/progre-foreground.png
```

The GNOME layer is noninteractive so desktop icons and windows remain usable. The
Shell background group is an internal integration point to revalidate after a
Shell upgrade. Remote storage connectors and file-operation verification are not
implemented.

The original scene was supplied by Edwin at
`/home/edwin/Pictures/Wallpapers/ChatGPT Image Sep 25, 2026, 12_52_06 PM.png`.
`assets/progre-foreground.png` is its edited, transparent-sky derivative, used
locally for this prototype. The source image remains untouched. Review visual
asset distribution rights before any public release. This repository is private;
an open-source license has not been selected.
