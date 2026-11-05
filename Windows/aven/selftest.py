"""Packaged synthetic media smoke check. This never claims neural inference."""
import json
import os
from pathlib import Path
import tempfile
import sys
from PIL import Image,ImageDraw
from .runtime import Cancellation, binary, run, atomic_json
from .media import encode_scene, combine, validate_clip


def engine_contract():
    if sys.platform!='win32': return 'not_run_not_windows'
    # This release imports nvcuda.dll directly, even for --help. It belongs to
    # the installed NVIDIA driver, not to the redistributable CUDA runtime ZIP.
    driver=Path(os.environ.get('WINDIR','C:/Windows'))/'System32/nvcuda.dll'
    if not driver.is_file(): return 'not_run_no_nvidia_driver'
    help_text=run([binary('sd-cli'),'--help'],timeout=60)
    for flag in ['--backend','--params-backend','--video-frames','--flow-shift','--scheduler','--auto-fit','--temporal-tiling','--max-vram']:
        if flag not in help_text: raise ValueError('Engine-Vertrag fehlt: '+flag)
    return 'passed'


def self_test(folder):
    from .models import selected
    if len(selected(1))!=3: raise ValueError('Gebündelte Modellquellen fehlen.')
    support='not_run_not_windows'
    if sys.platform=='win32':
        import ctypes
        directory=binary('sd-cli').parent
        # These real dependencies need no NVIDIA device. Always load them,
        # including OpenMP, even if the driver-dependent CLI cannot run in CI.
        for name in ['ggml-base.dll','ggml.dll','libsharpyuv.dll','libwebp.dll','libwebpmux.dll','webm.dll']:
            ctypes.WinDLL(str(directory/name),winmode=0x1100)
        support='passed'
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    from .i18n import Locale
    language=Locale(folder/'language-test.json'); language.select('en')
    if language.render('Musik hinzufügen')!='Add music' or Locale(language.path).code!='en':
        raise ValueError('Packaged language test failed')
    files=[]
    for i in range(33):
        p=folder/f'generated_{i:03}.png'
        im=Image.new('RGB',(64,64),'red'); d=ImageDraw.Draw(im)
        d.rectangle((0,0,63,31),fill='green'); d.rectangle((i,40,i+8,55),fill='blue'); im.save(p); files.append(p)
    clip=folder/'clip.mp4'; encode_scene(files,16,clip,Cancellation())
    result=folder/'fractional.mp4'; combine([clip],result,1.337,None,Cancellation()); validate_clip(result,1.337)
    contract=engine_contract()
    atomic_json(folder/'self-test.json',{'synthetic_media':'passed','language_switch':'passed','engine_support_dlls':support,'engine_cli':contract,'neural_video':'not_run','cuda_inference':'not_run','frames':33,'fractional_seconds':1.337})


def gui_smoke(root,studio):
    """Native Windows CI uses actual widgets/buttons; no user's settings are written."""
    from .i18n import Locale, message
    from tkinter import ttk
    original_path=studio.language.path
    original_code=studio.language.code
    try:
        with tempfile.TemporaryDirectory() as temporary:
            studio.language.path=Path(temporary)/'settings.json'
            studio.prompt.delete('1.0','end'); studio.prompt.insert('1.0','My own prompt ü {keep}')
            studio.seed.set('12345'); studio.seconds.set('5.375')
            for widget in studio.controls: widget.configure(state='disabled')
            before=[str(widget.cget('state')) for widget in studio.controls]
            studio.set_text(studio.status,message('Szene {number} gespeichert.',number=3))
            studio.language_buttons['en'].invoke(); root.update()
            assert Locale(studio.language.path).code=='en'
            assert studio.status.get()=='Scene 3 saved.'
            assert any(str(w.cget('text'))=='Add music' for w in studio.controls if 'text' in w.keys())
            assert studio.prompt.get('1.0','end').strip()=='My own prompt ü {keep}'
            assert studio.seed.get()=='12345' and studio.seconds.get()=='5.375'
            assert [str(widget.cget('state')) for widget in studio.controls]==before
            studio.language_buttons['de'].invoke(); root.update()
            assert studio.status.get()=='Szene 3 gespeichert.'
            assert any(str(w.cget('text'))=='Musik hinzufügen' for w in studio.controls if 'text' in w.keys())
            # Exercise actual new Tk controls and original-frame comparison in native CI.
            for widget in studio.controls:
                widget.configure(state='readonly' if isinstance(widget,ttk.Combobox) else 'normal')
            studio.story.sections.delete('1.0','end')
            studio.story.sections.insert('1.0','0 | Intro | wide shot\n2 | Chorus | close-up')
            assert studio.story.value(5)['sections'][1]['start']==2
            from .jobs import create_job
            from .policy import Plan
            from .studio_panels import show_report
            jobs=Path(temporary)/'Jobs'
            ref=Path(temporary)/'ref.png'; Image.new('RGB',(64,32),'red').save(ref)
            job=create_job(jobs,Plan.make(1,'16:9'),'test','',42,2,[(ref,0)],None,Cancellation())
            scene=job/'scene_000001'; scene.mkdir()
            for i in range(2):
                im=Image.new('RGB',(64,32),'green'); ImageDraw.Draw(im).rectangle((i,0,20,31),fill='blue')
                im.save(scene/f'generated_{i:03}.png')
            original_jobs=studio.jobs; original_job=studio.job
            studio.jobs=jobs; studio.job=job
            browser=studio.browse(); root.update()
            assert browser.a.photo is not None and browser.a.path.name=='generated_000.png'
            browser.compare(); assert browser.b.photo is not None
            browser.a.index.set(1); browser.a.render(); assert browser.a.path.name=='generated_001.png'
            browser.a.reference.set(True); browser.a.render(); assert browser.a.path.name=='reference_000.png'
            browser.a.native(); root.update()
            studio.language_buttons['en'].invoke(); root.update()
            assert browser.table.heading('scenes')['text']=='Scenes'
            assert browser.table.set(browser.table.selection()[0],'status')=='No MP4 yet'
            atomic_json(job/'benchmark.json',{'status':'completed','elapsed_seconds':3,'hardware':{},'plan':{},'completed_scenes':1})
            report=show_report(studio,job); root.update()
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child; yield from descendants(child)
            accept=next(w for w in descendants(report) if 'text' in w.keys() and str(w.cget('text'))=='Subject and motion look good')
            accept.invoke(); assert json.loads((job/'benchmark.json').read_text())['visual_assessment']=='accepted'
            browser.top.destroy(); studio.jobs=original_jobs; studio.job=original_job
            studio.language_buttons['de'].invoke(); root.update()

    finally:
        studio.language.path=original_path
        studio.language.code=original_code
