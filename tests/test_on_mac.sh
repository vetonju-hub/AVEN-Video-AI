#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
bash "$ROOT/tests/test_logic.sh"
xcrun swiftc -swift-version 5 -framework AppKit -framework AVFoundation \
  -framework CoreGraphics -framework CoreVideo -framework CoreText -framework AudioToolbox -framework ImageIO -framework UniformTypeIdentifiers \
  "$ROOT/Sources/AdaptiveRealism.swift" "$ROOT/Sources/GenerationPolicy.swift" \
  "$ROOT/Sources/RenderCancellation.swift" "$ROOT/Sources/MediaImport.swift" \
  "$ROOT/Sources/FrameValidation.swift" "$ROOT/Sources/PNGIntegrity.swift" "$ROOT/Sources/AIFrameEncoder.swift" \
  "$ROOT/Sources/VideoFormat.swift" "$ROOT/Sources/VideoRenderer.swift" \
  "$ROOT/tests/MediaTests.swift" -o "$TMP/aven-media-tests"
"$TMP/aven-media-tests" "$ROOT/tests/Fixtures"
python3 "$ROOT/tests/smoke_static.py"
echo 'PASS: native policy, actual PNG/MP4/audio integration and build metadata checks'
