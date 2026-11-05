"""Cheap project metadata and confined original-frame paths; never scan all frames."""
import json
import math
from pathlib import Path
from .policy import CONTINUATION_FRAMES, Plan, duration, ENGINE_TAG
from .story import validate_story
from .runtime import local_path


def list_projects(root, limit=500):
    root=Path(root)
    if not root.exists(): return []
    rows=[]
    for folder in sorted((p for p in root.iterdir() if p.is_dir() and not p.is_symlink()),key=lambda p:p.name,reverse=True)[:limit]:
        manifest=folder/'job.json'
        if not manifest.exists(): continue
        row={'folder':folder,'name':folder.name,'valid':False,'output_exists':False,'completed':0,'total':0,'prompt':''}
        try:
            if manifest.is_symlink() or manifest.stat().st_size>1024*1024: raise ValueError('Invalid manifest')
            data=json.loads(manifest.read_text(encoding='utf-8'))
            if not isinstance(data,dict): raise ValueError('Invalid manifest root')
            if data.get('version') not in (1,2) or data.get('engine')!=ENGINE_TAG: raise ValueError('Invalid job version')
            if data.get('source_video')!=('source.mp4' if data['version']==2 else None): raise ValueError('Invalid continuation')
            refs=data.get('references')
            if not isinstance(refs,list) or len(refs)>1000: raise ValueError('Invalid references')
            for name in refs: local_path(folder,name)
            if data.get('story') is not None: validate_story(data['story'],data['seconds'])
            plan=Plan(**data['plan']); plan.validate(); duration(data['seconds'],None,False)
            n=math.ceil(data['seconds']/(plan.frames/plan.fps))
            if type(data['completed']) is not int or not 0<=data['completed']<=n or not isinstance(data['prompt'],str): raise ValueError('Invalid progress')
            output=local_path(folder,'AVEN_KI_VORSCHAU.mp4')
            row.update(valid=True,prompt=data['prompt'][:120],completed=data['completed'],total=n,
                       seconds=data['seconds'],output_exists=output.is_file(),data=data)
        except (OSError,ValueError,KeyError,TypeError,OverflowError): pass
        rows.append(row)
    return rows


def scene_frames(folder, number):
    if type(number) is not int or not 1<=number<=100000: raise ValueError('Ungültige Szenennummer.')
    result=[]
    for index in range(33):
        try: p=local_path(Path(folder),f'scene_{number:06}/generated_{index:03}.png')
        except ValueError: continue
        if p.is_file(): result.append(p)
    return result


def reference_path(folder, data, index, *, scene=None):
    refs=data.get('references',[])
    if type(index) is int and 0<=index<len(refs):
        name=refs[index]
    elif index is None and data.get('version')==2 and type(scene) is int and 1<=scene<=100000:
        name=f'scene_{scene:06}/control/frame_{CONTINUATION_FRAMES-1:03}.png'
    else: return None
    path=local_path(Path(folder),name)
    return path if path.is_file() else None


def save_assessment(folder,choice,notes):
    from .runtime import atomic_json
    if choice not in ('accepted','needs_work','pending_user_review') or not isinstance(notes,str) or len(notes)>12000:
        raise ValueError('Ungültige Qualitätsbewertung.')
    path=local_path(Path(folder),'benchmark.json')
    if path.stat().st_size>1024*1024: raise ValueError('Messbericht ist ungültig.')
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict): raise ValueError('Messbericht ist ungültig.')
    data.update(visual_assessment=choice,visual_notes=notes)
    atomic_json(path,data)


def report_caption(report):
    """Render independently validated values; corrupt values are never reported as zero."""
    from .i18n import message
    from .telemetry import clock
    if not isinstance(report,dict): raise ValueError('Messbericht ist ungültig.')
    hardware=report.get('hardware'); plan=report.get('plan')
    hardware=hardware if isinstance(hardware,dict) else {}
    plan=plan if isinstance(plan,dict) else {}
    unknown=message('Nicht gemessen')
    def number(value):
        return value if type(value) in (int,float) and 0<=value<=1e12 and math.isfinite(value) else None
    def measured(value):
        value=number(value)
        return unknown if value is None else value
    elapsed=number(report.get('elapsed_seconds'))
    status=report.get('status')
    states={'completed':'Abgeschlossen','failed':'Fehlgeschlagen','cancelled':'Angehalten'}
    state=message(states.get(status,'Nicht gemessen')) if isinstance(status,str) else unknown
    name=hardware.get('name')
    mode=plan.get('memory_mode')
    return message('Status: {status} · Laufzeit: {elapsed} · Szenen: {scenes}\nGPU: {gpu}\nGemessener VRAM-Höchstwert: {peak} MB ({samples} Messungen, gesamte GPU)\nProfil: {width}×{height}, {steps} Schritte, {mode}\nBildqualität und natürliche Bewegung bitte selbst anhand der Originalbilder und des Videos prüfen.',
        status=state,elapsed=clock(elapsed) if elapsed is not None else unknown,
        scenes=measured(report.get('completed_scenes')),gpu=name if isinstance(name,str) and name else unknown,
        peak=measured(report.get('peak_sampled_vram_mb')),samples=measured(report.get('gpu_samples')),
        width=measured(plan.get('width')),height=measured(plan.get('height')),steps=measured(plan.get('steps')),
        mode=message('Gewichte im VRAM' if mode=='resident' else 'Gewichte im Arbeitsspeicher') if mode in ('resident','balanced') else unknown)
