#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$repo_dir/.venv/bin/python" ]]; then
  echo 'Install Python dependencies in .venv first; see README.md.' >&2
  exit 1
fi
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p -- "$app_dir"
cat > "$app_dir/factory-observatory.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Factory Observatory
Comment=Shared ProgreTech memory map
Exec=$repo_dir/launcher.sh
Path=$repo_dir
Terminal=false
Categories=Graphics;Development;
Icon=applications-graphics
StartupNotify=false
DESKTOP
chmod 644 "$app_dir/factory-observatory.desktop"
echo "Installed $app_dir/factory-observatory.desktop"
