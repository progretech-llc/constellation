#!/usr/bin/env bash
set -euo pipefail
if [[ -z ${XDG_CURRENT_DESKTOP:-} || ${XDG_CURRENT_DESKTOP,,} != *gnome* ]]; then
  echo 'This release supports Ubuntu GNOME 50. Run from a GNOME desktop session.' >&2
  exit 1
fi
sudo apt-get install -y python3-venv python3-gi gir1.2-gtk-4.0 gjs
exec "$(dirname -- "${BASH_SOURCE[0]}")/install-user.sh"
