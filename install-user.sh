#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$repo_dir/.venv/bin/python" ]]; then
  echo 'Install Python dependencies in .venv first; see README.md.' >&2
  exit 1
fi
if [[ ! -f "$repo_dir/assets/progre-foreground.png" ]]; then
  echo 'Progre foreground image is missing.' >&2
  exit 1
fi
for executable in python3 gjs gnome-extensions systemctl; do
  command -v "$executable" >/dev/null || { echo "Missing $executable" >&2; exit 1; }
done
python3 -c 'import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk' >/dev/null

app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
foreground_dir="${XDG_DATA_HOME:-$HOME/.local/share}/constellation"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p -- "$app_dir" "$unit_dir" "$repo_dir/build" "$foreground_dir"
chmod 700 "$foreground_dir"
install -m 600 "$repo_dir/assets/progre-foreground.png" "$foreground_dir/progre-foreground.png"
cat > "$app_dir/factory-observatory.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Constellation by ProgreTech
Comment=Control Progre's rotating factory memory sky
Exec=/usr/bin/python3 $repo_dir/control_app.py
Path=$repo_dir
Terminal=false
Categories=Graphics;Settings;
Icon=applications-graphics
StartupNotify=true
DESKTOP
chmod 644 "$app_dir/factory-observatory.desktop"
cat > "$unit_dir/factory-observatory-scene.service" <<UNIT
[Unit]
Description=Refresh the Constellation wallpaper from shared MemPalace

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

gnome-extensions pack --force --out-dir "$repo_dir/build" --extra-source=galaxy.js "$repo_dir/gnome-extension" >/dev/null
extension_zip="$repo_dir/build/factory-observatory@progretech.com.shell-extension.zip"
if [[ ! -f "$extension_zip" ]]; then
  echo "GNOME extension bundle missing at $extension_zip" >&2
  exit 1
fi
gnome-extensions install --force "$extension_zip"
if gnome-extensions info factory-observatory@progretech.com >/dev/null 2>&1; then
  gnome-extensions enable factory-observatory@progretech.com
  printf 'Installed and enabled Constellation controls, refresh timer, and GNOME wallpaper extension.\n'
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
  printf 'Installed Constellation. GNOME Wayland will load the new extension at the next login.\n'
fi
