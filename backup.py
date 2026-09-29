#!/usr/bin/env python3
"""Snapshot OrcaSlicer's user presets and base (system) profiles into a zip.

Usage:
  ./backup.py                 # write to <script dir>/backups/
  ./backup.py --pick          # choose the output folder in a native dialog
  ./backup.py --out DIR       # explicit output folder
  ./backup.py --list          # list existing backups
  ./backup.py --diff-latest   # diff the live setup against the newest backup

Zip layout:
  metadata.json         app version, date, host, source paths
  data/                 user/, system/, printers/, OrcaSlicer.conf from the data dir
  bundled-profiles/     the profiles shipped inside the installed app (if found)
"""
import argparse
import getpass
import hashlib
import json
import os
import platform
import plistlib
import shutil
import socket
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = SCRIPT_DIR / "backups"
PREFIX = "orcaslicer-userdata-backup"

# Entries of the data dir that make up the snapshot. Everything else (cache, log,
# hms, ota, user_backup-*, .orcaslicer_machine_id) is deliberately left out.
DATA_INCLUDE = ["user", "system", "printers", "OrcaSlicer.conf"]
IGNORED_NAMES = {".DS_Store"}


def data_dir_candidates():
    home = Path.home()
    if sys.platform == "darwin":
        return [home / "Library/Application Support/OrcaSlicer"]
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return [
        xdg / "OrcaSlicer",
        home / ".var/app/io.github.softfever.OrcaSlicer/config/OrcaSlicer",  # Flatpak
    ]


def app_dir_candidates():
    if sys.platform == "darwin":
        return [
            Path("/Applications/OrcaSlicer.app"),
            Path.home() / "Applications/OrcaSlicer.app",
        ]
    return [
        Path("/usr/share/OrcaSlicer"),
        Path("/opt/OrcaSlicer"),
        Path("/opt/orca-slicer"),
        Path.home() / "OrcaSlicer",
    ]


def find_data_dir(override):
    if override:
        p = Path(override).expanduser()
        return p if p.is_dir() else None
    return next((p for p in data_dir_candidates() if p.is_dir()), None)


def find_bundled_profiles(override_app):
    candidates = [Path(override_app).expanduser()] if override_app else app_dir_candidates()
    for app in candidates:
        for sub in ("Contents/Resources/profiles", "resources/profiles", "profiles"):
            p = app / sub
            if p.is_dir():
                return app, p
    return None, None


def detect_app_version(app):
    if app and sys.platform == "darwin":
        try:
            with open(app / "Contents/Info.plist", "rb") as f:
                return plistlib.load(f).get("CFBundleShortVersionString")
        except (OSError, plistlib.InvalidFileException):
            pass
    return None


def warn(msg):
    """Print a yellow warning with an icon to stderr (plain text if not a TTY or NO_COLOR is set)."""
    if sys.stderr.isatty() and "NO_COLOR" not in os.environ:
        print(f"\033[1;33m⚠️  {msg}\033[0m", file=sys.stderr)
    else:
        print(f"⚠️  {msg}", file=sys.stderr)


def orca_running():
    try:
        out = subprocess.run(["pgrep", "-fi", r"OrcaSlicer\.app/Contents/MacOS|orca-slicer|OrcaSlicer$"],
                             capture_output=True, text=True)
        return bool(out.stdout.strip())
    except FileNotFoundError:
        return False


def pick_folder(initial):
    """Native folder dialog. Returns a Path, or None if unavailable/cancelled."""
    try:
        if sys.platform == "darwin":
            script = (f'POSIX path of (choose folder with prompt "Where to save the OrcaSlicer backup?" '
                      f'default location POSIX file "{initial}")')
            out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        elif shutil.which("zenity"):
            out = subprocess.run(["zenity", "--file-selection", "--directory",
                                  "--title=Where to save the OrcaSlicer backup?",
                                  f"--filename={initial}/"], capture_output=True, text=True)
        elif shutil.which("kdialog"):
            out = subprocess.run(["kdialog", "--getexistingdirectory", str(initial)],
                                 capture_output=True, text=True)
        else:
            print("No native folder dialog available (need zenity or kdialog); using default.", file=sys.stderr)
            return None
    except FileNotFoundError:
        return None
    chosen = out.stdout.strip()
    if out.returncode != 0 or not chosen:
        return None
    return Path(chosen)


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_NAMES)
        for name in sorted(filenames):
            if name not in IGNORED_NAMES:
                yield Path(dirpath) / name


def collect_live(data_dir, bundled):
    """Map of archive path -> source file for everything that goes into the snapshot."""
    files = {}
    for entry in DATA_INCLUDE:
        src = data_dir / entry
        if src.is_file():
            files[f"data/{entry}"] = src
        elif src.is_dir():
            for f in iter_files(src):
                files[f"data/{f.relative_to(data_dir).as_posix()}"] = f
    if bundled:
        for f in iter_files(bundled):
            files[f"bundled-profiles/{f.relative_to(bundled).as_posix()}"] = f
    return files


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    return sha(Path(path).read_bytes())


