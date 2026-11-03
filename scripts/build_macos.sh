#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
ARCH="$(uname -m)"
APP="$DIST/AVEN Video AI.app"

if [[ "$ARCH" != "x86_64" && "$ARCH" != "arm64" ]]; then
  echo "This build requires an Intel or Apple Silicon macOS machine." >&2
  exit 1
fi
for tool in xcrun swiftc cmake iconutil codesign hdiutil git; do
  command -v "$tool" >/dev/null || { echo "Missing build dependency: $tool" >&2; exit 1; }
done
rm -rf "$DIST"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/AIEngine"
cp "$ROOT/Info.plist" "$APP/Contents/Info.plist"
iconutil -c icns "$ROOT/Assets/AVEN.iconset" -o "$APP/Contents/Resources/AVEN.icns"
SDK="$(xcrun --sdk macosx --show-sdk-path)"
TARGET="${ARCH}-apple-macosx14.0"
xcrun swiftc -O -swift-version 5 -target "$TARGET" -sdk "$SDK" \
    -framework AppKit -framework SwiftUI -framework AVFoundation -framework Vision \
    -framework CoreGraphics -framework CoreVideo -framework CoreText \
    -framework Metal -framework UniformTypeIdentifiers \
    "$ROOT/Sources/AVENApp.swift" "$ROOT/Sources/VideoRenderer.swift" \
    "$ROOT/Sources/AdaptiveRealism.swift" "$ROOT/Sources/AIGenerator.swift" \
    "$ROOT/Sources/AIFrameEncoder.swift" \
    -o "$APP/Contents/MacOS/AVEN Video AI"
chmod +x "$APP/Contents/MacOS/AVEN Video AI"

BUILD_TMP="$(mktemp -d)"
trap 'rm -rf "$BUILD_TMP"' EXIT
git clone --quiet --depth 1 --recurse-submodules https://github.com/leejet/stable-diffusion.cpp.git "$BUILD_TMP/stable-diffusion.cpp"
git -C "$BUILD_TMP/stable-diffusion.cpp" rev-parse HEAD > "$APP/Contents/Resources/AIEngine/upstream-commit.txt"
METAL=OFF
if [[ "$ARCH" == "arm64" ]]; then METAL=ON; fi
cmake -S "$BUILD_TMP/stable-diffusion.cpp" -B "$BUILD_TMP/build" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES="$ARCH" \
    -DSD_METAL="$METAL" -DSD_CUDA=OFF -DSD_VULKAN=OFF \
    -DSD_WEBP=OFF -DSD_WEBM=OFF -DSD_BUILD_EXAMPLES=ON \
    -DSD_BUILD_SHARED_LIBS=OFF -DSD_BUILD_SHARED_GGML_LIB=OFF \
    -DBUILD_SHARED_LIBS=OFF
cmake --build "$BUILD_TMP/build" --target sd-cli --parallel 3
cp "$BUILD_TMP/build/bin/sd-cli" "$APP/Contents/Resources/AIEngine/sd-cli"
chmod +x "$APP/Contents/Resources/AIEngine/sd-cli"

# A real integration smoke test: the engine must execute and expose the video mode.
"$APP/Contents/Resources/AIEngine/sd-cli" --help > "$BUILD_TMP/sd-cli-help.txt" 2>&1 || true
if ! grep -qi 'vid_gen\|video-frames\|video generation' "$BUILD_TMP/sd-cli-help.txt"; then
    echo 'ERROR: Bundled sd-cli did not provide video generation flags' >&2
    head -40 "$BUILD_TMP/sd-cli-help.txt" >&2
    exit 1
fi
# Ensure bundled executable is not dependent on an external brew-installed library.
if otool -L "$APP/Contents/Resources/AIEngine/sd-cli" | grep -E '/opt/homebrew|/usr/local/opt|@rpath/libggml|@rpath/libstable' ; then
  echo 'ERROR: sd-cli depends on libraries missing from the application bundle.' >&2
  exit 1
fi
codesign --force --sign - --timestamp=none "$APP/Contents/Resources/AIEngine/sd-cli"
codesign --force --deep --sign - --timestamp=none "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

mkdir -p "$DIST/dmg-content"
cp -R "$APP" "$DIST/dmg-content/"
ln -s /Applications "$DIST/dmg-content/Programme"
OUTPUT="$DIST/AVEN_Video_AI_v3_${ARCH}.dmg"
hdiutil create -volname "AVEN Video AI v3" -srcfolder "$DIST/dmg-content" \
    -ov -format UDZO "$OUTPUT"
hdiutil verify "$OUTPUT"
echo "READY: $OUTPUT"
