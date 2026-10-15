#!/usr/bin/env python3
"""Render a rotating, memory-backed Bokeh map of the local factory."""

from __future__ import annotations

import argparse
import hashlib
import html
import math
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from bokeh.embed import file_html
from bokeh.events import DocumentReady
from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, CustomJS, Div, HoverTool, LabelSet, Range1d, Slider, TapTool, Toggle
from bokeh.plotting import figure
from bokeh.resources import INLINE
from jinja2 import Template

from memory_map import ROOTS, HOST_NAME, GALAXY_PATH, build_catalog, read_activities, recent_links


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "build" / "factory-observatory.html"
ROOT_COLORS = {
    "PTINTERNAL": "#7ed6c3", "Hindsight": "#6d9fff", "Projects": "#e99e70",
    "Job artifacts": "#a18dff", "Deliverables": "#e7c46b",
}
AGENT_COLORS = {
    "codex": "#f5a86b", "rend": "#61d6c5",
    "progre": "#c798ff", "imagen": "#ff7d9d",
}
ACTION_COLORS = {"modified": "#ffc978", "created": "#ee8cae", "accessed": "#90d8c6", "referenced": "#8396ae"}
ACTIVE_ROLES = ("codex", "rend", "progre", "imagen")
ROOT_CENTERS = {
    label: (4.8 * math.sin(index * 2 * math.pi / len(ROOTS)),
            4.5 * math.cos(index * 2 * math.pi / len(ROOTS)),
            0.6 * math.sin(index * 2.4))
    for index, (label, _) in enumerate(ROOTS)
}


def _hash01(value: str, offset: int = 0) -> float:
    digest = hashlib.sha256(value.encode()).digest()
    return int.from_bytes(digest[offset:offset + 4], "big") / 0xFFFFFFFF


def _project(x: float, y: float, z: float, angle: float) -> tuple[float, float, float]:
    ca, sa = math.cos(angle), math.sin(angle)
    xr, zr = x * ca - z * sa, x * sa + z * ca
    tilt = 0.24
    yr = y * math.cos(tilt) - zr * math.sin(tilt)
    depth = y * math.sin(tilt) + zr * math.cos(tilt)
    factor = 1 / max(0.72, 1 + depth * 0.025)
    return xr * factor, yr * factor, depth


