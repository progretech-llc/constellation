#!/usr/bin/env python3
"""Build a self-contained Bokeh demo of a factory activity cluster map."""

from __future__ import annotations

import json
import math
import webbrowser
from pathlib import Path

from jinja2 import Template
from bokeh.embed import file_html
from bokeh.models import (
    Button,
    ColumnDataSource,
    CustomJS,
    Div,
    HoverTool,
    LabelSet,
    Range1d,
    Select,
    Slider,
    TapTool,
    Toggle,
)
from bokeh.plotting import figure
from bokeh.resources import INLINE


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "build" / "factory-observatory-demo.html"

COLORS = {
    "Codex": "#f4a261",
    "Rend": "#55d6be",
    "Lyra": "#f1c75b",
    "Mak": "#77a9ff",
    "Progre": "#c38bff",
    "Imagen": "#ff7a9c",
    "Moxy": "#67d6e8",
    "Rend workspace": "#62dbc3",
    "PT_CONTEXT": "#79a8ff",
    "Git · ProgreTech org": "#f1a85b",
    "Cloud services": "#c58cff",
    "Local home": "#ff7b9d",
}

# Positions are deliberately stable between views. Files are synthetic points
# around each resource cluster; roles sit between the central orchestrator and
# the clusters they are shown coordinating with in this illustrative scene.
RESOURCES = [
    {"name": "Rend workspace", "label": "/home/edwin/ptinternal", "x": -4.6, "y": 1.8, "z": -1.5, "count": 42, "kind": "Local workspace"},
    {"name": "PT_CONTEXT", "label": "/mnt/pt-context", "x": 0.0, "y": 4.0, "z": 0.4, "count": 48, "kind": "Mounted project storage"},
    {"name": "Git · ProgreTech org", "label": "github.com/progretech-llc", "x": 4.6, "y": 1.7, "z": -0.7, "count": 40, "kind": "Remote repositories"},
    {"name": "Cloud services", "label": "Google Cloud · configured services", "x": 3.4, "y": -3.0, "z": 1.6, "count": 34, "kind": "Remote services"},
    {"name": "Local home", "label": "/home/edwin", "x": -3.8, "y": -3.1, "z": 0.8, "count": 38, "kind": "Local files"},
]
AGENTS = [
    {"name": "Codex", "x": 0.0, "y": 0.0, "z": 2.4, "kind": "Orchestrator · logical role", "resource": "Factory overview"},
    {"name": "Rend", "x": -3.0, "y": 0.0, "z": 0.4, "kind": "SRE · logical role", "resource": "Rend workspace"},
    {"name": "Lyra", "x": -1.4, "y": 2.2, "z": 0.2, "kind": "Research · logical role", "resource": "PT_CONTEXT"},
    {"name": "Mak", "x": 2.0, "y": 2.0, "z": -0.3, "kind": "Engineering · logical role", "resource": "Git · ProgreTech org"},
    {"name": "Progre", "x": 2.5, "y": -0.7, "z": 0.7, "kind": "Research · logical role", "resource": "Cloud services"},
    {"name": "Imagen", "x": -2.1, "y": -1.0, "z": 1.2, "kind": "Visual design · logical role", "resource": "PT_CONTEXT"},
    {"name": "Moxy", "x": 0.2, "y": -2.6, "z": -0.4, "kind": "SQA planning · logical role", "resource": "Rend workspace"},
]


def project(x: float, y: float, z: float, angle: float, view: str) -> tuple[float, float, float]:
    """Project a stable 3D scene into Bokeh's 2D scatter coordinates."""
    if view == "Areas":
        return x, y, z
    if view == "Relations":
        return x * 0.84, y * 0.84 + z * 0.38, z
    if view == "Timeline":
        return x, y * 0.25 + (z + 2.0) * 0.15, z
    ca, sa = math.cos(angle), math.sin(angle)
    xr = x * ca - z * sa
    zr = x * sa + z * ca
    tilt = 0.29
    yr = y * math.cos(tilt) - zr * math.sin(tilt)
    depth = y * math.sin(tilt) + zr * math.cos(tilt)
    perspective = 1.0 / max(0.48, 1.0 + depth * 0.045)
    return xr * perspective, yr * perspective, depth


