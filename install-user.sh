#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for executable in python3 gjs gnome-extensions systemctl; do
  command -v "$executable" >/dev/null || { echo "Missing $executable; see README.md" >&2; exit 1; }
done
python3 -c 'import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk' >/dev/null || {
  echo 'Missing GTK 4 Python bindings; install python3-gi and gir1.2-gtk-4.0.' >&2; exit 1;
}
if [[ ! -d "$repo_dir/.venv" ]]; then
  python3 -m venv "$repo_dir/.venv"
fi
"$repo_dir/.venv/bin/python" -m pip install -r "$repo_dir/requirements.txt"
if [[ ! -f "${XDG_CONFIG_HOME:-$HOME/.config}/constellation/sources.json" ]]; then
  python3 "$repo_dir/configure.py"
fi
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
foreground_dir="${XDG_DATA_HOME:-$HOME/.local/share}/constellation"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p -- "$app_dir" "$unit_dir" "$repo_dir/build" "$foreground_dir"
install -m 644 "$repo_dir/assets/progre-foreground.png" "$foreground_dir/foreground.png"
cat > "$app_dir/factory-observatory.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Constellation by ProgreTech
Comment=Control your rotating agent memory galaxy
Exec=/usr/bin/python3 $repo_dir/control_app.py
Path=$repo_dir
Terminal=false
Categories=Graphics;Settings;
Icon=applications-graphics
StartupNotify=true
DESKTOP
cat > "$unit_dir/factory-observatory-scene.service" <<UNIT
[Unit]
Description=Refresh the Constellation wallpaper from configured memory

[Service]
Type=oneshot
ExecStart=$repo_dir/.venv/bin/python $repo_dir/wallpaper_scene.py
UNIT
cat > "$unit_dir/factory-observatory-scene.timer" <<'UNIT'
[Unit]
Description=Refresh the Constellation memory scene every two minutes

[Timer]
OnStartupSec=20s
OnUnitActiveSec=2min
Persistent=true
AccuracySec=10s
Unit=factory-observatory-scene.service

[Install]
WantedBy=timers.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now factory-observatory-scene.timer
systemctl --user start factory-observatory-scene.service

gnome-extensions pack --force --out-dir "$repo_dir/build" --extra-source=galaxy.js --extra-source=memory_viewer.py "$repo_dir/gnome-extension" >/dev/null
extension_zip="$repo_dir/build/factory-observatory@progretech.com.shell-extension.zip"
test -f "$extension_zip" || { echo 'GNOME extension bundle was not created' >&2; exit 1; }
gnome-extensions install --force "$extension_zip"
if gnome-extensions info factory-observatory@progretech.com >/dev/null 2>&1; then
  gnome-extensions enable factory-observatory@progretech.com
  printf 'Constellation installed and enabled. Open it from the application menu.\n'
  if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
    printf 'Log out and back in to load new or updated GNOME extension code on Wayland.\n'
  fi
else
  python3 - <<'PY'
from gi.repository import Gio
settings = Gio.Settings.new('org.gnome.shell')
extensions = list(settings.get_strv('enabled-extensions'))
uuid = 'factory-observatory@progretech.com'
if uuid not in extensions:
    extensions.append(uuid)
    settings.set_strv('enabled-extensions', extensions)
PY
  printf 'Constellation installed. Log out and back in to load the new GNOME extension.\n'
fi
