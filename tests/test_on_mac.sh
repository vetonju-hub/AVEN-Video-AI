#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
xcrun swiftc -swift-version 5 -framework Metal \
  "$ROOT/Sources/AdaptiveRealism.swift" "$ROOT/tests/AdaptiveTests.swift" \
  -o "$TMP/aven-hardware-tests"
"$TMP/aven-hardware-tests"
bash -n "$ROOT/scripts/build_macos.sh"
echo 'OK: macOS hardware tests and shell syntax'
