# Constellation by ProgreTech

Constellation turns reviewed agent-memory activity into a rotating, luminous map on an Ubuntu GNOME wallpaper. Configured directory roots become solar systems; files mentioned in memory become stars; agents connect to the files they remember touching. Progre watches the sky from the bundled rooftop foreground. The lower-right **Constellation by ProgreTech · © 2026 ProgreTech LLC** attribution is rendered by the official wallpaper in both live and empty-data states.

![Constellation running on the ProgreTech workstation](assets/constellation-preview.png)

*Live workstation preview supplied by Edwin. Progre and this preview are ProgreTech visual assets; see the [asset terms](assets/PROGRE-ASSET-LICENSE.md).*

The preview captures an earlier roster. Current factory configuration groups retired role IDs under Rend and labels the separate Rend directory system **MS-S1 Max**.

The map is an interpretation of remembered activity, not a file monitor or an access-control tool. Only existing files inside configured roots can become file stars. The renderer never scans an entire disk to invent activity. Paths that look like credentials or private configuration are filtered. For MemPalace, Constellation calls the supplied CLI under **your own authorized identity** and reads shared structured activities; it does not open the database or another role's private memory. A JSON-directory adapter lets other memory systems export the same small activity shape.

### How updates appear

The user timer rebuilds the memory scene **every two minutes**. The GNOME extension checks for an updated scene **every two seconds** and redraws the rotating sky about eight times per second. A new activity record can add a file star on the next scene build when it names an existing file inside one of your configured roots. An agent touching a file already shown adds another agent-to-file link. The moving light travels back and forth along each visible link continuously; it is a recent-memory cue, not a one-time file-transfer event. The seven most recent visible file links per agent are drawn, then older links fall away as newer ones take priority.

The default display holds up to **160 remembered files** and **48 remembered directories**. When full, newer eligible files may replace older ones; the number on screen need not increase. Set `"max_files"` and `"max_directories"` in `sources.json` to change those limits (maximum 1,000 and 200). Missing files, paths outside configured roots, and sensitive-looking paths do not appear. If memory retrieval fails, the last scene remains in place; the wallpaper marks it stale after six minutes. The Bokeh inspection page reads configured memory when opened or refreshed (its local served page defaults to a 120-second refresh).

## Ubuntu GNOME install

Tested with Ubuntu GNOME Shell 50 on Wayland. Python 3.10+ and a user systemd session are required. This GNOME Shell extension has no macOS or Windows release.

```bash
git clone https://github.com/progretech-llc/constellation.git constellation
cd constellation
./install-ubuntu.sh
```

`install-ubuntu.sh` installs Ubuntu packages (`python3-venv`, `python3-gi`, GTK 4 bindings and `gjs`), creates a Python environment for Bokeh, installs the bundled Progre image, registers the control app and user refresh timer, and installs/enables the GNOME extension. It does not copy your memory or file contents. A first install in a running Wayland session may require logging out and back in before the extension appears. If the packages already exist, `./install-user.sh` performs only the user-level installation.

Open **Constellation by ProgreTech** from the app menu to control rotation, glow, rays, density, foreground, links and labels. The wallpaper keeps running without the control window. `gnome-extensions disable factory-observatory@progretech.com` turns it off; `systemctl --user disable --now factory-observatory-scene.timer` stops memory refreshes. The static GNOME wallpaper setting is untouched.

## Point it at your memory and solar systems

The installer creates `~/.config/constellation/sources.json`, initially with a local JSON memory directory and your home directory as one root. Use `configure.py` to replace those values; every `--root` replaces the whole root list. Paths must be absolute or start with `~` in the JSON file. Up to 12 roots are supported. A root appears as a solar system even when it has no remembered files.

For any agent memory that can export reviewed activity as JSON:

```bash
python3 configure.py \
  --memory-dir "$HOME/agent-memory/constellation-events" \
  --root "Projects=$HOME/Projects" \
  --root "Documents=$HOME/Documents" \
  --center-agent my-orchestrator \
  --agents my-orchestrator worker-a worker-b
```

Put one JSON object or an array of objects in each `*.json` file in that directory. A minimal object is:

```json
{
  "memory_id": "example-001",
  "author": "worker-a",
  "project": "MyProject",
  "technical_steps": ["Created /home/USER/Projects/demo/report.md"],
  "evidence": ["/home/USER/Projects/demo/report.md"]
}
```

Replace `USER` with your actual login; the file must already exist inside a configured root. `created`, `modified`, and `accessed` are inferred from step wording; all other references show as referenced. The exporter should supply reviewed summaries, not secrets or full conversations. JSON files stay local and are never uploaded by Constellation.

For MemPalace, point to its **CLI executable**, your identity and project; do not point Constellation at the database directory:

```bash
python3 configure.py \
  --mempalace-cli "$HOME/Rend/bin/mempalace" \
  --agent YOUR_OWN_ID --project YOUR_PROJECT \
  --root "Repositories=$HOME/Projects" \
  --root "Documents=$HOME/Documents" \
  --center-agent YOUR_OWN_ID
```

The CLI path above is an example only. Use the path on your workstation and the identity you are authorized to use. The reader accepts MemPalace's reviewed `structured-agent-activity` records in the selected project. Other authors' shared project records retain their attribution. Use `sources.json` to add `"include_subprojects": true` inside `memory` if intended. After editing sources or dropping new JSON summaries, refresh immediately with `systemctl --user start factory-observatory-scene.service`. The timer refreshes every two minutes. Check failures with `journalctl --user -u factory-observatory-scene.service -n 30`.

To keep a current roster while showing older memories, configure display-only author aliases. For example, `python3 configure.py --agents codex rend lyra mak progre imagen moxy --alias architect=rend --alias reviewer=rend --alias fast=rend --alias designer=rend --alias factory-worker=rend --unlisted-agent rend` groups those older authors, and any other unlisted authors, under Rend. Set `--center-agent codex` separately if desired. These choices change scene nodes and links only; the source memory records and their original authors remain unchanged. Omit `--unlisted-agent` if you want unlisted authors to receive their own nodes.

Choose roots at the level you want to see as solar systems. For instance, `--root "MS-S1 Max=$HOME/Rend" --root "Repositories=$HOME/Projects"` labels a work directory without confusing it with the Rend agent. If a drive contains several desired solar systems, configure those child directories as separate roots and leave out the broad parent root. Files named through a symlinked root still belong to that root as long as they resolve within it.

## Inspect and extend

The native app's **Open interactive map** button launches a Bokeh view bound to `127.0.0.1:8765`; hover to inspect remembered paths. Run `.venv/bin/python app.py --no-open` to save a local HTML snapshot. Run `gjs -m gnome-extension/render-preview.js ~/.local/state/factory-observatory/scene.json /tmp/constellation.png 1920 1080 assets/progre-foreground.png` to preview the exact Cairo composition. The GNOME background group is an internal Shell integration point and should be rechecked after Shell upgrades.

The code is MIT licensed. The bundled [Progre foreground, preview, and brand identifiers](assets/PROGRE-ASSET-LICENSE.md) have separate, rights-reserved terms; they are **not** MIT licensed. See [LICENSING.md](LICENSING.md) for the exact file scope. You can reuse the galaxy code for another project and supply your own foreground. The official release retains its lower-right ProgreTech credit. [GitHub's licensing guide](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) explains why repositories with separately licensed material need an explicit scope statement. This release does not include private factory memory, scene JSON, or credentials.
