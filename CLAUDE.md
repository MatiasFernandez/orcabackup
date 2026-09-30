# CLAUDE.md

## What this is

Tools for keeping an OrcaSlicer setup reproducible across app updates. There is no build, no test suite, no linter, and no package manifest. [README.md](README.md) is the user-facing documentation.

- [backup.py](backup.py): Python 3.8+, **standard library only** for now. Supports macOS and Linux.
- [freeze-version.sh](freeze-version.sh): bash, macOS only. Uses `ditto`, `PlistBuddy`, `codesign`, `lsregister`.

## Running / verifying changes

With no tests, verify by running the scripts. Both act on the real OrcaSlicer install by default, so be careful:

```sh
./backup.py --out /tmp/ob --no-app-profiles        # quick small snapshot, away from ./backups/
./backup.py --out /tmp/ob --diff-latest            # should report "No differences." right after a backup
./backup.py --data-dir <fixture> --app-dir <fixture> --app-version 0.0.0 --out /tmp/ob   # run against a fake tree
python3 -m py_compile backup.py
bash -n freeze-version.sh
```

`freeze-version.sh` writes into `/Applications`, `~/.local/apps` and `~/Library/Application Support`, and `--force` deletes existing targets with `rm -rf`. Don't run it to "test" a change without asking the user.

## Docs

When adding or changing CLI options or paths, update the matching tables in README.md (Options, "Where it looks for your data", freeze targets) and the usage docstring at the top of `backup.py`.