def _build_scene(files, active_agents):
    author_order = list(ACTIVE_ROLES)
    nodes = {key: [] for key in ("id", "orbit_parent", "x", "y", "depth", "bx", "by", "bz", "size", "color", "alpha", "name", "kind", "detail", "action", "memory", "path", "root", "memory_project")}
    labels = {key: [] for key in ("x", "y", "bx", "by", "bz", "text", "color", "kind")}
    node_index: dict[str, int] = {}
    position: dict[str, tuple[float, float, float]] = {}

    def node(key, name, kind, detail, action, memory, xyz, size, color, alpha=0.92, label=False, path="", root="", memory_project="", orbit_parent=""):
        px, py, depth = _project(*xyz, 0.35)
        node_index[key] = len(nodes["x"])
        position[key] = xyz
        for column, value in {
            "id": key, "orbit_parent": orbit_parent,
            "x": px, "y": py, "depth": depth, "bx": xyz[0], "by": xyz[1], "bz": xyz[2],
            "size": size, "color": color, "alpha": alpha, "name": name, "kind": kind,
            "detail": detail, "action": action, "memory": memory, "path": path,
            "root": root, "memory_project": memory_project,
        }.items():
            nodes[column].append(value)
        if label:
            for column, value in {"x": px, "y": py + (0.31 if kind == "Directory system" else -0.36), "bx": xyz[0], "by": xyz[1], "bz": xyz[2], "text": name, "color": color, "kind": kind}.items():
                labels[column].append(value)

    node("host", HOST_NAME, "Host", str(GALAXY_PATH), "center", "", (0, 0, 0),
         18, "#f5a86b", label=True, path=str(GALAXY_PATH))
    for label, path in ROOTS:
        node("root:" + label, label, "Directory system", str(path), "", "", ROOT_CENTERS[label], 19,
             ROOT_COLORS[label], label=True, path=str(path), root=label, orbit_parent="host")

    directories = sorted({(item.root, item.directory) for item in files},
                         key=lambda pair: (len(Path(pair[1]).parts), pair[0], pair[1]))
    by_root: dict[str, list[str]] = defaultdict(list)
    for root, directory in directories:
        by_root[root].append(directory)
    counts = Counter(item.directory for item in files)
    child_counts: dict[str, int] = defaultdict(int)
    for root, paths in by_root.items():
        for directory in paths:
            root_path = next(path for label, path in ROOTS if label == root)
            if directory == str(root_path):
                position["dir:" + directory] = ROOT_CENTERS[root]
                continue
            parent_key = "root:" + root
            parent_path = Path(directory).parent
            while parent_path != parent_path.parent:
                candidate = "dir:" + str(parent_path)
                if candidate in node_index:
                    parent_key = candidate
                    break
                parent_path = parent_path.parent
            index = child_counts[parent_key]
            child_counts[parent_key] += 1
            cx, cy, cz = position[parent_key]
            angle = index * 2.399963229728653 + _hash01(directory) * 0.5
            radius = 0.58 + 0.12 * math.sqrt(index + 1)
            xyz = (cx + radius * math.cos(angle), cy + radius * math.sin(angle) * 0.82, cz + (_hash01(directory, 4) - 0.5) * 1.1)
            name = Path(directory).name or directory
            node("dir:" + directory, name, "Remembered directory", directory + " · " + str(counts[directory]) + " remembered files", "", "", xyz, 8.5, ROOT_COLORS[root], 0.82, label=counts[directory] >= 3 and index < 5, path=directory, root=root, orbit_parent=parent_key)

    action_priority = {"referenced": 0, "accessed": 1, "created": 2, "modified": 3}
    for item in files:
        parent = position["dir:" + item.directory]
        theta = _hash01(item.path) * 2 * math.pi
        radius = 0.28 + _hash01(item.path, 4) * 0.38
        xyz = (parent[0] + math.cos(theta) * radius, parent[1] + math.sin(theta) * radius * 0.75, parent[2] + (_hash01(item.path, 8) - 0.5) * 0.9)
        action = max(item.agents.values(), key=lambda value: action_priority[value])
        actors = ", ".join(sorted(item.agents))
        parent_key = "dir:" + item.directory if "dir:" + item.directory in node_index else "root:" + item.root
        node("file:" + item.path, Path(item.path).name, "Remembered file", item.path + " · agents: " + actors, action, ", ".join(item.memory_ids[:4]), xyz, 5.3, ACTION_COLORS[action], 0.78, path=item.path, root=item.root, memory_project=item.memory_projects[0] if item.memory_projects else "", orbit_parent=parent_key)

    for index, agent in enumerate(author_order):
        theta = index * 2 * math.pi / max(1, len(author_order)) + 0.13
        xyz = (1.72 * math.cos(theta), 1.55 * math.sin(theta), (_hash01(agent) - 0.5) * 0.8)
        has_files = agent in active_agents
        node("agent:" + agent, "Odexi" if agent == "codex" else agent.title(), "Agent", "Shared reviewed file references: " + str(sum(agent in item.agents for item in files)), "", "", xyz, 11.5, AGENT_COLORS.get(agent, "#aab9ce"), 0.96 if has_files else 0.42, label=agent in ACTIVE_ROLES or has_files, orbit_parent="host")

    links = {key: [] for key in ("xs", "ys", "source_idx", "target_idx", "color", "alpha", "size")}
    for agent, file_path, action in recent_links(files, active_agents):
        source_idx, target_idx = node_index["agent:" + agent], node_index["file:" + file_path]
        for column, value in {
            "xs": [nodes["x"][source_idx], nodes["x"][target_idx]],
            "ys": [nodes["y"][source_idx], nodes["y"][target_idx]],
            "source_idx": source_idx, "target_idx": target_idx,
            "color": AGENT_COLORS.get(agent, "#aab9ce"), "alpha": 0.32, "size": 1.1,
        }.items():
            links[column].append(value)
    return nodes, labels, links, author_order


