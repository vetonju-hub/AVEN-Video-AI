import codecs
import csv
import io
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import threading
import time
import uuid
from .i18n import message


class Cancelled(Exception):
    pass


class Cancellation:
    def __init__(self):
        self.event = threading.Event()
        self.lock = threading.RLock()

    def cancel(self):
        with self.lock: self.event.set()

    def check(self):
        if self.event.is_set(): raise Cancelled('Auftrag angehalten. Fertige Szenen bleiben erhalten.')

    def publish(self, operation):
        with self.lock:
            self.check()
            return operation()


def app_root():
    return Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]


def user_root():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'.local/share')))/'AVEN Video AI'


def local_path(root, value):
    if not isinstance(value,str) or not value or PureWindowsPath(value).drive or '\\' in value:
        raise ValueError('Ungültiger Auftragspfad.')
    root = root.resolve()
    p = (root/value).resolve()
    if not p.is_relative_to(root) or Path(value).is_absolute(): raise ValueError('Auftragspfad liegt außerhalb des Auftrags.')
    return p


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name('.'+uuid.uuid4().hex+'.json')
    try:
        tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


def run(args, cancellation=None, log=None, timeout=None, cwd=None, on_output=None):
    cancellation = cancellation or Cancellation()
    cancellation.check()
    kwargs = {'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
    # Read stderr too, never let a full pipe deadlock an encoder/model process.
    with subprocess.Popen([str(x) for x in args],cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,**kwargs) as p:
        chunks = []; reader_errors=[]
        def drain():
            decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
            try:
                while True:
                    data = p.stdout.read1(4096)
                    if not data: break
                    if log:
                        log.write(data); log.flush()
                    else: chunks.append(data)
                    if on_output: on_output(decoder.decode(data))
                tail=decoder.decode(b'',final=True)
                if tail and on_output: on_output(tail)
            except Exception as e: reader_errors.append(e)
        t = threading.Thread(target=drain,daemon=True); t.start()
        start = time.monotonic()
        try:
            while p.poll() is None:
                cancellation.check()
                if reader_errors: raise reader_errors[0]
                if timeout is not None and time.monotonic()-start > timeout: raise TimeoutError('Prozess-Zeitlimit überschritten.')
                time.sleep(.05)
            t.join()
            if reader_errors: raise reader_errors[0]
            cancellation.check()
            output = b''.join(chunks).decode('utf-8',errors='replace')
            if p.returncode:
                raise RuntimeError(message('{name}: Fehlercode {code}. {detail}',name=Path(args[0]).name,code=p.returncode,detail=output[-2500:] if not log else message('Bitte engine.log im Szenenordner prüfen.')))
            return output
        finally:
            if p.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    import signal
                    try: os.killpg(p.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                p.wait()
            t.join(timeout=5)


def binary(name):
    executable = name+'.exe' if os.name=='nt' else name
    bundled = app_root()/'engine'/executable
    if bundled.is_file(): return bundled
    # A built Windows package must never use unrelated PATH executables.
    if not getattr(sys,'frozen',False) and os.name!='nt':
        found = shutil.which(executable)
        if found: return Path(found)
    raise FileNotFoundError(message('{name} fehlt im App-Paket. Bitte das vollständige Windows-Paket entpacken.',name=executable))


def nvidia_info():
    exe = shutil.which('nvidia-smi')
    if not exe and os.name=='nt':
        p = Path(os.environ.get('WINDIR','C:/Windows'))/'System32/nvidia-smi.exe'
        if p.exists(): exe=str(p)
    if not exe: raise ValueError('NVIDIA-Treiber nicht gefunden. NVIDIA-Treiber installieren und die App neu starten.')
    output = run([exe,'--query-gpu=name,memory.total,driver_version','--format=csv,noheader,nounits'],timeout=20)
    rows = list(csv.reader(io.StringIO(output)))
    if not rows: raise ValueError('Keine NVIDIA-Grafikkarte gefunden.')
    name, memory, driver = [x.strip() for x in rows[0]]
    return {'name':name,'vram_mb':int(memory),'driver':driver}


def cuda_preflight(cancellation):
    info = nvidia_info()
    if info['vram_mb'] < 6144: raise ValueError('Dieses CUDA-Profil benötigt mindestens 6 GB Grafikspeicher. Kein automatischer Qualitätsverlust.')
    devices = run([binary('sd-cli'),'--list-devices'],cancellation,timeout=60)
    if 'cuda0' not in devices.lower():
        raise ValueError('Die gebündelte KI-Engine findet CUDA0 nicht. NVIDIA-Treiber und engine.log prüfen. CPU-Ersatz wurde nicht gestartet.')
    return info


def nvidia_sample():
    exe=shutil.which('nvidia-smi')
    if not exe and os.name=='nt':
        p=Path(os.environ.get('WINDIR','C:/Windows'))/'System32/nvidia-smi.exe'
        if p.exists(): exe=str(p)
    if not exe: return None
    output=run([exe,'--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],timeout=3)
    rows=list(csv.reader(io.StringIO(output)))
    if not rows: return None
    used,total,util=[int(x.strip()) for x in rows[0]]
    if not 0<=used<=total or not 0<=util<=100: return None
    return {'used_mb':used,'total_mb':total,'utilization_percent':util}
