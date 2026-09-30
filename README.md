# 🐋 orcabackup

Tools to keep your OrcaSlicer setup reproducible across updates. Backups work on macOS and Linux; the version freeze is macOS only.

## What's in this repo

| Tool | Use it to |
|---|---|
| [`backup.py`](backup.py) | Snapshot your presets and the base profiles they inherit from, and diff your current setup against a snapshot |
| [`freeze-version.sh`](freeze-version.sh) | Keep the currently installed OrcaSlicer runnable side by side after you upgrade (macOS) |
| [`pin-printer.py`](pin-printer.py) | Re-link printers you saved with "Detach from parent" to their system printer, so they keep every setting and still match system filaments and processes |

## Upgrade workflow

The recommended order when moving to a new OrcaSlicer version. Quit OrcaSlicer before running any of the scripts.

| # | Where | Step | |
|---|---|---|---|
| 1 | Terminal | `./freeze-version.sh` — keep the current app runnable (macOS) | optional |
| 2 | OrcaSlicer (old) | Save detached copies of the presets you want to keep | optional |
| 3 | OrcaSlicer (old) | *Export Preset Bundle* for a GUI-importable backup, then quit | optional |
| 4 | Terminal | `./pin-printer.py` — re-link detached printers to their parent | |
| 5 | Terminal | `./backup.py` — snapshot your setup | |
| 6 | — | Install the new version and open it once | |
| 7 | Terminal + OrcaSlicer (new) | `./backup.py --diff-latest`, then *Compare presets* | |

