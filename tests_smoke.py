"""Offline static project smoke tests (does NOT claim macOS inference is verified)."""
from pathlib import Path
import subprocess
import zipfile

root = Path(__file__).resolve().parent
src = (root/'Sources/AIGenerator.swift').read_text()
ui = (root/'Sources/AVENApp.swift').read_text()
workflow = (root/'.github/workflows/build-macos.yml').read_text()
build = (root/'scripts/build_macos.sh').read_text()
assert '"-M", "vid_gen"' in src
assert '"--video-frames", "9"' in src
assert '"-i", reference.path' in src
assert '"--backend", "cpu"' in src
assert '"--t5xxl"' in src
assert '"--vae"' in src
assert 'frame_%03d.png' in src
assert 'URLSessionDownloadDelegate' in src
assert '"ECHTE KI-ANIMATION TESTEN"' in ui
assert 'private var aiControls' in ui
assert 'localAI.generate(' in ui
assert 'AIGenerator.swift' in build
assert 'stable-diffusion.cpp' in build and 'SD_METAL=OFF' in build
assert 'runs-on: macos-26-intel' in workflow
assert 'dist/AVEN_Video_AI_Intel.dmg' in workflow
subprocess.run(['bash', '-n', str(root/'scripts/build_macos.sh')], check=True)
subprocess.run(['swiftc', '-frontend', '-parse'] + [str(p) for p in sorted((root/'Sources').glob('*.swift'))], check=True)
print('OK: 16 source/build assertions, bash -n, swiftc syntax parse.')
print('NOT TESTED: Compiling on macOS, downloading 4+GB weights, running GGML or rendering neural video.')
