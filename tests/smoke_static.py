from pathlib import Path
import plistlib
import re
ROOT=Path(__file__).resolve().parents[1]
info=plistlib.loads((ROOT/'Info.plist').read_bytes())
assert info['CFBundleShortVersionString']=='3.0.0'
assert info['LSMinimumSystemVersion']=='14.0'
app=(ROOT/'Sources/AVENApp.swift').read_text()
profile=(ROOT/'Sources/AdaptiveRealism.swift').read_text()
engine=(ROOT/'Sources/AIGenerator.swift').read_text()
encoder=(ROOT/'Sources/AIFrameEncoder.swift').read_text()
assert 'ADAPTIVE REALISM ENGINE' in app
assert 'MAX REALISM' in app
assert 'ECHTES KI-VIDEO GENERIEREN' in app
assert 'Letzten Auftrag fortsetzen' in app
assert '1...10' in app
assert 'physicalMemory' in profile
assert 'MTLCreateSystemDefaultDevice' in profile
assert 'metal' in profile and 'cpu' in profile
assert 'frames = category == 0' in profile
assert 'targetSeconds: min(240, max(2, targetSeconds))' in engine
assert 'launchNextScene()' in engine
assert 'job.json' in engine
assert 'generated_%03d.png' in engine, 'sd-cli must output individual AI frames'
assert '--video-frames' in engine and '"vid_gen"' in engine
assert 'AVAssetWriter' in encoder and 'AVMutableComposition' in encoder
assert 'scene_%03d' in engine
assert (ROOT/'.github/workflows/build-macos.yml').exists()
assert (ROOT/'scripts/build_macos.sh').exists()
print('PASS: v3 project, adaptive profiles, local model pipeline, scene checkpointing, frames encoder, installer references')
