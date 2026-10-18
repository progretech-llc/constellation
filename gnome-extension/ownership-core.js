// Shared by Avalon and Constellation. Shell executes claims synchronously.
export class WallpaperOwnership {
    constructor() {
        this.owner = null;
    }

    claim(uuid, stop) {
        const previous = this.owner;
        if (previous) {
            // Keep the old lease on failure: starting a second renderer is unsafe.
            previous.stop();
            if (this.owner === previous)
                this.owner = null;
        }
        const lease = {uuid, stop};
        this.owner = lease;
        return () => {
            if (this.owner === lease)
                this.owner = null;
        };
    }
}
