#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
url='http://127.0.0.1:8765/'
if [[ "$(curl --silent --show-error --max-time 3 "$url"health 2>/dev/null || true)" == 'factory-observatory-ok' ]]; then
  xdg-open "$url" >/dev/null 2>&1 &
  exit 0
fi
exec "$repo_dir/.venv/bin/python" "$repo_dir/app.py" --serve
