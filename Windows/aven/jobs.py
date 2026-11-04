from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import time
from pathlib import Path
import uuid
from .policy import Plan, ENGINE_TAG, duration, engine_arguments, ordered_frames
from .runtime import atomic_json, binary, cuda_preflight, local_path, run
from .models import ensure_models
from .media import import_reference, inspect_frames, encode_scene, combine, validate_clip
from .i18n import message
from .story import validate_story, scene_spec
from .telemetry import Tracker
from .runtime import Cancelled


def digest(path, cancel=None):
    sha=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(4*1024*1024):
            if cancel: cancel.check()
            sha.update(block)
    return sha.hexdigest()


def copy_file(source, target, cancel):
    with Path(source).open('rb') as src, Path(target).open('wb') as dst:
        while block:=src.read(4*1024*1024): cancel.check(); dst.write(block)
    cancel.check()


def create_job(root, plan, prompt, negative, seed, seconds, references, soundtrack, cancel, story=None):
    plan.validate(); duration(seconds,None,False)
    engine_arguments(plan,prompt,negative,seed,['m','t','v'],Path('.'))
    if story is not None: validate_story(story,seconds)
    if not isinstance(prompt,str) or len(prompt)>12000 or len(negative)>12000: raise ValueError('Prompt ist zu lang (maximal 12000 Zeichen).')
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    job=root/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]); job.mkdir()
    refs=[]; hashes={}
    for i,(source,at) in enumerate(references):
        name=f'reference_{i:03}.png'; target=job/name
        import_reference(source,target,at,cancel)
        refs.append(name); hashes[name]=digest(target,cancel)
    sound=None
    if soundtrack:
        sound='soundtrack'+Path(soundtrack).suffix.lower()
        copy_file(soundtrack,job/sound,cancel); hashes[sound]=digest(job/sound,cancel)
    state={'version':1,'engine':ENGINE_TAG,'plan':asdict(plan),'prompt':prompt,'negative':negative,
           'seed':seed,'seconds':seconds,'references':refs,'soundtrack':sound,'hashes':hashes,
           'story':story,'completed':0,'created':datetime.now(timezone.utc).isoformat()}
    cancel.check(); atomic_json(job/'job.json',state)
    return job


def load_job(folder, cancel=None):
    folder=Path(folder)
    try:
        if (folder/'job.json').stat().st_size>1024*1024: raise ValueError('Auftragsdatei ist zu groß.')
        data=json.loads((folder/'job.json').read_text(encoding='utf-8'))
        if data['version']!=1 or data['engine']!=ENGINE_TAG: raise ValueError('Veralteter Auftrag. Bitte einen neuen Auftrag starten.')
        plan=Plan(**data['plan']); plan.validate(); duration(data['seconds'],None,False)
        engine_arguments(plan,data['prompt'],data['negative'],data['seed'],['m','t','v'],folder)
        if data.get('story') is not None: validate_story(data['story'],data['seconds'])
        n=math.ceil(data['seconds']/(plan.frames/plan.fps))
        if type(data['completed']) is not int or not 0<=data['completed']<=n: raise ValueError('Ungültiger Szenenstand.')
        if not isinstance(data['references'],list) or len(data['references'])>1000: raise ValueError('Ungültige Referenzen.')
        names=data['references']+([data['soundtrack']] if data['soundtrack'] else [])
        for name in names:
            path=local_path(folder,name)
            if not path.is_file() or digest(path,cancel)!=data['hashes'][name]:
                raise ValueError('Eine gesicherte Referenz oder Musikdatei fehlt oder wurde verändert.')
        return data
    except (KeyError,TypeError,OverflowError,json.JSONDecodeError) as e:
        raise ValueError('Auftragsdatei ist ungültig oder unvollständig.') from e


