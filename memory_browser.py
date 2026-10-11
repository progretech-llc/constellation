#!/usr/bin/env python3
"""Open a temporary, local, read-only browser view of one MemPalace author."""

from __future__ import annotations

import html
import secrets
import subprocess
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

from mempalace_planets import MemoryPlanet, read_recent


def render_page(records: list[MemoryPlanet], selected: MemoryPlanet, query: str = "") -> str:
    same_author = [record for record in records if (record.author_type, record.author) ==
                   (selected.author_type, selected.author)]
    term = query.casefold().strip()
    shown = [record for record in same_author if term in record.title.casefold()]
    esc = html.escape
    rows = ''.join(
        f'<a class="item{" current" if record.short_id == selected.short_id else ""}" '
        f'href="?{urlencode({"memory": record.short_id, "q": query})}">'
        f'<strong>{esc(record.title)}</strong><small>{esc(record.project or record.scope)} · {esc(record.short_id)}</small></a>'
        for record in shown)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Constellation · {esc(selected.author)} memories</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#0d131d;color:#e6eef9;font:14px system-ui,sans-serif}}
header{{padding:18px 24px;border-bottom:1px solid #2a3950;color:#9ed5fa}}header b{{color:#fff;letter-spacing:.08em}}
main{{display:grid;grid-template-columns:minmax(280px,38%) 1fr;gap:14px;padding:16px;height:calc(100vh - 68px)}}
section{{border:1px solid #2b3a51;border-radius:9px;overflow:auto;padding:16px;background:#111a29}}
form{{display:flex;gap:8px;margin-bottom:12px}}input,button{{background:#16253a;color:#eef5ff;border:1px solid #3b5775;border-radius:6px;padding:9px}}
input{{flex:1;min-width:0}}button{{cursor:pointer}}.item{{display:block;text-decoration:none;color:#e6eef9;padding:10px 8px;border-bottom:1px solid #29394c}}
.item:hover,.current{{background:#1a2b43}}small{{display:block;color:#8ca8c6;margin-top:4px}}h1{{font-size:20px;margin:0 0 12px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,monospace;color:#cbd8e8}}
@media(max-width:760px){{main{{display:block;height:auto}}section{{margin-bottom:12px;max-height:70vh}}}}
</style></head><body><header><b>CONSTELLATION BY PROGRETECH</b> · MemPalace review · {esc(selected.author_type)} / {esc(selected.author)}</header>
<main><section><form method="get"><input type="hidden" name="memory" value="{esc(selected.short_id)}"><input name="q" value="{esc(query)}" placeholder="Filter this author’s memories"><button>Filter</button></form>
<small>{len(same_author)} accessible active memories by this author in this snapshot</small>{rows or '<p>No titles match.</p>'}</section>
<section><h1>{esc(selected.title)}</h1><small>{esc(selected.project or selected.scope)} · {esc(selected.short_id)}</small><pre>{esc(selected.raw)}</pre></section></main></body></html>'''


def serve(cli: str, agent: str, selected_id: str, *, open_browser: bool = True,
          idle_seconds: float = 600) -> str:
    if len(selected_id) != 8 or any(c not in '0123456789abcdef' for c in selected_id):
        raise ValueError('Invalid memory planet ID')
    records = read_recent(cli, agent, 5000)
    selected = [record for record in records if record.short_id == selected_id]
    if len(selected) != 1:
        raise LookupError('Memory is no longer available or its short ID is ambiguous')
    token = secrets.token_urlsafe(24)
    deadline = time.monotonic() + idle_seconds

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal deadline
            parsed = urlsplit(self.path)
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}' or parsed.path != f'/{token}/':
                self.send_error(404)
                return
            params = parse_qs(parsed.query)
            wanted = params.get('memory', [selected_id])[0]
            match = [record for record in records if record.short_id == wanted and
                     (record.author_type, record.author) == (selected[0].author_type, selected[0].author)]
            if len(match) != 1:
                self.send_error(404)
                return
            query = params.get('q', [''])[0][:100]
            body = render_page(records, match[0], query).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)
            deadline = time.monotonic() + idle_seconds

        def log_message(self, _format, *_args):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        server.timeout = min(1, idle_seconds)
        url = f'http://127.0.0.1:{server.server_port}/{token}/?{urlencode({"memory": selected_id})}'
        if open_browser:
            webbrowser.open(url)
        while time.monotonic() < deadline:
            server.handle_request()
    return url


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('Usage: memory_browser.py CLI AGENT MEMORY_ID')
    try:
        serve(*sys.argv[1:])
    except (OSError, ValueError, LookupError, subprocess.SubprocessError) as error:
        raise SystemExit(f'Constellation memory view unavailable: {error}') from error