def _page_html(*, refresh_seconds: int | None = None) -> tuple[str, int, int, int]:
    activities = read_activities()
    files, active_agents = build_catalog(activities)
    nodes, labels, links, authors = _build_scene(files, active_agents)
    node_source = ColumnDataSource(nodes)
    label_source = ColumnDataSource(labels)
    link_source = ColumnDataSource(links)
    bullet_source = ColumnDataSource(dict(x=[], y=[], color=[], size=[]))

    plot = figure(width=1440, height=900, x_range=Range1d(-8.6, 8.6), y_range=Range1d(-6.3, 6.3),
                  tools="pan,wheel_zoom,reset,save,tap", active_scroll="wheel_zoom", toolbar_location="above",
                  background_fill_color="#090d13", border_fill_color="#090d13", outline_line_color="#192633",
                  sizing_mode="stretch_both", min_width=640, min_height=440, match_aspect=True)
    plot.title.text = "MEMORY MAP  ·  FILES NAMED IN REVIEWED ACTIVITY"
    plot.title.text_color = "#cbd8e5"
    plot.title.text_font = "monospace"
    plot.title.text_font_size = "11px"
    plot.axis.visible = False
    plot.grid.visible = False
    plot.min_border = 15

    plot.multi_line(xs="xs", ys="ys", line_color="color", line_alpha="alpha", line_width="size", source=link_source)
    plot.scatter(x="x", y="y", size="size", fill_color="color", line_color="color", fill_alpha=0.94, line_alpha=0.9, source=bullet_source)
    glyph = plot.scatter(x="x", y="y", size="size", fill_color="color", fill_alpha="alpha", line_color="#d6e2ec", line_alpha=0.2,
                         source=node_source, selection_fill_alpha=1, selection_line_color="#ffffff", selection_line_width=1.8,
                         nonselection_fill_alpha=0.22)
    plot.add_layout(LabelSet(x="x", y="y", text="text", text_color="color", text_font="monospace", text_font_size="9px", text_align="center", source=label_source))
    plot.add_tools(HoverTool(renderers=[glyph], tooltips=[("node", "@name"), ("type", "@kind"), ("context", "@detail"), ("memory action", "@action"), ("memory ID", "@memory")]))
    plot.select_one(TapTool).renderers = [glyph]

    info = Div(text="Select a node to inspect the remembered path and agent link.", width_policy="max")
    node_source.selected.js_on_change("indices", CustomJS(args=dict(source=node_source, info=info), code="""
        const i=source.selected.indices[0];
        if(i===undefined) {info.text='Select a node to inspect the remembered path and agent link.'; return;}
        const d=source.data, esc=s=>String(s).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
        info.text='<strong>'+esc(d.name[i])+'</strong> &nbsp; '+esc(d.kind[i])+' &nbsp; '+esc(d.detail[i]);
    """))
    angle = Slider(title="Rotation", start=-180, end=180, step=0.5, value=20, width=220, show_value=False)
    pause = Toggle(label="Pause rotation", active=False, width=150)
    angle.js_on_change("value", CustomJS(args=dict(angle=angle, nodes=node_source, labels=label_source, links=link_source), code="""
        const radians=angle.value*Math.PI/180, ca=Math.cos(radians), sa=Math.sin(radians), tilt=.24;
        const project=(x,y,z)=>{
            const xr=x*ca-z*sa,zr=x*sa+z*ca,yr=y*Math.cos(tilt)-zr*Math.sin(tilt),depth=y*Math.sin(tilt)+zr*Math.cos(tilt);
            const f=1/Math.max(.72,1+depth*.025);return [xr*f,yr*f,depth];
        };
        const n=nodes.data;
        for(let i=0;i<n.x.length;i++) {
            const p=project(n.bx[i],n.by[i],n.bz[i]);n.x[i]=p[0];n.y[i]=p[1];n.depth[i]=p[2];
        }
        nodes.change.emit();
        const l=labels.data;
        for(let i=0;i<l.x.length;i++) {
            const p=project(l.bx[i],l.by[i],l.bz[i]);l.x[i]=p[0];l.y[i]=p[1]+(l.kind[i]==='Directory system'?0.31:-0.36);
        }
        labels.change.emit();
        const e=links.data;
        for(let i=0;i<e.xs.length;i++) {
            const a=e.source_idx[i],b=e.target_idx[i];e.xs[i]=[n.x[a],n.x[b]];e.ys[i]=[n.y[a],n.y[b]];
        }
        links.change.emit();
    """))

    title = Div(text="<span class='mark'>◉</span> &nbsp; CONSTELLATION BY PROGRETECH <span class='subtitle'> / SHARED MEMORY</span> <span class='right'>LOCAL · MEMORY SNAPSHOT</span>", height=28)
    scanned = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    summary = Div(text=(f"{len(files)} remembered files &nbsp;·&nbsp; {len({item.directory for item in files})} directories &nbsp;·&nbsp; "
                        f"{len(active_agents)} agents with file references &nbsp;·&nbsp; {len(activities)} reviewed activity records &nbsp;·&nbsp; refreshed {html.escape(scanned)}"),
                  height=20)
    legend = Div(text="<span class='created'>● created</span> &nbsp; <span class='modified'>● modified</span> &nbsp; <span class='accessed'>● accessed</span> &nbsp; <span class='referenced'>● referenced</span> &nbsp; · &nbsp; moving lights connect agents to remembered files; each agent's latest seven visible references are linked", height=24)
    controls = row(pause, angle, sizing_mode="stretch_width")
    page = column(title, plot, controls, info, legend, summary, sizing_mode="stretch_both")

    page.js_on_event(DocumentReady, CustomJS(args=dict(angle=angle, pause=pause, bullets=bullet_source, links=link_source), code="""
        if(window.__factoryObservatoryMotion) window.clearInterval(window.__factoryObservatoryMotion);
        let frame=0;
        window.__factoryObservatoryMotion=window.setInterval(()=>{
            if(pause.active) return;
            angle.value=angle.value<=-179.5?180:angle.value-0.5;
            frame++;
            const e=links.data,b={x:[],y:[],color:[],size:[]};
            for(let i=0;i<e.xs.length;i++) {
                const phase=((frame*.018+i*.137)%1),t=phase<.5?phase*2:(1-phase)*2;
                b.x.push(e.xs[i][0]+(e.xs[i][1]-e.xs[i][0])*t);
                b.y.push(e.ys[i][0]+(e.ys[i][1]-e.ys[i][0])*t);
                b.color.push(e.color[i]);b.size.push(4.8);
            }
            bullets.data=b;
        },80);
    """))

    css = """
      :root { color-scheme:dark; } html,body{background:#090d13;margin:0;height:100%;overflow:hidden;color:#cbd8e5;font:11px ui-monospace,monospace;}
      body{padding:10px 18px 8px;box-sizing:border-box;} .bk-root{height:100vh;} .mark{color:#f5a86b;text-shadow:0 0 8px #f5a86b;}
      .subtitle{color:#74889c}.right{float:right;color:#72899d}.created{color:#ee8cae}.modified{color:#ffc978}.accessed{color:#90d8c6}.referenced{color:#8396ae}
      .bk-btn,.bk-input{background:#121d29 !important;color:#cbd8e5 !important;border-color:#2a3b4e !important;}
    """
    refresh_tag = f'<meta http-equiv="refresh" content="{refresh_seconds}">' if refresh_seconds else ""
    template = Template("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }}</title>{{ refresh_tag }}{{ bokeh_css }}<style>{{ css }}</style>{{ bokeh_js }}</head><body>{{ plot_div }}{{ plot_script }}</body></html>""")
    document = file_html(page, INLINE, "Constellation by ProgreTech · shared memory", template=template,
                         template_variables={"css": css, "refresh_tag": refresh_tag})
    return document, len(files), len({item.directory for item in files}), len(active_agents)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", nargs="?", const=8765, type=int, help="serve a refreshing local page on 127.0.0.1")
    parser.add_argument("--refresh-seconds", type=int, default=120)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    if args.refresh_seconds < 30:
        parser.error("--refresh-seconds must be at least 30")
    if args.serve is None:
        document, file_count, directory_count, agent_count = _page_html()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(document)
        print(f"Wrote {OUTPUT} from shared Hindsight: {file_count} files, {directory_count} directories, {agent_count} linked agents")
        if not args.no_open:
            webbrowser.open(OUTPUT.as_uri())
        return

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", "22")
                self.end_headers()
                self.wfile.write(b"factory-observatory-ok")
                return
            if self.path != "/":
                self.send_error(404)
                return
            try:
                document, _, _, _ = _page_html(refresh_seconds=args.refresh_seconds)
            except RuntimeError:
                self.send_error(503, "Hindsight retrieval failed")
                return
            data = document.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *arguments):
            pass

    address = f"http://127.0.0.1:{args.serve}/"
    print(f"Serving {address}; shared memory will be reread on page refresh", flush=True)
    with HTTPServer(("127.0.0.1", args.serve), Handler) as server:
        if not args.no_open:
            webbrowser.open(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