def unique_zip_path(out_dir, stem):
    path = out_dir / f"{stem}.zip"
    n = 2
    while path.exists():
        path = out_dir / f"{stem}_{n}.zip"
        n += 1
    return path


def list_backups(out_dir):
    return sorted(out_dir.glob(f"{PREFIX}_*.zip")) if out_dir.is_dir() else []


def cmd_backup(args, out_dir):
    data_dir = find_data_dir(args.data_dir)
    if not data_dir:
        sys.exit("OrcaSlicer data dir not found. Tried: "
                 + ", ".join(str(p) for p in data_dir_candidates()) + ". Use --data-dir.")

    app, bundled = (None, None) if args.no_app_profiles else find_bundled_profiles(args.app_dir)
    if bundled is None and not args.no_app_profiles:
        warn("Installed app's bundled profiles not found; use --app-dir to point at it "
             "(or --no-app-profiles to silence this).")

    version = args.app_version or detect_app_version(app) or "unknown"
    if version == "unknown":
        warn("Could not detect the OrcaSlicer version; pass --app-version X.Y.Z.")

    if orca_running():
        warn("OrcaSlicer is running. Close it for a fully consistent snapshot "
             "(it rewrites OrcaSlicer.conf and presets on exit). Continuing anyway.")

    files = collect_live(data_dir, bundled)
    now = datetime.now()
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = unique_zip_path(out_dir, f"{PREFIX}_v{version}_{now:%Y-%m-%d_%H%M}")

    metadata = {
        "created": now.astimezone().isoformat(timespec="seconds"),
        "orcaslicer_version": version,
        "host": socket.gethostname(),
        "user": getpass.getuser(),
        "platform": platform.platform(),
        "data_dir": str(data_dir),
        "app_dir": str(app) if app else None,
        "bundled_profiles_dir": str(bundled) if bundled else None,
        "file_count": len(files),
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("metadata.json", json.dumps(metadata, indent=2) + "\n")
        for arc, src in files.items():
            z.write(src, arc)

    print(f"OrcaSlicer {version}: {len(files)} files -> {zip_path} ({zip_path.stat().st_size / 1024:.0f} KiB)")


def cmd_list(out_dir):
    backups = list_backups(out_dir)
    if not backups:
        print(f"No backups in {out_dir}")
        return
    for b in backups:
        print(f"{b.name}  {b.stat().st_size / 1024:.0f} KiB")


def cmd_diff_latest(args, out_dir):
    backups = list_backups(out_dir)
    if not backups:
        sys.exit(f"No backups in {out_dir}")
    latest = backups[-1]
    data_dir = find_data_dir(args.data_dir)
    if not data_dir:
        sys.exit("OrcaSlicer data dir not found; use --data-dir.")
    _, bundled = (None, None) if args.no_app_profiles else find_bundled_profiles(args.app_dir)
    live = collect_live(data_dir, bundled)

    with zipfile.ZipFile(latest) as z:
        old = {n: sha(z.read(n)) for n in z.namelist() if n != "metadata.json" and not n.endswith("/")}
    new = {arc: sha_file(src) for arc, src in live.items()}

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(n for n in set(old) & set(new) if old[n] != new[n])
    print(f"Comparing live setup against {latest.name}")
    for label, names in (("Added", added), ("Removed", removed), ("Changed", changed)):
        print(f"\n{label} ({len(names)})")
        for n in names:
            print(f"  {n}")
    if not (added or removed or changed):
        print("\nNo differences.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="output folder (default: <script dir>/backups)")
    ap.add_argument("--pick", action="store_true", help="choose the output folder in a native dialog")
    ap.add_argument("--data-dir", help="OrcaSlicer data dir (auto-detected by default)")
    ap.add_argument("--app-dir", help="installed OrcaSlicer app/install dir (auto-detected by default)")
    ap.add_argument("--app-version", help="override the detected OrcaSlicer version in the file name")
    ap.add_argument("--no-app-profiles", action="store_true", help="skip the app's bundled profiles")
    ap.add_argument("--list", action="store_true", help="list existing backups and exit")
    ap.add_argument("--diff-latest", action="store_true", help="diff the live setup against the newest backup")
    args = ap.parse_args()

    out_dir = Path(args.out).expanduser() if args.out else None
    if out_dir is None and args.pick:
        DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
        out_dir = pick_folder(DEFAULT_OUT)
        if out_dir is None:
            print(f"No folder chosen; using {DEFAULT_OUT}", file=sys.stderr)
    out_dir = out_dir or DEFAULT_OUT

    if args.list:
        cmd_list(out_dir)
    elif args.diff_latest:
        cmd_diff_latest(args, out_dir)
    else:
        cmd_backup(args, out_dir)


if __name__ == "__main__":
    main()
