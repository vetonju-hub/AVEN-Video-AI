"""Run on native Windows x64; creates the complete portable AVEN folder."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image
from aven.bundle import download_checked, extract_checked
from aven.runtime import Cancellation, run, user_root

ROOT=Path(__file__).resolve().parent


def check_app(args, timeout):
    # A --windowed executable has no stderr; main.py writes its traceback here.
    # Remove the previous check's log so a failure can never report stale data.
    error=user_root()/'app-error.log'
    error.unlink(missing_ok=True)
    print('Packaged check:', ' '.join(str(arg) for arg in args), flush=True)
    try:
        run(args,timeout=timeout)
    except Exception as exc:
        if error.is_file():
            detail=error.read_text(encoding='utf-8',errors='replace')
            raise RuntimeError(f'{exc}\nPackaged startup traceback ({error}):\n{detail}') from exc
        raise
    print('Packaged check passed.',flush=True)


def build():
    if os.name!='nt' or sys.maxsize<2**32: raise RuntimeError('Dieser Build benötigt Windows x64.')
    lock=json.loads((ROOT/'dependencies.lock.json').read_text())
    cache=ROOT/'.cache'; unpack=ROOT/'build-dependencies'
    if unpack.exists(): shutil.rmtree(unpack)
    unpack.mkdir()
    for asset in lock['assets']:
        print('Verified dependency:',asset['name'],flush=True)
        archive=download_checked(asset['url'],cache/asset['name'],asset['sha256'],Cancellation())
        extract_checked(archive,unpack/asset['name'].removesuffix('.zip'))
    ico=ROOT/'aven.ico'
    with Image.open(ROOT.parent/'Assets/AVEN.iconset/icon_256x256.png') as im: im.save(ico,format='ICO')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
                    '--name','AVEN Video AI','--icon',str(ico),'--add-data',str(ROOT/'aven/weights.json')+':aven',
                    '--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build'),'--specpath',str(ROOT),str(ROOT/'main.py')],cwd=ROOT,check=True)
    app=ROOT/'dist/AVEN Video AI'; engine=app/'engine'; engine.mkdir(exist_ok=True)
    notices=app/'ThirdParty'; notices.mkdir(exist_ok=True)
    for tree in unpack.iterdir():
        for source in tree.rglob('*'):
            if not source.is_file(): continue
            if source.suffix.lower() in {'.exe','.dll'}:
                target=engine/source.name
                if target.exists() and hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(source.read_bytes()).digest():
                    raise ValueError('Widersprüchliche Runtime-DLL: '+source.name)
                shutil.copy2(source,target)
            elif any(word in source.name.lower() for word in ['license','copying','readme','notice']):
                target=notices/tree.name/source.relative_to(tree); target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
    # Use the Visual Studio redistributable CRT, not a user's System32 DLLs.
    vs=Path('C:/Program Files/Microsoft Visual Studio')
    crts=sorted(vs.glob('**/VC/Redist/MSVC/*/x64/Microsoft.VC*.CRT'))
    if not crts: raise RuntimeError('Visual Studio x64 redistributable CRT fehlt im Build-Rechner.')
    for source in crts[-1].glob('*.dll'): shutil.copy2(source,engine/source.name)
    for name in ['sd-cli.exe','ffmpeg.exe','ffprobe.exe','msvcp140.dll','vcruntime140.dll']:
        if not (engine/name).exists(): raise RuntimeError('Paket unvollständig: '+name)
    shutil.copy2(ROOT/'dependencies.lock.json',app/'dependencies.lock.json')
    shutil.copy2(ROOT/'README_DEUTSCH.md',app/'START_HIER.txt')
    shutil.copy2(ROOT/'THIRD_PARTY.md',notices/'SOURCES_AND_LICENSES.md')
    # Frozen subprocess self-tests use explicit bundled paths and no Python install.
    smoke=ROOT/'packaged-smoke'
    check_app([app/'AVEN Video AI.exe','--self-test',smoke],timeout=300)
    check_app([app/'AVEN Video AI.exe','--gui-smoke'],timeout=60)
    result=json.loads((smoke/'self-test.json').read_text())
    if result['synthetic_media']!='passed': raise RuntimeError('Paket-Medientest fehlgeschlagen.')
    (app/'package-check.json').write_text(json.dumps(result,indent=2))
    (notices/'ffmpeg-buildconf.txt').write_text(run([engine/'ffmpeg.exe','-buildconf'],timeout=30),encoding='utf-8')
    hashes={str(p.relative_to(app)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in app.rglob('*') if p.is_file()}
    (app/'SHA256.json').write_text(json.dumps(hashes,indent=2))
    shutil.make_archive(str(ROOT/'dist/AVEN-v3.5-Windows-CUDA-x64'),'zip',root_dir=app.parent,base_dir=app.name)
    print('READY: AVEN-v3.5-Windows-CUDA-x64.zip',flush=True)


if __name__=='__main__': build()
