"""Measured engine progress. Never synthesize neural quality or total-job ETA."""
import math
import re
import threading
import time
from .runtime import nvidia_sample

ANSI=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
STEP=re.compile(r'\|\s*(\d+)\s*/\s*(\d+)\s*-\s*([\d.]+)\s*s/it')


class SamplingProgress:
    def __init__(self, steps):
        self.steps=steps; self.step=0; self.remaining_seconds=None
        self.active=False; self.buffer=''

    def feed(self, chunk):
        self.buffer+=chunk
        lines=re.split(r'[\r\n]',self.buffer)
        self.buffer=lines.pop()[-16384:]
        for raw in lines:
            line=ANSI.sub('',raw)
            if re.search(r'\bsample \d+x\d+x\d+\b',line): self.active=True
            if 'sampling completed' in line.lower():
                self.step=self.steps; self.active=False; self.remaining_seconds=None
            m=STEP.search(line)
            if not self.active or not m: continue
            step,total=int(m[1]),int(m[2]); rate=float(m[3])
            if total!=self.steps or not self.step<=step<=total: continue
            if not math.isfinite(rate) or rate<=0: continue
            self.step=step; self.remaining_seconds=(total-step)*rate


class Tracker:
    def __init__(self, steps, callback=None):
        self.steps=steps; self.callback=callback or (lambda s:None)
        self.lock=threading.RLock(); self.started=time.monotonic()
        self.stage='preflight'; self.scene=0; self.total=0
        self.parser=SamplingProgress(steps); self.gpu=None; self.peak_mb=None
        self.samples=0; self.stop=threading.Event(); self.thread=None
        self.sampling_seen=False; self.engine_invocations=0; self.generated_scenes=0; self.last_emit=0

    def phase(self, stage, scene=None, total=None):
        with self.lock:
            self.stage=stage
            if scene is not None:
                if scene!=self.scene: self.parser=SamplingProgress(self.steps)
                self.scene=scene
            if total is not None: self.total=total
        self.emit(force=True)

    def feed(self, text):
        with self.lock:
            self.parser.feed(text)
            if self.parser.active:
                self.stage='sampling'; self.sampling_seen=True
            elif self.parser.step==self.steps: self.stage='decode'
        self.emit()

    def snapshot(self):
        with self.lock:
            return {'stage':self.stage,'scene':self.scene,'scenes':self.total,
                    'step':self.parser.step,'steps':self.steps,'elapsed_seconds':time.monotonic()-self.started,
                    'sampling_eta_seconds':self.parser.remaining_seconds if self.stage=='sampling' else None,
                    'gpu':self.gpu,'peak_sampled_vram_mb':self.peak_mb,'gpu_samples':self.samples}

    def emit(self,force=False):
        now=time.monotonic()
        with self.lock:
            if not force and now-self.last_emit<.15: return
            self.last_emit=now
        self.callback(self.snapshot())

    def start(self):
        def worker():
            while not self.stop.is_set():
                try: sample=nvidia_sample()
                except Exception: sample=None
                with self.lock:
                    self.gpu=sample
                    if sample:
                        self.samples+=1
                        self.peak_mb=max(self.peak_mb or 0,sample['used_mb'])
                self.emit()
                if self.stop.wait(2): break
        self.thread=threading.Thread(target=worker,daemon=True); self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread: self.thread.join(timeout=4)

    def report(self, status, hardware, plan, completed, synthetic=False):
        s=self.snapshot()
        return {'schema':1,'status':status,'inference':'synthetic_fixture' if synthetic else 'neural_engine',
                'hardware':hardware,'plan':plan,'elapsed_seconds':s['elapsed_seconds'],
                'peak_sampled_vram_mb':s['peak_sampled_vram_mb'],'gpu_samples':s['gpu_samples'],
                'gpu_measurement':'whole GPU, sampled every 2 seconds, not an exact process peak',
                'sampling_progress_observed':self.sampling_seen,'completed_scenes':completed,
                'engine_invocations':self.engine_invocations,'generated_scenes_this_run':self.generated_scenes,
                'visual_assessment':'pending_user_review',
                'limitations':'Frame variation and edge metrics do not prove subject quality, realism or natural motion. Sampling ETA excludes loading, VAE, encoding and future scenes.'}


def clock(seconds):
    seconds=max(0,int(seconds)); h,rest=divmod(seconds,3600); m,s=divmod(rest,60)
    return f'{h:d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


def status_text(event):
    from .i18n import message
    stages={'preflight':'CUDA prüfen','models':'Modelle prüfen','loading':'Modelle laden / Referenzen vorbereiten',
            'sampling':'KI-Schritte','decode':'Originalbilder decodieren','frames':'Originalbilder prüfen',
            'encoding':'MP4 speichern','muxing':'Musik und Szenen verbinden','completed':'Fertig','cancelled':'Angehalten'}
    gpu=event.get('gpu')
    gpu_text=message('VRAM {used}/{total} MB · GPU {util} %',used=gpu['used_mb'],total=gpu['total_mb'],util=gpu['utilization_percent']) if gpu else message('GPU-Messung nicht verfügbar')
    eta=event.get('sampling_eta_seconds')
    eta_text=message('Restzeit dieser KI-Schritte: ca. {time} (ohne Laden/VAE/MP4)',time=clock(eta)) if eta is not None else message('Restzeit unbekannt')
    return message('Szene {scene}/{scenes} · {stage} · Schritt {step}/{steps} · Laufzeit {elapsed}\n{gpu}\n{eta}',
                   scene=event['scene'],scenes=event['scenes'],stage=message(stages.get(event['stage'],event['stage'])),
                   step=event['step'],steps=event['steps'],elapsed=clock(event['elapsed_seconds']),gpu=gpu_text,eta=eta_text)
