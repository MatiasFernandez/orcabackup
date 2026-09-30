#!/bin/bash
# Freeze the installed OrcaSlicer as a side-by-side "pinned" version (macOS).
#
#   ./freeze-version.sh [--version X.Y.Z] [--force]
#   ./freeze-version.sh --remove X.Y.Z
#
# 1. Copies /Applications/OrcaSlicer.app to ~/.local/apps/OrcaSlicer-<version>.app
# 2. Copies the data dir to "~/Library/Application Support/OrcaSlicer-<version>"
# 3. Builds /Applications/"OrcaSlicer <version>".app, a minimal bundle whose launcher
#    starts the copied app with --datadir pointing at the copied data dir.
#
# The original OrcaSlicer.app and its data dir are never modified.
#
# --remove X.Y.Z unregisters the wrapper and deletes all three, including the
# pinned data dir and any changes made to it while using that version. It lists
# what it will delete and asks for confirmation first.
set -euo pipefail

SRC_APP="/Applications/OrcaSlicer.app"
SRC_DATA="$HOME/Library/Application Support/OrcaSlicer"
APPS_DIR="$HOME/.local/apps"
VERSION=""
FORCE=0
REMOVE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --remove) REMOVE=1; VERSION="${2:-}"; shift $(( $# > 1 ? 2 : 1 )) ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

if [ "$REMOVE" -eq 1 ]; then
  [ -n "$VERSION" ] || { echo "--remove needs a version, e.g. --remove 2.3.2" >&2; exit 2; }
  [ "$FORCE" -eq 0 ] || { echo "--force can't be combined with --remove" >&2; exit 2; }
  DEST_APP="$APPS_DIR/OrcaSlicer-$VERSION.app"
  DEST_DATA="$HOME/Library/Application Support/OrcaSlicer-$VERSION"
  WRAPPER="/Applications/OrcaSlicer $VERSION.app"
  if pgrep -f "$DEST_APP/Contents/MacOS/OrcaSlicer" >/dev/null; then
    echo "OrcaSlicer $VERSION is running; quit it first." >&2
    exit 1
  fi
  targets=()
  for target in "$WRAPPER" "$DEST_APP" "$DEST_DATA"; do
    [ -e "$target" ] && targets+=("$target")
  done
  [ ${#targets[@]} -gt 0 ] || { echo "no frozen OrcaSlicer $VERSION found" >&2; exit 1; }
  echo "This will delete:"
  for target in "${targets[@]}"; do
    echo "  $target ($(du -sh "$target" | awk '{print $1}'))"
  done
  read -r -p "Remove OrcaSlicer $VERSION? [y/N] " answer || answer=""
  case "$answer" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Aborted, nothing was removed."; exit 1 ;;
  esac
  for target in "${targets[@]}"; do
    echo "Removing $target"
    [ "$target" = "$WRAPPER" ] && "$LSREGISTER" -u "$WRAPPER" || true
    rm -rf "$target"
  done
  echo "Done. OrcaSlicer $VERSION removed."
  exit 0
fi

[ -d "$SRC_APP" ] || { echo "not found: $SRC_APP" >&2; exit 1; }
[ -d "$SRC_DATA" ] || { echo "not found: $SRC_DATA" >&2; exit 1; }
if pgrep -xi OrcaSlicer >/dev/null; then
  echo "OrcaSlicer is running; quit it first so the data dir copy is consistent." >&2
  exit 1
fi

if [ -z "$VERSION" ]; then
  VERSION=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$SRC_APP/Contents/Info.plist")
fi

DEST_APP="$APPS_DIR/OrcaSlicer-$VERSION.app"
DEST_DATA="$HOME/Library/Application Support/OrcaSlicer-$VERSION"
WRAPPER="/Applications/OrcaSlicer $VERSION.app"

for target in "$DEST_APP" "$DEST_DATA" "$WRAPPER"; do
  if [ -e "$target" ]; then
    if [ "$FORCE" -eq 1 ]; then
      rm -rf "$target"
    else
      echo "already exists: $target (use --force to replace)" >&2
      exit 1
    fi
  fi
done

echo "Copying app     -> $DEST_APP"
mkdir -p "$APPS_DIR"
ditto "$SRC_APP" "$DEST_APP"

echo "Copying datadir -> $DEST_DATA"
cp -R "$SRC_DATA" "$DEST_DATA"

echo "Building wrapper -> $WRAPPER"
mkdir -p "$WRAPPER/Contents/MacOS" "$WRAPPER/Contents/Resources"
cp "$DEST_APP/Contents/Resources/Icon.icns" "$WRAPPER/Contents/Resources/Icon.icns"

cat > "$WRAPPER/Contents/MacOS/launcher" <<EOF
#!/bin/zsh
exec "\$HOME/.local/apps/OrcaSlicer-$VERSION.app/Contents/MacOS/OrcaSlicer" \\
  --datadir "\$HOME/Library/Application Support/OrcaSlicer-$VERSION" "\$@"
EOF
chmod +x "$WRAPPER/Contents/MacOS/launcher"

cat > "$WRAPPER/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>launcher</string>
<key>CFBundleIdentifier</key><string>local.orcaslicer.pinned.$VERSION</string>
<key>CFBundleName</key><string>OrcaSlicer $VERSION</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleIconFile</key><string>Icon</string>
<key>CFBundleVersion</key><string>1</string>
</dict></plist>
EOF

codesign --force --deep --sign - "$WRAPPER"
touch "$WRAPPER"
"$LSREGISTER" -f "$WRAPPER"

echo "Done. Launch \"OrcaSlicer $VERSION\" from /Applications, Spotlight or Alfred."
