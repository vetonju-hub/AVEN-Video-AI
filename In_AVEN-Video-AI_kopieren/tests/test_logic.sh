#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
SWIFT_COMPILER="${SWIFTC:-swiftc}"
for suite in PolicyTests AdaptiveTests; do
  "$SWIFT_COMPILER" -swift-version 5 \
    "$ROOT/Sources/AdaptiveRealism.swift" "$ROOT/Sources/GenerationPolicy.swift" "$ROOT/Sources/RenderCancellation.swift" "$ROOT/Sources/PNGIntegrity.swift" \
    "$ROOT/tests/$suite.swift" -o "$TMP/$suite"
  "$TMP/$suite"
done