def build_data(angle: float, view: str) -> tuple[dict[str, list], dict[str, list], dict[str, list]]:
    nodes = {key: [] for key in ("x", "y", "size", "color", "alpha", "name", "detail", "kind", "node_id", "z", "base_x", "base_y", "base_z", "base_size", "base_alpha")}
    lines = {key: [] for key in ("xs", "ys", "color", "alpha", "width", "name", "kind")}
    labels = {key: [] for key in ("x", "y", "text", "color", "dy")}

    def add_node(name: str, detail: str, kind: str, node_id: str, xyz: tuple[float, float, float], size: float, color: str, alpha: float = 0.9) -> None:
        px, py, depth = project(*xyz, angle, view)
        depth_scale = 1 + max(-1.4, min(1.4, depth * 0.04))
        nodes["x"].append(px)
        nodes["y"].append(py)
        nodes["z"].append(depth)
        nodes["size"].append(max(3, size * depth_scale))
        nodes["color"].append(color)
        nodes["alpha"].append(alpha * (0.84 if depth < -1 else 1))
        nodes["name"].append(name)
        nodes["detail"].append(detail)
        nodes["kind"].append(kind)
        nodes["node_id"].append(node_id)
        nodes["base_x"].append(xyz[0])
        nodes["base_y"].append(xyz[1])
        nodes["base_z"].append(xyz[2])
        nodes["base_size"].append(size)
        nodes["base_alpha"].append(alpha)

    centers = {r["name"]: r for r in RESOURCES}
    orchestrator = next(agent for agent in AGENTS if agent["name"] == "Codex")
    for index, resource in enumerate(RESOURCES):
        color = COLORS[resource["name"]]
        # A compact center marks each resource. The surrounding scatter reads as
        # representative files/items without implying exact inventory counts.
        add_node(resource["name"], resource["label"], resource["kind"], "resource:" + resource["name"], (resource["x"], resource["y"], resource["z"]), 20, color)
        labels["x"].append(project(resource["x"], resource["y"], resource["z"], angle, view)[0])
        labels["y"].append(project(resource["x"], resource["y"], resource["z"], angle, view)[1] + 0.72)
        labels["text"].append(resource["name"])
        labels["color"].append(color)
        labels["dy"].append(0.72)
        for j in range(resource["count"]):
            # Golden-angle pattern creates visibly organic but repeatable clouds.
            theta = j * 2.399963229728653 + index * 0.63
            radius = 0.55 + 0.12 * math.sqrt(j + 1)
            dx = math.cos(theta) * radius
            dy = math.sin(theta) * radius * 0.74
            dz = math.sin(theta * 1.71) * (0.45 + 0.025 * (j % 7))
            add_node(f"{resource['name']} item {j + 1:02d}", f"Representative item · {resource['label']}", "Synthetic resource point", f"item:{resource['name']}:{j}", (resource["x"] + dx, resource["y"] + dy, resource["z"] + dz), 4.1 + (j % 3) * 0.55, color, 0.68)

    for agent in AGENTS:
        color = COLORS[agent["name"]]
        add_node(agent["name"], agent["kind"], agent["kind"], "agent:" + agent["name"], (agent["x"], agent["y"], agent["z"]), 14, color)
        point = project(agent["x"], agent["y"], agent["z"], angle, view)
        labels["x"].append(point[0])
        labels["y"].append(point[1] - 0.42)
        labels["text"].append(agent["name"])
        labels["color"].append(color)
        labels["dy"].append(-0.42)
        # Dashed relation lines show declared illustrative map links only.
        if agent["name"] != "Codex":
            target = centers[agent["resource"]]
            p1 = project(agent["x"], agent["y"], agent["z"], angle, view)
            p2 = project(target["x"], target["y"], target["z"], angle, view)
            lines["xs"].append([p1[0], p2[0]])
            lines["ys"].append([p1[1], p2[1]])
            lines["color"].append(color)
            lines["alpha"].append(0.28)
            lines["width"].append(1.3)
            lines["name"].append(agent["name"] + " ↔ " + agent["resource"])
            lines["kind"].append("Illustrative role/resource relationship · not observed access")
            hub = project(orchestrator["x"], orchestrator["y"], orchestrator["z"], angle, view)
            lines["xs"].append([hub[0], p1[0]])
            lines["ys"].append([hub[1], p1[1]])
            lines["color"].append(color)
            lines["alpha"].append(0.12)
            lines["width"].append(1.0)
            lines["name"].append("Codex ↔ " + agent["name"])
            lines["kind"].append("Illustrative orchestration relationship · not observed activity")

    return nodes, lines, labels


