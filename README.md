# AVEN Video AI v3 — Adaptive Realism Engine

Native macOS SwiftUI application for **Intel and Apple Silicon**; genuine offline inference with stable-diffusion.cpp and Wan2.1 VACE 1.3B. No Python, PyTorch, cloud inference, subscription, or terminal necessary for everyday use. Model weights must be downloaded once from Hugging Face (~4.5 GB for Q4, more for Q8).

## Implemented

- Detects CPU architecture, CPU thread count, physical RAM, and Metal GPU.
- Adapts video diffusion steps, image size, frame count, quantization tier, CPU threads, and backend based on hardware and user-defined realism level (1–10).
- **MAX REALISM** (level 10): more compute-heavy locally suitable settings; doesn't promise photorealism or guarantee better frames. May fail due to memory or take extremely long on Intel 16 GB.
- Image/reference-to-video or prompt-to-video (Wan VACE), new model-computed frames; no zoom-only placeholder in AI mode.
- Up to 240 seconds via sequential AI clips; per-clip MP4 saves, persistent `job.json`, resume previous job, final video assembly with optional audio.
- Previous photo montage video editor still available (5–240 seconds).
- Intel package uses CPU inference; Apple Silicon builds an optional Metal backend. Same source adapts to both. **No Windows installer in this release.**
- Q4 quantized model for low RAM, Q8 with more precise text encoder available for higher RAM (separate download); no automatic claim that model quality increases monotonically with more steps.

## What is NOT yet verified

- This Linux session can check Swift syntax but **cannot compile or run the native app or inference engine on macOS**. The GitHub Actions workflows compile and smoke-test sd-cli on macOS; an actual generative model render must be tested on your Mac after the model download.
- The first Wan video render may exceed 16 GB usable RAM depending on input and upstream engine version. Rendering 240 seconds of *unique* AI scenes locally may take days/weeks; it is not a single 4-minute generation. Some large models simply do not fit regardless of time.
- **Windows PC support is a future port**, not an advertised built product.
- The highest realism level cannot substitute for a larger model, powerful GPU or better training; it just increases compute and applies the best available settings for the current hardware class.

## Architecture

- `Sources/AVENApp.swift`: SwiftUI app, controls for quality and scene duration
- `Sources/AdaptiveRealism.swift`: hardware detection and deterministic performance profiles
- `Sources/AIGenerator.swift`: model download, local sd-cli Process, scene queue, persistent manifest, resume
- `Sources/AIFrameEncoder.swift`: model-frame H.264 encoding and multi-clip assembly via AVFoundation
- `Sources/VideoRenderer.swift`: earlier non-generative photo montage editor
- `.github/workflows/build-macos.yml`: real macOS Intel and Apple Silicon builds + hardware tests + DMG artifacts
- `scripts/build_macos.sh`: Swift compiler, C++ inference engine, ad hoc signing, DMG

## Model and engine sources

- Wan2.1: https://github.com/Wan-Video/Wan2.1
- stable-diffusion.cpp: https://github.com/leejet/stable-diffusion.cpp (MIT)
- Quantized Wan VACE: https://huggingface.co/calcuis/wan-1.3b-gguf
- UMT5 text encoder: https://huggingface.co/city96/umt5-xxl-encoder-gguf
- Wan VAE: https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged

Model licenses must be reviewed by the user before redistribution. AVEN does not redistribute model weights in the installer. The standalone installer builds the underlying engine from upstream source during GitHub Actions, so users don't need to use a terminal.

See [INSTALLATION_DEUTSCH.md](INSTALLATION_DEUTSCH.md) for step-by-step installation.
