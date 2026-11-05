import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request
import uuid
from .runtime import Cancellation
from .i18n import message


def weights():
    return json.loads((Path(__file__).with_name('weights.json')).read_text(encoding='utf-8'))


def selected(level):
    w = weights()
    return [w['q8' if level >= 8 else 'q4'],w['t5Q5' if level >= 8 else 't5Q3'],w['vae']]


def verify_file(path, size, digest, cancel):
    cancel.check()
    if Path(path).stat().st_size != size: raise ValueError(message('Falsche Dateigröße: {name}',name=Path(path).name))
    sha = hashlib.sha256()
    with open(path,'rb') as f:
        while block:=f.read(4*1024*1024):
            cancel.check(); sha.update(block)
    cancel.check()
    if sha.hexdigest()!=digest: raise ValueError(message('Prüfsumme ungültig: {name}',name=Path(path).name))


def ensure_models(directory, level, cancel, progress, import_from=None, allow_download=False):
    directory = Path(directory); directory.mkdir(parents=True,exist_ok=True)
    paths=[]
    for weight in selected(level):
        cancel.check()
        target = directory/weight['name']
        if target.exists():
            try:
                progress(message('Prüfe {name}',name=target.name))
                verify_file(target,weight['size'],weight['sha256'],cancel)
                paths.append(target); continue
            except ValueError:
                if not (allow_download or import_from): raise
        stage = directory/('.model-'+uuid.uuid4().hex+'.part')
        try:
            source = Path(import_from)/weight['name'] if import_from else None
            if source and source.is_file():
                progress(message('Importiere {name}',name=source.name))
                with source.open('rb') as src, stage.open('wb') as dst:
                    while block:=src.read(4*1024*1024): cancel.check(); dst.write(block)
            elif allow_download:
                progress(message('Lade {name}',name=weight['name']))
                request = urllib.request.Request(weight['url'],headers={'User-Agent':'AVEN-Video-AI/3.5'})
                with urllib.request.urlopen(request,timeout=30) as response, stage.open('wb') as dst:
                    total=0; last=-1
                    while block:=response.read(1024*1024):
                        cancel.check(); total+=len(block)
                        if total>weight['size']: raise ValueError('Modelldownload ist größer als erwartet.')
                        dst.write(block)
                        percent=total*100//weight['size']
                        if percent!=last: progress(f'{weight["name"]}: {percent}%'); last=percent
            else:
                raise FileNotFoundError(message('Modell fehlt: {name}. Modelle über die App herunterladen oder importieren.',name=weight['name']))
            verify_file(stage,weight['size'],weight['sha256'],cancel)
            cancel.publish(lambda: os.replace(stage,target))
            paths.append(target)
        finally: stage.unlink(missing_ok=True)
    return paths
