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
for tool in xcrun swiftc cmake iconutil codesign hdiutil git lipo otool; do
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
    -framework Metal -framework UniformTypeIdentifiers -framework ImageIO -framework CryptoKit \
    "$ROOT"/Sources/*.swift \
    -o "$APP/Contents/MacOS/AVEN Video AI"
chmod +x "$APP/Contents/MacOS/AVEN Video AI"

BUILD_TMP="$(mktemp -d)"
trap 'rm -rf "$BUILD_TMP"' EXIT
ENGINE_REVISION="$(tr -d '\n\r' < "$ROOT/scripts/engine-revision.txt")"
if [[ ! "$ENGINE_REVISION" =~ ^[0-9a-f]{40}$ ]]; then echo "Invalid pinned engine revision" >&2; exit 1; fi
git init --quiet "$BUILD_TMP/stable-diffusion.cpp"
git -C "$BUILD_TMP/stable-diffusion.cpp" remote add origin https://github.com/leejet/stable-diffusion.cpp.git
git -C "$BUILD_TMP/stable-diffusion.cpp" fetch --quiet --depth 1 origin "$ENGINE_REVISION"
git -C "$BUILD_TMP/stable-diffusion.cpp" checkout --quiet --detach FETCH_HEAD
# Only ggml is needed for the CLI; skip CUDA CUTLASS, web codecs and server frontend.
git -C "$BUILD_TMP/stable-diffusion.cpp" submodule update --init --depth 1 ggml
git -C "$BUILD_TMP/stable-diffusion.cpp" rev-parse HEAD > "$APP/Contents/Resources/AIEngine/upstream-commit.txt"
METAL=OFF
if [[ "$ARCH" == "arm64" ]]; then METAL=ON; fi
cmake -S "$BUILD_TMP/stable-diffusion.cpp" -B "$BUILD_TMP/build" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES="$ARCH" -DCMAKE_OSX_DEPLOYMENT_TARGET=14.0 \
    -DSD_METAL="$METAL" -DSD_CUDA=OFF -DSD_VULKAN=OFF \
    -DSD_WEBP=OFF -DSD_WEBM=OFF -DSD_BUILD_EXAMPLES=ON \
    -DSD_BUILD_SHARED_LIBS=OFF -DSD_BUILD_SHARED_GGML_LIB=OFF \
    -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF \
    -DGGML_METAL_EMBED_LIBRARY=ON
cmake --build "$BUILD_TMP/build" --target sd-cli --parallel 3
cp "$BUILD_TMP/build/bin/sd-cli" "$APP/Contents/Resources/AIEngine/sd-cli"
chmod +x "$APP/Contents/Resources/AIEngine/sd-cli"
cp "$BUILD_TMP/stable-diffusion.cpp/LICENSE" "$APP/Contents/Resources/AIEngine/LICENSE.sd.cpp.txt"
cp "$BUILD_TMP/stable-diffusion.cpp/ggml/LICENSE" "$APP/Contents/Resources/AIEngine/LICENSE.ggml.txt"

# Contract checks only: executing --help is not a neural generation test.
"$APP/Contents/Resources/AIEngine/sd-cli" --version > "$APP/Contents/Resources/AIEngine/version.txt"
"$APP/Contents/Resources/AIEngine/sd-cli" --help > "$BUILD_TMP/sd-cli-help.txt" 2>&1
for flag in vid_gen video-frames fps flow-shift scheduler backend auto-fit vae-tile-size temporal-tiling; do
  if ! grep -q -- "$flag" "$BUILD_TMP/sd-cli-help.txt"; then
    echo "ERROR: Required engine argument missing: $flag" >&2; exit 1
  fi
done
for binary in "$APP/Contents/MacOS/AVEN Video AI" "$APP/Contents/Resources/AIEngine/sd-cli"; do
  actual="$(lipo -archs "$binary")"
  if [[ "$actual" != "$ARCH" ]]; then echo "Wrong architecture: $actual, expected $ARCH" >&2; exit 1; fi
done
# Ensure bundled executable is not dependent on an external brew-installed library.
if otool -L "$APP/Contents/Resources/AIEngine/sd-cli" | tail -n +2 | awk '{print $1}' | grep -Ev '^(/usr/lib/|/System/Library/)'  ; then
  echo 'ERROR: sd-cli depends on libraries missing from the application bundle.' >&2
  exit 1
fi
codesign --force --sign - --timestamp=none "$APP/Contents/Resources/AIEngine/sd-cli"
codesign --force --deep --sign - --timestamp=none "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

mkdir -p "$DIST/dmg-content"
cp -R "$APP" "$DIST/dmg-content/"
ln -s /Applications "$DIST/dmg-content/Programme"
OUTPUT="$DIST/AVEN_Video_AI_v3.4_${ARCH}.dmg"
hdiutil create -volname "AVEN Video AI v3.4" -srcfolder "$DIST/dmg-content" \
    -ov -format UDZO "$OUTPUT"
hdiutil verify "$OUTPUT"
echo "READY: $OUTPUT"
