"""Prepare the pinned FFmpeg on Windows before behavioral tests."""
import json
from pathlib import Path
import shutil
from aven.bundle import download_checked,extract_checked
from aven.runtime import Cancellation

root=Path(__file__).resolve().parent
asset=next(a for a in json.loads((root/'dependencies.lock.json').read_text())['assets'] if a['name']=='ffmpeg.zip')
archive=download_checked(asset['url'],root/'.cache/ffmpeg.zip',asset['sha256'],Cancellation())
extract_checked(archive,root/'build-test-ffmpeg')
target=root/'engine'; target.mkdir(exist_ok=True)
for name in ['ffmpeg.exe','ffprobe.exe']:
    paths=list((root/'build-test-ffmpeg').rglob(name))
    if len(paths)!=1: raise RuntimeError('FFmpeg-Paket enthält nicht genau ein '+name)
    shutil.copy2(paths[0],target/name)