def main() -> None:
    events = json.loads((ROOT / "sample_data" / "demo_events.json").read_text())
    angle = 0.48
    view = "Cluster 3D"
    node_data, line_data, label_data = build_data(angle, view)
    node_source = ColumnDataSource(node_data)
    link_source = ColumnDataSource(line_data)
    label_source = ColumnDataSource(label_data)
    trail_source = ColumnDataSource(dict(xs=[[]], ys=[[]]))
    timeline_xs = [-4.4 + i * (8.8 / max(1, len(events) - 1)) for i in range(len(events))]
    timeline_source = ColumnDataSource(data=dict(
        x=timeline_xs, y=[0] * len(events), color=[COLORS.get(e["actor"], "#dce5ee") for e in events],
        actor=[e["actor"] for e in events], action=[e["action"] for e in events], item=[e["item"] for e in events],
        at=[e["at"] for e in events], source=[e["source"] for e in events], destination=[e["destination"] for e in events],
    ))
    timeline_label_source = ColumnDataSource(data=dict(
        x=timeline_xs, y=[0] * len(events), text=[f'{e["at"]}  ·  {e["actor"]} {e["action"]}' for e in events],
        color=[COLORS.get(e["actor"], "#dce5ee") for e in events],
    ))

    plot = figure(
        width=1280,
        height=800,
        x_range=Range1d(-8.8, 8.8),
        y_range=Range1d(-6.1, 6.1),
        tools="pan,wheel_zoom,reset,save,tap",
        active_scroll="wheel_zoom",
        toolbar_location="above",
        background_fill_color="#080c11",
        border_fill_color="#080c11",
        outline_line_color="#18222d",
        sizing_mode="stretch_both",
        min_width=620,
        min_height=420,
        match_aspect=True,
    )
    plot.axis.visible = False
    plot.grid.visible = False
    plot.title.text = "FACTORY ACTIVITY MAP  ·  CLUSTER VIEW"
    plot.title.text_color = "#d8e1e9"
    plot.title.text_font = "monospace"
    plot.title.text_font_size = "12px"
    plot.title.align = "left"
    plot.min_border_left = 20
    plot.min_border_right = 24
    plot.min_border_top = 10
    plot.min_border_bottom = 16

    # Fine points sit behind the explicit relationship and transfer paths.
    link_glyph = plot.multi_line(xs="xs", ys="ys", source=link_source, line_color="color", line_alpha="alpha", line_width="width")
    trail = plot.multi_line(xs="xs", ys="ys", source=trail_source, line_color="#ffffff", line_alpha=0.95, line_width=3.4)
    timeline_axis_source = ColumnDataSource(data=dict(x=[-5.2, 5.2], y=[0, 0]))
    timeline_axis = plot.line(x="x", y="y", source=timeline_axis_source, line_color="#344454", line_alpha=0.7, line_width=1.2, visible=False)
    timeline_glyph = plot.scatter(x="x", y="y", size=18, fill_color="color", line_color="#dce5ee", line_alpha=0.72, source=timeline_source, visible=False, selection_fill_color="#ffffff", selection_fill_alpha=1, selection_line_color="#ffffff", selection_line_width=2, nonselection_fill_alpha=0.34)
    timeline_labels = LabelSet(x="x", y="y", text="text", text_color="color", text_font="monospace", text_font_size="10px", text_align="center", y_offset=15, source=timeline_label_source, visible=False)
    plot.add_layout(timeline_labels)
    glyph = plot.scatter(x="x", y="y", size="size", fill_color="color", fill_alpha="alpha", line_color="#d9e5ef", line_alpha=0.26, line_width=0.6, source=node_source, selection_fill_alpha=1.0, selection_line_color="#ffffff", selection_line_width=2.1, nonselection_fill_alpha=0.22, nonselection_line_alpha=0.08)
    labels = LabelSet(x="x", y="y", text="text", text_color="color", text_font="monospace", text_font_size="10px", text_font_style="bold", text_align="center", source=label_source, y_offset="dy")
    plot.add_layout(labels)

    plot.add_tools(HoverTool(renderers=[glyph], tooltips=[
        ("node", "@name"), ("kind", "@kind"), ("detail", "@detail"), ("depth", "@z{0.0}")
    ], point_policy="snap_to_data"))
    tap = plot.select_one(TapTool)
    tap.renderers = [glyph, timeline_glyph]
    plot.add_tools(HoverTool(renderers=[timeline_glyph], tooltips=[("time", "@at"), ("actor", "@actor"), ("operation", "@action @item"), ("from", "@source"), ("to", "@destination")]))

    inspector = Div(text="<span class='muted'>Select a point to inspect its role or resource.</span>", css_classes=["inspector"])
    node_source.selected.js_on_change("indices", CustomJS(args=dict(source=node_source, inspector=inspector), code="""
        const i = source.selected.indices[0];
        if (i === undefined) { inspector.text = "<span class='muted'>Select a point to inspect its role or resource.</span>"; return; }
        const d = source.data;
        inspector.text = `<span class='eyebrow'>${d.kind[i]}</span><br><strong>${d.name[i]}</strong><br><span class='muted'>${d.detail[i]}</span>`;
    """))

    status = Div(text="<span class='live-dot'></span> DEMO DATA · No workstation or agent events connected", css_classes=["status"])
    event_detail = Div(text="Sample transfer replay is paused.", css_classes=["event-detail"])
    angle_slider = Slider(title="View angle", start=-180, end=180, value=27, step=1, width=260, show_value=False)
    layout_select = Select(title="Layout", value="Cluster 3D", options=["Cluster 3D", "Areas", "Relations", "Timeline"], width=200)
    animate = Toggle(label="Replay sample events", active=False, button_type="default", width=184)
    next_event = Button(label="Next sample event", button_type="primary", width=156)

    refresh = CustomJS(args=dict(node_source=node_source, link_source=link_source, label_source=label_source, trail_source=trail_source, timeline_source=timeline_source, angle=angle_slider, layout_select=layout_select, status=status, event_detail=event_detail), code="""
        const resources = __RESOURCES__;
        const agents = __AGENTS__;
        const view = layout_select.value;
        const radians = angle.value * Math.PI / 180;
        const project = (x, y, z) => {
            if (view === 'Areas') return [x, y, z];
            if (view === 'Relations') return [x * .84, y * .84 + z * .38, z];
            if (view === 'Timeline') return [x, y * .25 + (z + 2) * .15, z];
            const ca = Math.cos(radians), sa = Math.sin(radians);
            const xr = x * ca - z * sa, zr = x * sa + z * ca;
            const tilt = .29;
            const yr = y * Math.cos(tilt) - zr * Math.sin(tilt);
            const depth = y * Math.sin(tilt) + zr * Math.cos(tilt);
            const perspective = 1 / Math.max(.48, 1 + depth * .045);
            return [xr * perspective, yr * perspective, depth];
        };
        const nd = node_source.data;
        const put = (i, p) => {
            const scale = 1 + Math.max(-1.4, Math.min(1.4, p[2] * .04));
            nd.x[i] = p[0]; nd.y[i] = p[1]; nd.z[i] = p[2];
            nd.size[i] = Math.max(3, nd.base_size[i] * scale);
            nd.alpha[i] = nd.base_alpha[i] * (p[2] < -1 ? .84 : 1);
        };
        for (let i = 0; i < nd.x.length; i++) put(i, project(nd.base_x[i], nd.base_y[i], nd.base_z[i]));
        node_source.change.emit();

        const ld = label_source.data;
        for (let i = 0; i < resources.length; i++) {
            const p = project(resources[i].x, resources[i].y, resources[i].z);
            ld.x[i] = p[0]; ld.y[i] = p[1] + ld.dy[i];
        }
        for (let i = 0; i < agents.length; i++) {
            const p = project(agents[i].x, agents[i].y, agents[i].z), j = resources.length + i;
            ld.x[j] = p[0]; ld.y[j] = p[1] + ld.dy[j];
        }
        label_source.change.emit();

        const lines = {xs: [], ys: [], color: [], alpha: [], width: [], name: [], kind: []};
        const byName = Object.fromEntries(resources.map(r => [r.name, r]));
        for (const a of agents) {
            if (a.name === 'Codex') continue;
            const target = byName[a.resource];
            const p1 = project(a.x, a.y, a.z), p2 = project(target.x, target.y, target.z);
            lines.xs.push([p1[0],p2[0]]); lines.ys.push([p1[1],p2[1]]);
            lines.color.push(a.color); lines.alpha.push(.28); lines.width.push(1.3);
            lines.name.push(a.name + ' ↔ ' + a.resource);
            lines.kind.push('Illustrative role/resource relationship · not observed access');
            const hub = agents.find(agent => agent.name === 'Codex'), hp = project(hub.x, hub.y, hub.z);
            lines.xs.push([hp[0],p1[0]]); lines.ys.push([hp[1],p1[1]]);
            lines.color.push(a.color); lines.alpha.push(.12); lines.width.push(1.0);
            lines.name.push('Codex ↔ ' + a.name);
            lines.kind.push('Illustrative orchestration relationship · not observed activity');
        }
        link_source.data = lines;
        trail_source.data = {xs: [[]], ys: [[]]};
        timeline_source.selected.indices = [];
        status.text = "<span class='live-dot'></span> DEMO DATA · No workstation or agent events connected";
        event_detail.text = view === 'Timeline' ? 'Timeline layout is illustrative; sample event order is shown with Next sample event.' : 'Sample transfer replay is paused.';
    """.replace("__RESOURCES__", json.dumps(RESOURCES)).replace("__AGENTS__", json.dumps([{**a, "color": COLORS[a["name"]]} for a in AGENTS])))
    angle_slider.js_on_change("value", refresh)
    layout_select.js_on_change("value", refresh)
    layout_select.js_on_change("value", CustomJS(args=dict(layout_select=layout_select, glyph=glyph, links=link_glyph, labels=labels, timeline_glyph=timeline_glyph, timeline_labels=timeline_labels, timeline_axis=timeline_axis, status=status, event_detail=event_detail), code="""
        const timeline=layout_select.value==='Timeline';
        glyph.visible=!timeline; links.visible=!timeline; labels.visible=!timeline;
        timeline_glyph.visible=timeline; timeline_labels.visible=timeline; timeline_axis.visible=timeline;
        status.text=timeline ? "<span class='live-dot'></span> SYNTHETIC EVENT TIMELINE · sample sequence only" : "<span class='live-dot'></span> DEMO DATA · No workstation or agent events connected";
        event_detail.text=timeline ? 'Synthetic sample events are ordered by time. Hover a point for its transfer path.' : 'Sample transfer replay is paused.';
    """))

    demo_events = events
    event_index = ColumnDataSource(data=dict(value=[0]))
    event_code = """
        const events=__EVENTS__, resources=__RESOURCES__, agents=__AGENTS__;
        const idx=event_index.data.value[0] % events.length, e=events[idx];
        event_index.data={value:[idx+1]};
        const angle=angle_slider.value*Math.PI/180, view=layout_select.value;
        const project=(x,y,z)=>{
            if(view==='Areas') return [x,y,z];
            if(view==='Relations') return [x*.84,y*.84+z*.38,z];
            const ca=Math.cos(angle),sa=Math.sin(angle),xr=x*ca-z*sa,zr=x*sa+z*ca,tilt=.29;
            const yr=y*Math.cos(tilt)-zr*Math.sin(tilt),depth=y*Math.sin(tilt)+zr*Math.cos(tilt),scale=1/Math.max(.48,1+depth*.045);
            return [xr*scale,yr*scale,depth];
        };
        const a=agents.find(x=>x.name===e.actor),s=resources.find(x=>x.name===e.source_resource),d=resources.find(x=>x.name===e.destination_resource);
        const p1=project(a.x,a.y,a.z),p2=project(s.x,s.y,s.z),p3=project(d.x,d.y,d.z);
        const mx=(p2[0]+p3[0])/2,my=(p2[1]+p3[1])/2+1.15;
        if(view==='Timeline') { timeline_source.selected.indices=[idx]; trail_source.data={xs:[[]],ys:[[]]}; }
        else { timeline_source.selected.indices=[]; trail_source.data={xs:[[p1[0],mx,p3[0]]],ys:[[p1[1],my,p3[1]]]}; }
        status.text=`<span class='live-dot'></span> SYNTHETIC DEMO EVENT ${idx+1}/${events.length}`;
        event_detail.text=`<span class='event-actor'>${e.actor}</span> · ${e.action} <strong>${e.item}</strong> &nbsp; ${e.source} → ${e.destination} <span class='muted'>· ${e.at}</span>`;
    """.replace("__EVENTS__", json.dumps(demo_events)).replace("__RESOURCES__", json.dumps(RESOURCES)).replace("__AGENTS__", json.dumps(AGENTS))
    next_event.js_on_click(CustomJS(args=dict(trail_source=trail_source, timeline_source=timeline_source, status=status, event_detail=event_detail, event_index=event_index, angle_slider=angle_slider, layout_select=layout_select), code=event_code))
    animate.js_on_change("active", CustomJS(args=dict(toggle=animate, trail_source=trail_source, timeline_source=timeline_source, status=status, event_detail=event_detail, event_index=event_index, angle_slider=angle_slider, layout_select=layout_select), code="""
        const advance=()=>{ if(toggle.active) { __EVENT_BODY__ } };
        if(window.__factoryObservatoryTimer) window.clearInterval(window.__factoryObservatoryTimer);
        if(toggle.active) window.__factoryObservatoryTimer=window.setInterval(advance,1500);
    """.replace("__EVENT_BODY__", event_code).replace("__EVENTS__", json.dumps(demo_events)).replace("__RESOURCES__", json.dumps(RESOURCES)).replace("__AGENTS__", json.dumps(AGENTS))))

    toolbar = Div(text="<span class='brand-mark'>●</span>&nbsp;&nbsp;<span class='brand'>CONSTELLATION BY PROGRETECH</span>&nbsp;&nbsp; <span class='subtitle'>LOCAL WORKBENCH MAP</span><span class='toolbar-spacer'></span><span class='privacy'>LOCAL DEMO · NO CONNECTORS</span>", css_classes=["toolbar"])
    footnote = Div(text="<span class='key-dot' style='color:#f4a261'>●</span> Orchestrator &nbsp; <span class='key-dot' style='color:#77a9ff'>●</span> Logical agents &nbsp; <span class='key-dot' style='color:#62dbc3'>●</span> Resource clusters &nbsp; <span class='line-key'>━</span> Illustrative relationship &nbsp; <span class='trail-key'>━</span> Sample transfer", css_classes=["legend"])
    from bokeh.layouts import column, row
    control_row = row(layout_select, angle_slider, animate, next_event, sizing_mode="stretch_width", css_classes=["control-row"])
    footer = column(control_row, row(event_detail, sizing_mode="stretch_width"), row(inspector, sizing_mode="stretch_width"), footnote, status, sizing_mode="stretch_width", css_classes=["footer"])
    page = column(toolbar, plot, footer, sizing_mode="stretch_both", css_classes=["app-shell"])

    css = """
    :root { color-scheme: dark; }
    html, body { background:#080c11; margin:0; height:100%; overflow:hidden; }
    body { color:#c6d0db; font-family:Inter,ui-sans-serif,system-ui,sans-serif; }
    .bk-root { height:100vh; }
    .app-shell { height:100vh; padding:0 22px 16px; box-sizing:border-box; }
    .toolbar { height:43px; min-height:43px; display:flex; align-items:center; gap:11px; border-bottom:1px solid #1c2731; color:#8290a0; font:10px ui-monospace,monospace; letter-spacing:1.5px; }
    .brand-mark { color:#62dbc3; font-size:13px; text-shadow:0 0 10px #62dbc3; }
    .brand { color:#d6e0ea; font-weight:650; letter-spacing:2px; }
    .subtitle { color:#596a7c; margin-left:8px; }
    .toolbar-spacer { flex:1; }
    .privacy { color:#7a8c9b; border:1px solid #273441; padding:5px 8px; border-radius:3px; font-size:9px; }
    .footer { gap:6px; padding:3px 0 0; }
    .control-row { align-items:center; gap:12px; border-top:1px solid #18232d; padding-top:8px; }
    .legend { color:#718093; font:10px ui-monospace,monospace; padding:1px 0; }
    .key-dot { font-size:9px; }
    .line-key { color:#7f8e9d; }
    .trail-key { color:#fff; }
    .status,.event-detail,.inspector { color:#a8b5c2; font:11px ui-monospace,monospace; min-height:17px; }
    .status { color:#e7b766; }
    .live-dot { color:#e7b766; text-shadow:0 0 8px #e7b766; padding-right:7px; }
    .event-actor { color:#77a9ff; }
    .muted { color:#68798b; }
    .eyebrow { color:#62dbc3; text-transform:uppercase; font-size:9px; letter-spacing:1px; }
    .inspector strong { color:#e4ebf1; font-weight:600; }
    .bk-input-group label { color:#76889a !important; font:9px ui-monospace,monospace !important; text-transform:uppercase; letter-spacing:1px; }
    .bk-input,.bk-input-group select,.bk-btn,.bk-slider-title { background:#0d141c !important; color:#c8d2dd !important; border-color:#263442 !important; }
    .bk-btn { font:10px ui-monospace,monospace !important; letter-spacing:.4px; }
    .bk-btn-primary { background:#173047 !important; border-color:#285174 !important; }
    .bk-toolbar-button { color:#8394a5 !important; }
    .bk-slider-title { font-size:9px !important; text-transform:uppercase; }
    .bk-tooltip { background:#101923 !important; color:#d7e0e8 !important; }
    """
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    html = file_html(page, INLINE, "Constellation by ProgreTech · Demo", template=Template("""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }}</title>{{ bokeh_css }}<style>{{ css }}</style>{{ bokeh_js }}</head><body>{{ plot_div }}{{ plot_script }}</body></html>"""), template_variables={"css": css})
    OUTPUT.write_text(html)
    print(f"Wrote {OUTPUT}")
    webbrowser.open(OUTPUT.as_uri())


if __name__ == "__main__":
    main()
