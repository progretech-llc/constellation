import Cairo from 'cairo';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {DEFAULT_SETTINGS, advancePhase, hitTest, layoutScene, renderGalaxy} from './galaxy.js';

const SCENE_PATH = GLib.build_filenamev([GLib.get_user_state_dir(), 'factory-observatory', 'scene.json']);
const CONFIG_PATH = GLib.build_filenamev([GLib.get_user_config_dir(), 'factory-observatory', 'wallpaper.json']);
const FOREGROUND_PATH = GLib.build_filenamev([GLib.get_user_data_dir(), 'constellation', 'foreground.png']);
const LEGACY_FOREGROUND_PATH = GLib.build_filenamev([GLib.get_user_data_dir(), 'constellation', 'progre-foreground.png']);

function readJson(path) {
    const [ok, bytes] = GLib.file_get_contents(path);
    if (!ok) throw new Error(`Unable to read ${path}`);
    return JSON.parse(new TextDecoder().decode(bytes));
}

export default class FactoryObservatoryWallpaper extends Extension {
    enable() {
        this._scene = null;
        this._foreground = null;
        this._settings = {...DEFAULT_SETTINGS};
        this._areas = [];
        this._phase = 0.22;
        this._motionTime = 0;
        this._focus = null;
        this._lastTick = GLib.get_monotonic_time();
        this._reload();
        this._buildAreas();
        this._tooltip = new St.Label({visible: false, reactive: false,
            style: 'background-color: rgba(8, 15, 31, 0.94); color: #e5f2ff; padding: 8px 12px; border-radius: 8px; font-size: 11px;'});
        Main.uiGroup.add_child(this._tooltip);
        // DING owns the desktop pointer surface on Wayland. A background actor can
        // poll the pointer for hover, but it cannot receive clicks through DING.
        // Expose only the currently hovered star as a Shell UI hit target.
        this._clickTarget = new St.Widget({reactive: true, visible: false,
            style: 'background-color: rgba(0, 0, 0, 0);'});
        this._clickTarget.set_size(24, 24);
        this._clickTarget.connect('button-press-event', (_actor, event) => this._onCaptured(event));
        Main.uiGroup.add_child(this._clickTarget);
        this._captureId = global.stage.connect('captured-event', (_actor, event) => this._onCaptured(event));
        this._monitorId = Main.layoutManager.connect('monitors-changed', () => this._buildAreas());
        this._refreshId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this._reload();
            return GLib.SOURCE_CONTINUE;
        });
        this._tickId = GLib.timeout_add(GLib.PRIORITY_LOW, 125, () => {
            const now = GLib.get_monotonic_time();
            const elapsed = Math.min(0.5, Math.max(0, (now - this._lastTick) / 1_000_000));
            this._lastTick = now;
            if (this._settings.enabled !== false && this._settings.paused !== true) {
                this._phase = advancePhase(this._phase, elapsed, this._settings.rotation_speed);
                this._motionTime += elapsed;
                for (const area of this._areas) area.queue_repaint();
            }
            this._updateHover();
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        if (this._captureId) global.stage.disconnect(this._captureId);
        this._captureId = null;
        this._clickTarget?.destroy();
        this._clickTarget = null;
        this._tooltip?.destroy();
        this._tooltip = null;
        for (const id of [this._tickId, this._refreshId]) {
            if (id) GLib.Source.remove(id);
        }
        if (this._monitorId) Main.layoutManager.disconnect(this._monitorId);
        this._tickId = null;
        this._refreshId = null;
        this._monitorId = null;
        for (const area of this._areas ?? []) area.destroy();
        this._areas = [];
        this._scene = null;
        this._foreground = null;
        this._focus = null;
    }

    _reload() {
        try {
            const raw = readJson(CONFIG_PATH);
            const speed = Number(raw.rotation_speed);
            this._settings = {
                enabled: raw.enabled !== false,
                paused: raw.paused === true,
                foreground: raw.foreground !== false,
                rotation_speed: Number.isFinite(speed) ? Math.max(0, Math.min(5, speed)) : DEFAULT_SETTINGS.rotation_speed,
                glow: this._clamp(raw.glow, DEFAULT_SETTINGS.glow),
                rays: this._clamp(raw.rays, DEFAULT_SETTINGS.rays),
                density: this._clamp(raw.density, DEFAULT_SETTINGS.density),
                links: raw.links !== false,
                labels: raw.labels !== false,
            };
        } catch (_error) {
            this._settings = {...DEFAULT_SETTINGS};
        }
        try {
            const scene = readJson(SCENE_PATH);
            if (scene.schema === 'factory-observatory-wallpaper/v1' && Array.isArray(scene.nodes) && Array.isArray(scene.links))
                this._scene = scene;
        } catch (_error) {
            this._scene = null;
        }
        if (!this._foreground) {
            try {
                this._foreground = Cairo.ImageSurface.createFromPNG(
                    GLib.file_test(FOREGROUND_PATH, GLib.FileTest.EXISTS) ? FOREGROUND_PATH : LEGACY_FOREGROUND_PATH);
            } catch (_error) {
                this._foreground = null;
            }
        }
        for (const area of this._areas ?? []) {
            area.visible = this._settings.enabled;
            area.queue_repaint();
        }
        if (this._focus && !this._scene?.nodes.some(node => node.kind === this._focus.kind &&
            node.root === this._focus.root && node.path === this._focus.path)) this._focus = null;
    }

    _clamp(value, fallback) {
        const number = Number(value);
        return Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : fallback;
    }

    _buildAreas() {
        for (const area of this._areas) area.destroy();
        this._areas = [];
        const monitors = Main.layoutManager.monitors ?? [Main.layoutManager.primaryMonitor];
        for (const monitor of monitors) {
            if (!monitor) continue;
            const area = new St.DrawingArea({reactive: false, visible: this._settings.enabled});
            area.set_position(monitor.x, monitor.y);
            area.set_size(monitor.width, monitor.height);
            area.connect('repaint', actor => {
                const cr = actor.get_context();
                try {
                    renderGalaxy(cr, actor.width, actor.height, this._scene, this._settings, this._phase, this._motionTime, this._foreground, this._focus);
                } finally {
                    cr.$dispose();
                }
            });
            Main.layoutManager._backgroundGroup.add_child(area);
            this._areas.push(area);
            area.queue_repaint();
        }
    }

    _desktopPoint(x, y) {
        if (!this._settings.enabled || Main.overview.visible || Main.modalCount > 0 ||
            y < (Main.panel?.height ?? 0)) return false;
        for (const actor of global.get_window_actors()) {
            const window = actor.meta_window;
            if (!window || !actor.visible || window.get_window_type() === Meta.WindowType.DESKTOP) continue;
            const rect = window.get_frame_rect();
            if (x >= rect.x && x < rect.x + rect.width && y >= rect.y && y < rect.y + rect.height)
                return false;
        }
        return true;
    }

    _hitNode(x, y) {
        if (!this._scene?.nodes || !this._desktopPoint(x, y)) return null;
        for (const area of this._areas) {
            if (x < area.x || y < area.y || x >= area.x + area.width || y >= area.y + area.height) continue;
            const skyMode = this._settings.foreground !== false && this._foreground !== null;
            const {coordinates, visible} = layoutScene(this._scene, this._phase, area.width, area.height, skyMode, this._focus);
            return hitTest(this._scene, coordinates, visible, x - area.x, y - area.y);
        }
        return null;
    }

    _updateHover() {
        if (!this._tooltip) return;
        const [x, y, modifiers] = global.get_pointer();
        const node = this._hitNode(x, y);
        const ctrl = (modifiers & Clutter.ModifierType.CONTROL_MASK) !== 0;
        const alt = (modifiers & Clutter.ModifierType.MOD1_MASK) !== 0;
        const actionable = node && (node.kind !== 'Remembered file' || ctrl || alt);
        if (this._clickTarget) {
            if (actionable) {
                this._clickTarget.set_position(x - 12, y - 12);
                this._clickTarget.show();
            } else this._clickTarget.hide();
        }
        if (!actionable) {
            this._tooltip.hide();
            return;
        }
        const path = node.kind === 'Remembered file' ? GLib.path_get_dirname(node.path) : node.path;
        const displayedPath = path.length > 96 ? `…${path.slice(-95)}` : path;
        const memory = node.kind === 'Remembered file' && node.memory &&
            this._scene.memory_source?.provider === 'hindsight';
        this._tooltip.text = `${node.name}  →  ${displayedPath}\n` +
            (node.kind === 'Remembered file' ?
                `Ctrl+click: open folder${memory ? '   ·   Ctrl+Shift+click: newest memory' : ''}` :
                node.kind === 'Host' ? 'Click: open galaxy folder   ·   Alt+click: reset view' :
                'Click: open folder   ·   Alt+click: focus system');
        this._tooltip.set_position(Math.max(4, Math.min(x + 18, global.stage.width - 560)),
            Math.max(4, Math.min(y + 18, global.stage.height - 65)));
        this._tooltip.show();
    }

    _onCaptured(event) {
        if (event.type() !== Clutter.EventType.BUTTON_PRESS || event.get_button() !== 1)
            return Clutter.EVENT_PROPAGATE;
        const [x, y] = event.get_coords();
        const modifiers = event.get_state();
        const alt = (modifiers & Clutter.ModifierType.MOD1_MASK) !== 0;
        const ctrl = (modifiers & Clutter.ModifierType.CONTROL_MASK) !== 0;
        const shift = (modifiers & Clutter.ModifierType.SHIFT_MASK) !== 0;
        const node = this._hitNode(x, y);
        if (alt) {
            if (node?.kind === 'Host') {
                this._focus = null;
                for (const area of this._areas) area.queue_repaint();
                return Clutter.EVENT_STOP;
            }
            if (!node && this._focus && this._desktopPoint(x, y)) {
                this._focus = null;
            } else if (node) {
                const target = node.kind === 'Remembered file' ?
                    this._scene.nodes.find(item => item.kind === 'Remembered directory' && item.path === GLib.path_get_dirname(node.path)) ?? node : node;
                this._focus = this._focus?.path === target.path && this._focus?.root === target.root ?
                    null : {kind: target.kind, path: target.path, root: target.root, name: target.name};
            } else return Clutter.EVENT_PROPAGATE;
            for (const area of this._areas) area.queue_repaint();
            this._updateHover();
            return Clutter.EVENT_STOP;
        }
        if (!node) return Clutter.EVENT_PROPAGATE;
        if (node.kind === 'Remembered file') {
            if (!ctrl) return Clutter.EVENT_PROPAGATE;
            if (shift && node.memory && this._scene.memory_source?.provider === 'hindsight')
                this._openMemory(node);
            else this._openFolder(GLib.path_get_dirname(node.path));
        } else this._openFolder(node.path);
        return Clutter.EVENT_STOP;
    }

    _openFolder(path) {
        const file = Gio.File.new_for_path(path);
        if (file.query_file_type(Gio.FileQueryInfoFlags.NONE, null) !== Gio.FileType.DIRECTORY) {
            Main.notify('Constellation', 'That folder is no longer available.');
            return;
        }
        Gio.AppInfo.launch_default_for_uri_async(file.get_uri(), null, null, (_source, result) => {
            try { Gio.AppInfo.launch_default_for_uri_finish(result); }
            catch (error) { Main.notify('Constellation', `Could not open folder: ${error.message}`); }
        });
    }

    _openMemory(node) {
        const source = this._scene.memory_source;
        if (!source?.cli || !source.agent || !node.memory_project) return;
        try {
            Gio.Subprocess.new(['/usr/bin/python3', GLib.build_filenamev([this.path, 'memory_viewer.py']),
                source.cli, source.agent, node.memory_project, node.memory], Gio.SubprocessFlags.NONE);
        } catch (error) {
            Main.notify('Constellation', `Could not open memory: ${error.message}`);
        }
    }
}
