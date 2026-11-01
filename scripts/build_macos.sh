#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/AVEN Video AI.app"
rm -rf "$DIST"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$ROOT/Info.plist" "$APP/Contents/Info.plist"
iconutil -c icns "$ROOT/Assets/AVEN.iconset" -o "$APP/Contents/Resources/AVEN.icns"
SDK="$(xcrun --sdk macosx --show-sdk-path)"
xcrun swiftc -O -swift-version 5 -target x86_64-apple-macosx14.0 -sdk "$SDK" \
  -framework AppKit -framework SwiftUI -framework AVFoundation -framework Vision \
  -framework CoreGraphics -framework CoreVideo -framework CoreText -framework UniformTypeIdentifiers \
  "$ROOT/Sources/AVENApp.swift" "$ROOT/Sources/VideoRenderer.swift" \
  -o "$APP/Contents/MacOS/AVEN Video AI"
chmod +x "$APP/Contents/MacOS/AVEN Video AI"
# Ad-hoc code signing is not Apple notarization.
codesign --force --sign - --timestamp=none "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
file "$APP/Contents/MacOS/AVEN Video AI"
ls -lh "$APP/Contents/MacOS/AVEN Video AI"
mkdir -p "$DIST/dmg-content"
cp -R "$APP" "$DIST/dmg-content/"
ln -s /Applications "$DIST/dmg-content/Programme"
hdiutil create -volname "AVEN Video AI" -srcfolder "$DIST/dmg-content" \
  -ov -format UDZO "$DIST/AVEN_Video_AI_Intel.dmg"
hdiutil verify "$DIST/AVEN_Video_AI_Intel.dmg"
echo "READY: $DIST/AVEN_Video_AI_Intel.dmg"