def generate(folder, model_dir, cancel, progress, engine=None, telemetry=None):
    folder=Path(folder); data=load_job(folder,cancel); plan=Plan(**data['plan'])
    tracker=Tracker(plan.steps,telemetry); hardware={}; status='failed'; started=time.time()
    tracker.start()
    try:
        progress('Prüfe NVIDIA-Treiber und CUDA …')
        hardware=cuda_preflight(cancel); atomic_json(folder/'hardware.json',hardware)
        result=_generate(folder,model_dir,cancel,progress,data,tracker,engine)
        status='completed'; tracker.phase('completed')
        return result
    except Cancelled:
        status='cancelled'; tracker.phase('cancelled'); raise
    finally:
        tracker.close()
        report=tracker.report(status,hardware,asdict(plan),data['completed'],synthetic=engine is not None)
        report['started_unix']=started
        report['frame_reports']=[f'scene_{i+1:06}/frame-report.json' for i in range(data['completed'])]
        # Best-effort reporting must not mask an inference/cancellation error.
        try:
            atomic_json(folder/('benchmark-'+uuid.uuid4().hex+'.json'),report)
            atomic_json(folder/'benchmark.json',report)
        except OSError:
            if status=='completed': raise


def _generate(folder, model_dir, cancel, progress, data, tracker, engine=None):
    folder=Path(folder)
    plan=Plan(**data['plan'])
    tracker.phase('models')
    models=ensure_models(model_dir,plan.level,cancel,progress)
    count=math.ceil(data['seconds']/(plan.frames/plan.fps)); clips=[]
    for i in range(count):
        cancel.check(); tracker.phase('loading',i+1,count)
        scene=folder/f'scene_{i+1:06}'
        clip=scene/'clip.mp4'
        if i<data['completed']:
            try:
                frames=ordered_frames(scene.glob('generated_*.png'),33)
                report=inspect_frames(frames,plan.width,plan.height,cancel)
            except (OSError,ValueError,RuntimeError):
                data['completed']=i; atomic_json(folder/'job.json',data)
            else:
                try:
                    validate_clip(clip,33/16,cancel,33,(plan.width,plan.height),plan.fps)
                    saved=json.loads((scene/'frame-report.json').read_text(encoding='utf-8'))
                    if not isinstance(saved,dict) or saved.get('clip_sha256')!=digest(clip,cancel): raise ValueError('Videocache wurde verändert.')
                except (OSError,ValueError,RuntimeError):
                    progress(message('Szene {number}: Videocache wird aus geprüften Originalbildern neu erstellt …',number=i+1))
                    if clip.exists(): clip.rename(scene/('clip-invalid-'+uuid.uuid4().hex+'.mp4'))
                    encode_scene(frames,plan.fps,clip,cancel)
                    report['clip_sha256']=digest(clip,cancel)
                    atomic_json(scene/'frame-report.json',report)
                clips.append(clip); continue
        if scene.exists(): scene.rename(folder/(scene.name+'-interrupted-'+uuid.uuid4().hex[:8]))
        scene.mkdir()
        spec=scene_spec(data,i)
        refs=data['references']; reference=local_path(folder,refs[spec['reference']]) if spec['reference'] is not None else None
        atomic_json(scene/'scene.json',spec)
        args=engine_arguments(plan,spec['prompt'],data['negative'],(data['seed']+i*9973)%2147483648,models,scene,reference)
        command=list(engine) if engine else [binary('sd-cli')]
        command+=args
        atomic_json(scene/'command.json',{'engine':ENGINE_TAG,'argv':[str(x) for x in command]})
        progress(message('KI-Szene {number}/{total} wird berechnet.',number=i+1,total=count))
        tracker.engine_invocations+=1
        with (scene/'engine.log').open('wb') as log: run(command,cancel,log=log,cwd=scene,on_output=tracker.feed)
        tracker.phase('frames')
        frames=ordered_frames(scene.glob('generated_*.png'),plan.frames)
        report=inspect_frames(frames,plan.width,plan.height,cancel)
        tracker.generated_scenes+=1
        atomic_json(scene/'frame-report.json',report)
        progress(message('Szene {number}: Originalbilder werden als MP4 gespeichert …',number=i+1))
        tracker.phase('encoding')
        encode_scene(frames,plan.fps,clip,cancel)
        report['clip_sha256']=digest(clip,cancel)
        atomic_json(scene/'frame-report.json',report)
        clips.append(clip); data['completed']=i+1
        cancel.publish(lambda:atomic_json(folder/'job.json',data))
        progress(message('Szene {number} gespeichert.',number=i+1))
    cancel.check(); output=folder/'AVEN_KI_VORSCHAU.mp4'
    tracker.phase('muxing')
    progress('Szenen und Musik werden zusammengefügt …')
    combine(clips,output,data['seconds'],local_path(folder,data['soundtrack']) if data['soundtrack'] else None,cancel)
    cancel.check()
    return output
