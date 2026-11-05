from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import shutil
import time
from pathlib import Path
import uuid
from .policy import CONTINUATION_FRAMES, Plan, ENGINE_TAG, duration, engine_arguments, ordered_frames
from .runtime import atomic_json, binary, cuda_preflight, local_path, run
from .models import ensure_models
from .media import (import_reference, inspect_frames, encode_scene, combine, validate_clip,
                    prepare_source_video, video_duration, write_control_video)
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


def create_job(root, plan, prompt, negative, seed, seconds, references, soundtrack, cancel, story=None,
               *, source_video=None, avatar=None):
    plan.validate(); duration(seconds,None,False)
    engine_arguments(plan,prompt,negative,seed,['m','t','v'],Path('.'))
    if story is not None: validate_story(story,seconds)
    if not isinstance(prompt,str) or len(prompt)>12000 or len(negative)>12000: raise ValueError('Prompt ist zu lang (maximal 12000 Zeichen).')
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    job=root/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]); job.mkdir()
    try:
        refs=[]; hashes={}
        for i,(source,at) in enumerate([(avatar,0)] if avatar else references):
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
        if source_video:
            video='source.mp4'; audio='source.flac'
            has_audio=prepare_source_video(source_video,job/video,job/audio,plan,cancel)
            duration(video_duration(job/video,cancel)+seconds,None,False)
            hashes[video]=digest(job/video,cancel)
            if has_audio: hashes[audio]=digest(job/audio,cancel)
            state.update(version=2,source_video=video,source_audio=audio if has_audio else None)
        cancel.publish(lambda:atomic_json(job/'job.json',state))
    except Exception:
        shutil.rmtree(job,ignore_errors=True)
        raise
    return job


def load_job(folder, cancel=None):
    folder=Path(folder)
    try:
        if (folder/'job.json').stat().st_size>1024*1024: raise ValueError('Auftragsdatei ist zu groß.')
        data=json.loads((folder/'job.json').read_text(encoding='utf-8'))
        if data['version'] not in (1,2) or data['engine']!=ENGINE_TAG: raise ValueError('Veralteter Auftrag. Bitte einen neuen Auftrag starten.')
        plan=Plan(**data['plan']); plan.validate(); duration(data['seconds'],None,False)
        engine_arguments(plan,data['prompt'],data['negative'],data['seed'],['m','t','v'],folder)
        if data.get('story') is not None: validate_story(data['story'],data['seconds'])
        n=math.ceil(data['seconds']/(plan.frames/plan.fps))
        if type(data['completed']) is not int or not 0<=data['completed']<=n: raise ValueError('Ungültiger Szenenstand.')
        if not isinstance(data['references'],list) or len(data['references'])>1000: raise ValueError('Ungültige Referenzen.')
        source_video=data.get('source_video'); source_audio=data.get('source_audio')
        if (source_video not in (None,'source.mp4') or source_audio not in (None,'source.flac')
                or (source_audio and not source_video) or bool(source_video)!=(data['version']==2)):
            raise ValueError('Auftragsdatei ist ungültig oder unvollständig.')
        names=data['references']+[name for name in (data['soundtrack'],source_video,source_audio) if name is not None]
        for name in names:
            path=local_path(folder,name)
            if not path.is_file() or digest(path,cancel)!=data['hashes'][name]:
                raise ValueError('Eine gesicherte Mediendatei fehlt oder wurde verändert.')
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
    source_video=local_path(folder,data['source_video']) if data.get('source_video') else None
    source_audio=local_path(folder,data['source_audio']) if data.get('source_audio') else None
    for i in range(count):
        cancel.check(); tracker.phase('loading',i+1,count)
        scene=folder/f'scene_{i+1:06}'
        clip=scene/'clip.mp4'
        if i<data['completed']:
            try:
                frames=ordered_frames(scene.glob('generated_*.png'),plan.frames)
                report=inspect_frames(frames,plan.width,plan.height,cancel)
            except (OSError,ValueError,RuntimeError):
                data['completed']=i; atomic_json(folder/'job.json',data)
            else:
                try:
                    validate_clip(clip,plan.frames/plan.fps,cancel,plan.frames,(plan.width,plan.height),plan.fps)
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
        control=None
        if source_video:
            control=scene/'control'
            write_control_video(clips[-1] if clips else source_video,control,plan.fps,cancel)
            if reference is None: reference=control/f'frame_{CONTINUATION_FRAMES-1:03}.png'
        args=engine_arguments(plan,spec['prompt'],data['negative'],(data['seed']+i*9973)%2147483648,
                              models,scene,reference,control_video=control)
        command=list(engine) if engine else [binary('sd-cli')]
        command+=args
        atomic_json(scene/'command.json',{'engine':ENGINE_TAG,'argv':[str(x) for x in command]})
        progress(message('KI-Szene {number}/{total} wird berechnet.',number=i+1,total=count))
        tracker.engine_invocations+=1
        with (scene/'engine.log').open('wb') as log: run(command,cancel,log=log,cwd=scene,on_output=tracker.feed)
        tracker.phase('frames')
        overlap=CONTINUATION_FRAMES if control else 0
        frames=ordered_frames(scene.glob('generated_*.png'),plan.frames+overlap)
        if overlap:
            # Preserve every model PNG. The overlap belongs to the existing clip timeline.
            for index,path in enumerate(frames):
                cancel.check()
                name=f'overlap_{index:03}.png' if index<overlap else f'generated_{index-overlap:03}.png'
                path.rename(scene/name)
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
    combine(clips,output,data['seconds'],local_path(folder,data['soundtrack']) if data['soundtrack'] else None,cancel,
            source_video=source_video,source_audio=source_audio)
    cancel.check()
    return output
