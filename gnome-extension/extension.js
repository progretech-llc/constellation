import Cairo from 'cairo';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {DEFAULT_SETTINGS, renderGalaxy} from './galaxy.js';

const SCENE_PATH = GLib.build_filenamev([GLib.get_user_state_dir(), 'factory-observatory', 'scene.json']);
const CONFIG_PATH = GLib.build_filenamev([GLib.get_user_config_dir(), 'factory-observatory', 'wallpaper.json']);
const FOREGROUND_PATH = GLib.build_filenamev([GLib.get_user_data_dir(), 'constellation', 'progre-foreground.png']);

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
        this._lastTick = GLib.get_monotonic_time();
        this._reload();
        this._buildAreas();
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
                this._phase = (this._phase + elapsed * this._settings.rotation_speed * Math.PI / 180) % (2 * Math.PI);
                this._motionTime += elapsed;
                for (const area of this._areas) area.queue_repaint();
            }
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
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
                this._foreground = Cairo.ImageSurface.createFromPNG(FOREGROUND_PATH);
            } catch (_error) {
                this._foreground = null;
            }
        }
        for (const area of this._areas ?? []) {
            area.visible = this._settings.enabled;
            area.queue_repaint();
        }
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
                    renderGalaxy(cr, actor.width, actor.height, this._scene, this._settings, this._phase, this._motionTime, this._foreground);
                } finally {
                    cr.$dispose();
                }
            });
            Main.layoutManager._backgroundGroup.add_child(area);
            this._areas.push(area);
            area.queue_repaint();
        }
    }
}
