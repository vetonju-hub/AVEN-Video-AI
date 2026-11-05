from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import re
from .i18n import message

NEGATIVE = 'blurry, out of focus, low quality, noise, flicker, deformed anatomy, bad motion, oversaturated, text, watermark'
SMOKE_PROMPT = 'A ginger cat sitting on a wooden table in a sunlit room. The cat slowly turns its head. Sharp focus, natural colors, static camera.'
ENGINE_TAG = 'master-1043-3be2378'
BACKEND = 'diffusion=cuda0,te=cpu,vae=cpu'
CONTINUATION_FRAMES = 4


def duration(manual, music, match_music):
    value = music if match_music else manual
    if value is None or not math.isfinite(value) or not 0 < value <= 86400:
        raise ValueError('Eine gültige Länge zwischen 0 und 24 Stunden ist erforderlich. Musik zuerst importieren.')
    return float(value)


def target_duration(manual_text, music, match_music):
    return duration(0 if match_music else float(manual_text),music,match_music)


@dataclass(frozen=True)
class Plan:
    level: int
    width: int
    height: int
    steps: int
    threads: int
    frames: int = 33
    fps: int = 16
    cfg: float = 5.0
    shift: float = 16.0
    memory_mode: str = 'balanced'
    vram_gb: float = 8.0

    @staticmethod
    def make(level, fmt, cores=None, memory_mode='balanced', vram_mb=10240):
        if type(level) is not int or not 1 <= level <= 10:
            raise ValueError('Realismusstufe muss zwischen 1 und 10 liegen.')
        if memory_mode not in ('balanced','resident'): raise ValueError('Unbekanntes Speicherprofil.')
        if not math.isfinite(vram_mb) or vram_mb<6144: raise ValueError('Mindestens 6 GB Grafikspeicher erforderlich.')
        high = level >= 8
        sizes = {'16:9': (1024,576) if high else (832,480),
                 '9:16': (576,1024) if high else (480,832),
                 '1:1': (768,768) if high else (640,640)}
        if fmt not in sizes: raise ValueError('Unbekanntes Videoformat.')
        w,h = sizes[fmt]
        return Plan(level,w,h,[20,22,24,26,28,32,36,40,44,50][level-1],
                    max(1,min(16,(cores or os.cpu_count() or 1)//2)),
                    memory_mode=memory_mode,vram_gb=math.floor((vram_mb-2048)/512)/2)

    def validate(self):
        if self.memory_mode not in ('balanced','resident') or not math.isfinite(self.vram_gb) or not 4<=self.vram_gb<=256:
            raise ValueError('Unbekanntes Speicherprofil.')
        for fmt in ['16:9','9:16','1:1']:
            expected = Plan.make(self.level,fmt)
            fields = ['width','height','steps','frames','fps','cfg','shift']
            if all(getattr(self,k)==getattr(expected,k) for k in fields) and 1 <= self.threads <= 16:
                return
        raise ValueError('Veraltetes oder ungültiges Qualitätsprofil. Neuen Auftrag starten.')


def engine_arguments(plan, prompt, negative, seed, models, scene, reference=None, *, control_video=None):
    plan.validate()
    if not prompt.strip(): raise ValueError('Bitte eine Szenenbeschreibung eingeben.')
    if type(seed) is not int or not 0 <= seed <= 2147483647: raise ValueError('Seed muss zwischen 0 und 2147483647 liegen.')
    frames = plan.frames + (CONTINUATION_FRAMES if control_video else 0)
    args = ['-M','vid_gen','--diffusion-model',str(models[0]),'--t5xxl',str(models[1]),'--vae',str(models[2]),
            '-p',prompt,'-n',negative,'--video-frames',str(frames),'--fps',str(plan.fps),
            '--steps',str(plan.steps),'-W',str(plan.width),'-H',str(plan.height),
            '--cfg-scale',str(plan.cfg),'--flow-shift',str(plan.shift),'--sampling-method','euler',
            '--scheduler','discrete','--rng','cpu','--backend',BACKEND,'--params-backend',('diffusion=cpu,te=cpu,vae=cpu' if plan.memory_mode=='balanced' else BACKEND),
            '--max-vram',f'cuda0={plan.vram_gb:g}',
            '--auto-fit','off','--flash-attn','auto','--vae-tiling','--vae-tile-size','256x256',
            '--temporal-tiling','-t',str(plan.threads),'--seed',str(seed),'-v',
            '-o',str(Path(scene)/'generated_%03d.png')]
    if reference: args += ['-i',str(reference)]
    if control_video: args += ['--control-video',str(control_video)]
    return args


def ordered_frames(files, count):
    numbered = []
    for f in files:
        m = re.fullmatch(r'generated_(\d+)\.png',Path(f).name)
        if m: numbered.append((int(m[1]),Path(f)))
    numbered.sort(key=lambda x:x[0])
    if [i for i,_ in numbered] != list(range(count)):
        raise ValueError(message('Unvollständige Bildfolge: {actual} statt {expected} fortlaufender PNGs.',actual=len(numbered),expected=count))
    return [f for _,f in numbered]
