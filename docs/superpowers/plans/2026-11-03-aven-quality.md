# AVEN Video AI repair Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for inline implementation and one final independent code review.

**Goal:** repair local generation configuration/output validation and improve media, prompt and duration controls.
**Architecture:** existing SwiftUI app, isolated Foundation logic for quality/CLI/timing; macOS media decoding and encoder boundary tests.
**Tech Stack:** Swift 5, AppKit/SwiftUI, AVFoundation, pinned stable-diffusion.cpp, Python build checks.
**Spec:** docs/superpowers/plans/2026-11-03-aven-quality-design.md

## Global Constraints
- No mandatory paid cloud APIs; preserve native macOS app.
- Quality settings do not silently fall with RAM. No 4 GB feasibility or Veo quality guarantee.
- Document reference-frame-only video input honestly.
- No proof of neural quality from compilation or frame metrics alone.

## Review Focus
- Resuming old jobs must not replay known-bad low-step settings or stale frames.
- Cancellation during encoding must not launch the next scene or report success.
- Corrupt/missing/mis-sized generated frames must fail before export.
- Long or fractional audio lengths must neither truncate at 240s nor loop or stretch music.
- Requested precision must not silently fall back to other weights.

### Task 1: Generation policy and duration logic
Files: Sources/AdaptiveRealism.swift, new Sources/GenerationPolicy.swift, tests/AdaptiveTests.swift, tests/PolicyTests.swift.
Interface: AVENQualityPlan.make; CodablePlan; AIJobManifest; GenerationPolicy.arguments; VideoTiming.resolve.
- [x] Add executable regression assertions for quality floor, hardware parity, 4n+1 frame count, 16fps, matching CLI cfg/flow/seed, precision enforcement and long/fractional durations; run RED.
- [x] Implement shared policy and safe legacy-job handling.
- [x] Run policy tests GREEN and commit.

### Task 2: Frame integrity, encoding, and resumable jobs
Files: Sources/AIGenerator.swift, Sources/AIFrameEncoder.swift, new Sources/FrameValidation.swift; tests/MediaTests.swift.
Consumes Task 1 manifest/timing/args; produces strictly validated preview clips plus diagnostics.
- [x] Add failing macOS integration tests (written; native execution blocked) for PNG validation, ordering, RGB orientation, exact clip/composition duration, missing frames, cancel and audio preservation.
- [x] Integrate validation/logging/atomic outputs/checkpoints and background model verification.
- [x] Run locally possible checks; commit with evidence limits. Native CI media tests remain blocked until upload approval.

### Task 3: Prompt, reference import and song mode
Files: Sources/AVENApp.swift, new Sources/MediaImport.swift.
Consumes Task 1 duration and Task 2 generation reference list.
- [x] Add tests for EXIF orientation, video reference extraction and invalid audio duration in MediaTests.
- [x] Add multiline prompt, seed/negative controls, selected image/video reference imports, automatic song length and deterministic smoke button.
- [ ] Compile in macOS CI where available; document UI validation limits; commit.

### Task 4: Reproducible builds and delivery
Files: scripts/build_macos.sh, .github/workflows/build-macos.yml, tests/test_on_mac.sh, tests/smoke_static.py, tests_smoke.py, Info.plist and German docs.
- [x] Add portable policy test entry point and native media tests; remove obsolete source-string checks.
- [x] Pin engine SHA; verify arch/dependencies/CLI flags/codesign/DMG and run CI on push and PR.
- [ ] Run whole available suite, review diff independently, fix findings, package complete update with exact limitations and installation instructions.
