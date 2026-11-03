# AVEN Video AI quality and media repair

User scope: continue the existing Swift macOS app, prioritize usable local Wan output, then improve prompt entry, media import, music duration and hardware execution. Work autonomously in a separate branch.

Keep the existing native interface and stable-diffusion.cpp engine. Pin the engine revision rather than rebuilding arbitrary master. Use documented Wan VACE settings, a useful 480p/20+ step floor, explicit native 16fps, model precision based on the quality choice rather than RAM, and hardware-specific execution/offload only. Do not promise identical results across backends or that 4 GB can run this model.

Validate original generated frames before encoding, record command/engine/models/metrics, and expose a deterministic 2-second diagnostic. A frame statistic cannot certify object recognition or realism: export remains a preview requiring visual inspection. Reject missing, corrupt or wrong-size frames. Prevent stale partial output on resume and protect cancellation/checkpoints.

Add multiline prompt and negative prompt, reproducible seed, photo references and explicitly labelled video-as-reference-frame import; do not claim full video-to-video processing. Cycle imported references across scenes; -i is VACE subject reference rather than a guaranteed first frame. Music mode uses validated entire audio duration and preserves audio, with no silent 240-second truncation. Store references/audio in job so resume does not depend on originals.

Verification: executable logic tests, generated synthetic frame/encoder/music tests on macOS CI, engine help/architecture/linkage/signing/DMG checks, static checks locally. No claim that a macOS build or real neural inference passed unless actually run. Linux host has no Apple SDK. GitHub writes currently fail 403; deliver a complete patch/archive and simple Desktop instructions if access stays read-only.
