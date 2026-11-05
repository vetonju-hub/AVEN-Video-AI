"""Build-time verified dependency transfer; no binary downloads during generation."""
import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import urllib.request
import uuid
import zipfile
from .runtime import Cancellation


def download_checked(url, destination, sha256, cancel):
    destination=Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
    cancel.check()
    if destination.exists():
        with destination.open('rb') as old:
            if hashlib.file_digest(old,'sha256').hexdigest()==sha256: return destination
    temp=destination.with_name('.download-'+uuid.uuid4().hex)
    try:
        sha=hashlib.sha256(); size=0
        request=urllib.request.Request(url,headers={'User-Agent':'AVEN-Video-AI-Build/3.5'})
        with urllib.request.urlopen(request,timeout=60) as src,temp.open('wb') as dst:
            while block:=src.read(4*1024*1024):
                cancel.check(); size+=len(block)
                if size>4*1024**3: raise ValueError('Archiv überschreitet die maximale Größe.')
                sha.update(block); dst.write(block)
        if sha.hexdigest()!=sha256: raise ValueError('Archiv-Prüfsumme stimmt nicht: '+destination.name)
        cancel.publish(lambda:os.replace(temp,destination))
        return destination
    finally: temp.unlink(missing_ok=True)


def extract_checked(archive, destination):
    destination=Path(destination); destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        total=0
        for entry in z.infolist():
            name=entry.filename; relative=PurePosixPath(name)
            if ('\\' in name or ':' in name or relative.is_absolute() or '..' in relative.parts or
                PureWindowsPath(name).drive or stat.S_ISLNK(entry.external_attr>>16)):
                raise ValueError('Unsicherer Archivpfad: '+name)
            total+=entry.file_size
            if total>8*1024**3: raise ValueError('Entpacktes Archiv ist zu groß.')
            target=(destination/Path(*relative.parts)).resolve()
            if not target.is_relative_to(destination.resolve()): raise ValueError('Archivpfad liegt außerhalb des Zielordners.')
            if entry.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(entry) as src:
                if target.exists():
                    with target.open('rb') as old:
                        if hashlib.file_digest(src,'sha256').digest()!=hashlib.file_digest(old,'sha256').digest():
                            raise ValueError('Konflikt zwischen gebündelten Dateien: '+name)
                else:
                    with target.open('wb') as dst: shutil.copyfileobj(src,dst,4*1024*1024)
