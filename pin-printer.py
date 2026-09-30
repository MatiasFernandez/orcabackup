#!/usr/bin/env python3
"""Re-link detached OrcaSlicer printer presets to their system parent ("pinning").

A printer saved with "Detach from parent" holds every setting but has no parent, so
system filaments and processes that list compatible printers by name stop showing up
for it. Pinning restores "inherits" while keeping all the detached values, so the
preset keeps its settings and its compatibility.

Usage:
  ./pin-printer.py            # find detached printers, show the matches, ask once
  ./pin-printer.py --dry-run  # only show what would change
  ./pin-printer.py --yes      # don't ask

The parent is the installed system printer with the same printer_model and
printer_variant. Detached printers without exactly one match are skipped. OrcaSlicer
keeps presets without a parent in machine/base/, so a pinned printer is moved (with its
.info) to machine/, where it keeps presets that have one. The original is kept as
<name>.json.bak where it was (OrcaSlicer only loads *.json).
"""
import argparse
import json
import re
import sys
from pathlib import Path

from backup import find_data_dir, orca_running, warn

INHERITS_EMPTY = re.compile(r'^(\s*"inherits"\s*:\s*)""', re.MULTILINE)


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def system_printers(data_dir):
    """Map (printer_model, printer_variant) -> list of selectable system printer names."""
    index = {}
    for path in sorted((data_dir / "system").glob("*/machine/**/*.json")):
        d = load_json(path)
        if not d or d.get("instantiation") != "true":
            continue
        model, variant = d.get("printer_model"), d.get("printer_variant")
        if model and variant and d.get("name"):
            index.setdefault((model, variant), []).append(d["name"])
    return index


def detached_printers(data_dir):
    """Yield (path, config) for user printers saved without a parent.

    OrcaSlicer saves those in machine/base/; machine/ itself is checked too."""
    user = data_dir / "user"
    for path in sorted([*user.glob("*/machine/*.json"), *user.glob("*/machine/base/*.json")]):
        d = load_json(path)
        if d is not None and d.get("inherits") == "":
            yield path, d


def pinned_path(path):
    """Where OrcaSlicer keeps a printer that has a parent: machine/, not machine/base/."""
    return path.parent.parent / path.name if path.parent.name == "base" else path


def pin(path, parent):
    text = path.read_text(encoding="utf-8")
    new_text, n = INHERITS_EMPTY.subn(lambda m: m.group(1) + json.dumps(parent, ensure_ascii=False), text, count=1)
    if n != 1 or json.loads(new_text).get("inherits") != parent:
        raise RuntimeError(f"could not rewrite \"inherits\" in {path}")
    bak = path.with_name(path.name + ".bak")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    dest = pinned_path(path)
    dest.write_text(new_text, encoding="utf-8")
    if dest != path:
        info = path.with_suffix(".info")
        if info.exists():
            info.rename(dest.with_suffix(".info"))
        path.unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", help="OrcaSlicer data dir (auto-detected by default)")
    ap.add_argument("--dry-run", action="store_true", help="show what would change and exit")
    ap.add_argument("--yes", action="store_true", help="pin without asking")
    args = ap.parse_args()

    data_dir = find_data_dir(args.data_dir)
    if data_dir is None:
        sys.exit("OrcaSlicer data dir not found; pass --data-dir.")
    if orca_running() and not args.dry_run:
        sys.exit("OrcaSlicer is running; quit it first, it rewrites presets on exit.")

    parents = system_printers(data_dir)
    todo, skipped = [], []
    for path, d in detached_printers(data_dir):
        key = (d.get("printer_model"), d.get("printer_variant"))
        matches = parents.get(key, [])
        dest = pinned_path(path)
        if dest != path and (dest.exists() or dest.with_suffix(".info").exists()):
            skipped.append((d.get("name", path.stem), f"{dest} already exists"))
        elif len(matches) == 1:
            todo.append((path, d.get("name", path.stem), matches[0]))
        else:
            reason = "no system printer" if not matches else f"{len(matches)} system printers"
            skipped.append((d.get("name", path.stem), f"{reason} with printer_model={key[0]!r}, printer_variant={key[1]!r}"))

    for name, reason in skipped:
        warn(f"Skipping {name}: {reason}")
    if not todo:
        print("No detached printers to pin.")
        return

    print(f"Found {len(todo)} detached printer{'s' if len(todo) != 1 else ''}:")
    for _, name, parent in todo:
        print(f"  {name}\n    -> {parent}")
    if args.dry_run:
        return
    if not args.yes:
        try:
            answer = input("Pin? [Y/n] ").strip().lower()
        except EOFError:
            answer = "n"
        if answer not in ("", "y", "yes"):
            print("Nothing changed.")
            return

    for path, name, parent in todo:
        pin(path, parent)
        print(f"Pinned {name}")


if __name__ == "__main__":
    main()