1. **Keep the old version** (macOS, optional). [`freeze-version.sh`](#freeze-versionsh-macos) copies the app and its data dir, so the old version stays runnable with your setup as it is now.
2. **Freeze the presets you want to keep** (optional). A user preset only stores what differs from its system parent, so after the update it picks up the new parent's values. To keep a copy with today's values, open the preset in the current version with Developer mode on, click Save, tick **Detach from parent** and save it under a new name (e.g. `… (frozen 2.3.2)`). OrcaSlicer writes every setting into the file, including built-in defaults. The checkbox is in the Save dialog from 2.3.2 on, in Developer mode only. Do this in the regular app, not in the frozen copy, so the new version sees the frozen presets.
3. **Export a bundle you can import from the GUI** (optional). In the same session, *File → Export → Export Preset Bundle → Printer config bundle (.orca_printer)* saves a user printer together with every user filament and process compatible with it, frozen copies included. Restore it with *File → Import → Import Configs*. Presets that still inherit from a system preset only hold your changes, so after an update they resolve against the new parents; the frozen copies keep the old values. Export before pinning: importing re-saves a preset that has a parent as a diff against it, which would undo the pin, while a detached printer is imported whole. After importing the bundle, run `./pin-printer.py` again. Quit OrcaSlicer when done.
4. **Pin frozen printers.** Detached filaments and processes are done after step 2. Detached printers need their parent back, or most system filaments and processes stop showing up for them. Run [`pin-printer.py`](#pin-printerpy); it does nothing if there's no detached printer.
5. **Snapshot** with [`backup.py`](#backuppy). It holds your originals, the frozen copies, the pinned printers and the base profiles of the installed version, so it's the most complete record of the old setup. One run, as the last step before upgrading, is enough.
6. **Install the new version** and let it reuse the data dir. Your user preset files are left as they are; the system profiles are replaced. On first launch OrcaSlicer also copies `user/` to `user_backup-v<new version>` in the data dir.
7. **Check what changed** with `./backup.py --diff-latest`, and compare a live preset with its frozen copy in OrcaSlicer's *Compare presets* dialog (the compare button in the settings panel).

## Requirements

- `backup.py`, `pin-printer.py`: Python 3.8+ with no third-party packages. Python 3 ships with macOS (via the Xcode command line tools) and most Linux distributions.
- `freeze-version.sh`: macOS with OrcaSlicer installed in `/Applications`.

## backup.py

Takes a dated snapshot of your OrcaSlicer setup, including the base profiles your presets depend on, so that after an update you can still see how everything was configured before.

### Why not just use "Export Preset Bundle"?

OrcaSlicer's *File → Export → Export Preset Bundle* only exports your **user** presets. A user preset stores `inherits: "<system preset>"` and only the values you changed on top of it. The system preset it points to is not exported, so after an update the same user preset can resolve to different values.

This script zips your user presets **and** the base profiles from the installed version, so the snapshot is self-contained.

### What goes in the zip

```
orcaslicer-userdata-backup_v2.3.2_2026-09-29_1005.zip
├── metadata.json        app version, timestamp, host, source paths
├── data/
│   ├── user/            your printer / filament / process presets
│   ├── system/          vendor profiles OrcaSlicer has installed in its data dir
│   ├── printers/
│   └── OrcaSlicer.conf  app settings
└── bundled-profiles/    profiles shipped inside the installed app
```

Left out on purpose: `cache/`, `log/`, `hms/`, `ota/`, the `user_backup-*` folders, and `.orcaslicer_machine_id` (it identifies your machine).

The zip is about 25 MB, almost all of it the app's bundled profiles. `--no-app-profiles` brings it down to a few MB.

### Options

Run `./backup.py` with no arguments to write to `backups/` next to the script.

| Option | Purpose |
|---|---|
| `--out DIR` | Output folder (default: `backups/` next to the script) |
| `--pick` | Choose the output folder in a native dialog (`osascript` on macOS; `zenity` or `kdialog` on Linux, falling back to the default folder) |
| `--data-dir DIR` | OrcaSlicer data dir, if auto-detection fails |
| `--app-dir DIR` | Installed app or install dir, if auto-detection fails |
| `--app-version X.Y.Z` | Override the detected version in the file name |
| `--no-app-profiles` | Skip the app's bundled profiles (much smaller zip) |
| `--list` | List existing backups and exit |
| `--diff-latest` | Show added, removed and changed files against the newest backup |

OrcaSlicer rewrites `OrcaSlicer.conf` and presets on exit, so a backup taken while it is open may be inconsistent. The script warns if it detects the app running and carries on.

### Comparing before and after an update

Back up before updating, update OrcaSlicer and open it once, then run `./backup.py --diff-latest`. You can also unzip the backup and diff it against the live folders.

### Where it looks for your data

| OS | Data dir | App profiles |
|---|---|---|
| macOS | `~/Library/Application Support/OrcaSlicer` | `/Applications/OrcaSlicer.app` |
| Linux | `$XDG_CONFIG_HOME/OrcaSlicer` (default `~/.config/OrcaSlicer`) | `/usr/share/OrcaSlicer`, `/opt/OrcaSlicer`, `/opt/orca-slicer`, `~/OrcaSlicer` |
| Linux (Flatpak) | `~/.var/app/io.github.softfever.OrcaSlicer/config/OrcaSlicer` | not auto-detected; use `--app-dir` or `--no-app-profiles` |

## freeze-version.sh (macOS)

Before installing a new OrcaSlicer, freeze the installed one as a separate app with its own data dir. The new version then installs as a normal `OrcaSlicer.app` without replacing the old binary or sharing its settings.

```sh
./freeze-version.sh                  # version read from the installed app
./freeze-version.sh --version 2.3.2  # override the detected version
./freeze-version.sh --force          # replace targets that already exist
./freeze-version.sh --remove 2.3.2   # delete a frozen version
```

For version `X.Y.Z` it creates:

| Path | What it is |
|---|---|
| `~/.local/apps/OrcaSlicer-X.Y.Z.app` | Copy of `/Applications/OrcaSlicer.app`. It sits in a hidden folder so Launchpad and Spotlight don't list it twice. |
| `~/Library/Application Support/OrcaSlicer-X.Y.Z` | Copy of the data dir. |
| `/Applications/OrcaSlicer X.Y.Z.app` | Minimal wrapper app with the original icon. Its launcher runs the copy with `--datadir` pointing at the copied data dir. |

Launch the frozen version through the wrapper. Opening the copy in `~/.local/apps` directly ignores `--datadir` and uses the default data dir.

The original app and data dir are never modified. The script refuses to run while OrcaSlicer is open, so the data dir copy is consistent. It also refuses to overwrite existing targets unless you pass `--force`.

`--remove X.Y.Z` unregisters the wrapper from Launch Services and deletes all three paths, skipping any that are already gone. It lists the paths and their sizes and asks for confirmation before deleting anything. It refuses to run while that version is open. The frozen data dir is deleted too, including any presets you changed while using that version, so back it up first if you want to keep them (`./backup.py --data-dir "$HOME/Library/Application Support/OrcaSlicer-X.Y.Z"`).

Don't run two OrcaSlicer versions at the same time. The wrapper is ad-hoc signed and its launcher is a shell script, so macOS may show a one-time warning about the app not being optimized for your Mac.

## pin-printer.py

System filaments and processes list the printers they work with by name, and a user printer matches through its parent. A printer saved with *Detach from parent* (step 2 of the [upgrade workflow](#upgrade-workflow)) has no parent, so most of them disappear for it. `pin-printer.py` puts the parent back while keeping every detached value:

```sh
./pin-printer.py            # find detached printers, show the matches, ask once
./pin-printer.py --dry-run  # only show what would change
./pin-printer.py --yes      # don't ask
```

| Option | Purpose |
|---|---|
| `--data-dir DIR` | OrcaSlicer data dir, if auto-detection fails |
| `--dry-run` | Show the matches without changing anything |
| `--yes` | Pin without asking |

It looks for printers with an empty `inherits` in `user/*/machine/base/`, where OrcaSlicer saves presets without a parent, and in `user/*/machine/`. For each one it picks the installed system printer with the same `printer_model` and `printer_variant` (e.g. `Elegoo Centauri Carbon` + `0.4` → `Elegoo Centauri Carbon 0.4 nozzle`). Printers without exactly one match, such as ones built from scratch, are listed and skipped. Only the `inherits` line changes. The file and its `.info` then move from `machine/base/` to `machine/`, where OrcaSlicer keeps presets that have a parent; a printer is skipped if that name is already taken there. The original stays in `base/` as `<name>.json.bak`, which OrcaSlicer ignores. Pinned printers aren't detached any more, so running it again does nothing. It refuses to run while OrcaSlicer is open.

Detached filaments and processes need no pinning. With no parent, OrcaSlicer saves every setting each time, so you can keep editing them in the new version. A pinned printer keeps its values only until you save it in OrcaSlicer: saving diffs it against the current parent and drops the keys that happen to match, and those keys then follow future parent updates. Treat pinned printers as read-only. Importing one from a preset bundle has the same effect, so export printers before pinning them and run the script again after importing. The pin also needs the parent to exist in the new version; OrcaSlicer skips a user preset whose parent is gone (renames declared by the vendor profile are followed).

## Limitations

- Developed and tested on macOS. The Linux paths and the `zenity`/`kdialog` picker are untested.
- The app version is read automatically on macOS only. On Linux pass `--app-version`, otherwise the file name contains `vunknown`.
- Windows is not supported.
- `backup.py` makes a snapshot for reference and comparison. There is no restore command; unzip the archive and copy files back by hand if you need them.

## Contributing

Issues and pull requests are welcome. Linux and Windows are the main gaps: reports of what works or doesn't on those systems, or patches for them, are especially useful. Keep `backup.py` dependency-free (standard library only).

## License

[MIT](LICENSE)
