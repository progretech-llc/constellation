import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {ExtensionState} from 'resource:///org/gnome/shell/misc/extensionUtils.js';
import {WallpaperOwnership} from './ownership-core.js';

const KEY = Symbol.for('com.progretech.wallpaper-owner.v1');
const PEERS = ['avalon@progretech.com', 'factory-observatory@progretech.com'];

function restoreLegacyBackground() {
    const settings = new Gio.Settings({schema_id: 'org.gnome.desktop.background'});
    for (const key of ['picture-uri', 'picture-uri-dark']) {
        let uri = settings.get_string(key);
        try { uri = decodeURIComponent(uri); } catch { continue; }
        if (uri.startsWith('file://') && uri.endsWith('/Constellation/data/progretech-constellation.png'))
            settings.set_string(key, settings.get_default_value(key).deep_unpack());
    }
}

function publish(uuid) {
    const directory = GLib.build_filenamev([GLib.get_user_runtime_dir(), 'progretech-wallpaper']);
    GLib.mkdir_with_parents(directory, 0o700);
    const file = Gio.File.new_for_path(GLib.build_filenamev([directory, 'owner.json']));
    file.replace_contents(JSON.stringify({schema: 1, uuid, shell_pid: new Gio.Credentials().get_unix_pid()}),
        null, false, Gio.FileCreateFlags.PRIVATE, null);
}

export function claimWallpaper(uuid, stop) {
    if (!PEERS.includes(uuid))
        throw new Error(`Unknown wallpaper: ${uuid}`);
    restoreLegacyBackground();
    const registry = globalThis[KEY] ??= new WallpaperOwnership();
    const release = registry.claim(uuid, stop);
    try {
        for (const peer of PEERS.filter(id => id !== uuid)) {
            // Also stop an older installed peer that predates this protocol.
            const extension = Main.extensionManager.lookup(peer);
            if (extension?.stateObj && [ExtensionState.ACTIVE, ExtensionState.ACTIVATING].includes(extension.state))
                extension.stateObj.disable();
            Main.extensionManager.disableExtension(peer);
        }
        publish(uuid);
    } catch (error) {
        release();
        throw error;
    }
    return () => {
        release();
        restoreLegacyBackground();
        publish(registry.owner?.uuid ?? null);
    };
}
