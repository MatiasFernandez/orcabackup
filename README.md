# 🐋 orcabackup

Take a dated snapshot of your OrcaSlicer setup, including the base profiles your presets depend on, so that after an update you can still see how everything was configured before.

## Why not just use "Export Preset Bundle"?

OrcaSlicer's *File → Export → Export Preset Bundle* only exports your **user** presets. A user preset stores `inherits: "<system preset>"` and only the values you changed on top of it. The system preset it points to is not exported, so after an update the same user preset can resolve to different values.

This script zips your user presets **and** the base profiles from the installed version, so the snapshot is self-contained.

## What goes in the zip

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

## Requirements

Python 3.8+ with no third-party packages. Python 3 ships with macOS (via the Xcode command line tools) and most Linux distributions.

## Usage

```sh
./backup.py                # write to ./backups/ next to the script
./backup.py --pick         # choose the output folder in a native dialog
./backup.py --out DIR      # write to a specific folder
./backup.py --list         # list existing backups
./backup.py --diff-latest  # compare your current setup with the newest backup
```

Close OrcaSlicer before running. It rewrites `OrcaSlicer.conf` and presets on exit, so a backup taken while it is open may be inconsistent. The script warns if it detects the app running and carries on.

### Options

| Option | Purpose |
|---|---|
| `--out DIR` | Output folder (default: `backups/` next to the script) |
| `--pick` | Choose the output folder in a native dialog |
| `--data-dir DIR` | OrcaSlicer data dir, if auto-detection fails |
| `--app-dir DIR` | Installed app or install dir, if auto-detection fails |
| `--app-version X.Y.Z` | Override the detected version in the file name |
| `--no-app-profiles` | Skip the app's bundled profiles (much smaller zip) |
| `--list` | List existing backups and exit |
| `--diff-latest` | Show added, removed and changed files against the newest backup |

The zip is about 25 MB, almost all of it the app's bundled profiles. `--no-app-profiles` brings it down to a few MB.

### Folder picker

`--pick` uses `osascript` on macOS, which is always available. On Linux it uses `zenity` or `kdialog` if one is installed; otherwise it falls back to the default folder.

## Comparing before and after an update

1. Back up before updating.
2. Update OrcaSlicer and open it once.
3. Run `./backup.py --diff-latest` to see which files changed, or unzip the backup and diff it against the live folders.

## Keeping the old version runnable: `freeze-version.sh` (macOS)

Before installing a new OrcaSlicer, you can freeze the installed one as a separate app with its own data dir. The new version then installs as a normal `OrcaSlicer.app` without replacing the old binary or sharing its settings.

```sh
./freeze-version.sh                  # version read from the installed app
./freeze-version.sh --version 2.3.2  # override the detected version
./freeze-version.sh --force          # replace targets that already exist
```

For version `X.Y.Z` it creates:

| Path | What it is |
|---|---|
| `~/.local/apps/OrcaSlicer-X.Y.Z.app` | Copy of `/Applications/OrcaSlicer.app`. It sits in a hidden folder so Launchpad and Spotlight don't list it twice. |
| `~/Library/Application Support/OrcaSlicer-X.Y.Z` | Copy of the data dir. |
| `/Applications/OrcaSlicer X.Y.Z.app` | Minimal wrapper app with the original icon. Its launcher runs the copy with `--datadir` pointing at the copied data dir. |

Launch the frozen version through the wrapper. Opening the copy in `~/.local/apps` directly ignores `--datadir` and uses the default data dir.

The original app and data dir are never modified. The script refuses to run while OrcaSlicer is open, so the data dir copy is consistent. It also refuses to overwrite existing targets unless you pass `--force`.

Don't run two OrcaSlicer versions at the same time. The wrapper is ad-hoc signed and its launcher is a shell script, so macOS may show a one-time warning about the app not being optimized for your Mac.

## Where it looks for your data

| OS | Data dir | App profiles |
|---|---|---|
| macOS | `~/Library/Application Support/OrcaSlicer` | `/Applications/OrcaSlicer.app` |
| Linux | `$XDG_CONFIG_HOME/OrcaSlicer` (default `~/.config/OrcaSlicer`) | `/usr/share/OrcaSlicer`, `/opt/OrcaSlicer`, `/opt/orca-slicer`, `~/OrcaSlicer` |
| Linux (Flatpak) | `~/.var/app/io.github.softfever.OrcaSlicer/config/OrcaSlicer` | not auto-detected; use `--app-dir` or `--no-app-profiles` |

## Limitations

- Developed and tested on macOS. The Linux paths and the `zenity`/`kdialog` picker are untested.
- The app version is read automatically on macOS only. On Linux pass `--app-version`, otherwise the file name contains `vunknown`.
- Windows is not supported.
- This is a snapshot for reference and comparison. There is no restore command; unzip the archive and copy files back by hand if you need them.
