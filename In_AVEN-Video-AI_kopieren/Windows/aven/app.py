import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
from . import VERSION
from .i18n import Locale, Bindings, message, ENGLISH
from .policy import Plan, NEGATIVE, SMOKE_PROMPT, target_duration
from .runtime import Cancellation, Cancelled, user_root, nvidia_info
from .models import ensure_models
from .media import audio_duration, save_avatar
from .jobs import create_job, generate, load_job
from .studio_panels import StoryEditor, ProjectBrowser, show_report
from .telemetry import status_text


DEFAULT_PROMPT = 'A quiet city street at night, purple neon reflected on wet pavement. A slow forward camera movement, sharp focus, natural lighting.'


class Studio:
    def __init__(self, root):
        self.root=root; root.title('AVEN Video AI · Windows CUDA '+VERSION)
        root.geometry('1120x850'); root.minsize(800,650); root.configure(bg='#11121c')
        self.events=queue.SimpleQueue(); self.busy=False; self.closing=False
        self.token=Cancellation(); self.job=None; self.output=None; self.references=[]
        self.audio=None; self.audio_seconds=None; self.controls=[]; self.views=[]; self.hardware_info=None; self.testing=False
        self.data=user_root(); self.models=self.data/'Models'; self.jobs=self.data/'Jobs'
        self.source_video=None; self.avatar_path=self.data/'avatar.png'
        self.data.mkdir(parents=True,exist_ok=True)
        self.language=Locale(self.data/'settings.json'); self.bindings=Bindings(self.language); self.text_variables={}
        style=ttk.Style(root); style.theme_use('clam')
        style.configure('.',background='#191b29',foreground='#eeeeff',font=('Segoe UI',11))
        style.configure('TButton',padding=(12,9),background='#34314c',borderwidth=0)
        style.map('TButton',background=[('active','#675090')],foreground=[('disabled','#858197')])
        style.configure('Accent.TButton',background='#9957ef',foreground='white')
        style.configure('TEntry',fieldbackground='#26283b',foreground='white',insertcolor='white')
        style.configure('TCombobox',fieldbackground='#26283b',background='#34314c',foreground='white')
        style.map('TCombobox',fieldbackground=[('readonly','#26283b')],foreground=[('readonly','white')])
        style.configure('Header.TLabel',font=('Segoe UI',26,'bold'),foreground='#b986ff')
        style.configure('Info.TLabel',foreground='#bab6ce')
        header=ttk.Frame(root,padding=18); header.pack(fill='x')
        languages=ttk.Frame(header); languages.pack(side='right',anchor='n')
        self.language_buttons={}
        for code,caption in [('de','Deutsch'),('en','English')]:
            b=self.localized(ttk.Button,languages,text=caption,command=lambda code=code:self.set_language(code))
            b.pack(side='left',padx=4); self.language_buttons[code]=b
        self.localized(ttk.Label,header,text='AVEN  /  VIDEO AI',style='Header.TLabel').pack(anchor='w')
        self.localized(ttk.Label,header,text='Windows · NVIDIA CUDA · lokale Verarbeitung',style='Info.TLabel').pack(anchor='w')
        self.hardware=self.variable('RTX-Profil: Diffusion über CUDA0 · Textencoder und VAE über CPU/RAM')
        self.localized(ttk.Label,header,textvariable=self.hardware,wraplength=1000,style='Info.TLabel').pack(anchor='w',pady=(8,0))

        container=ttk.Frame(root); container.pack(fill='both',expand=True)
        canvas=tk.Canvas(container,bg='#11121c',highlightthickness=0)
        scroll=ttk.Scrollbar(container,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set); scroll.pack(side='right',fill='y'); canvas.pack(fill='both',expand=True)
        body=ttk.Frame(canvas,padding=20); item=canvas.create_window((0,0),window=body,anchor='nw')
        body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
        canvas.bind_all('<MouseWheel>',lambda e:canvas.yview_scroll(int(-e.delta/120),'units'))
        def label(text): self.localized(ttk.Label,body,text=text,font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(14,6))
        label('Szenenbeschreibung')
        self.prompt=tk.Text(body,height=4,wrap='word',bg='#252637',fg='white',insertbackground='white',font=('Segoe UI',11),relief='flat',padx=10,pady=10)
        self.prompt.insert('1.0',DEFAULT_PROMPT)
        self.prompt.pack(fill='x'); self.controls.append(self.prompt)
        self.localized(ttk.Label,body,text='Motiv, Bewegung, Licht und Kamera beschreiben. Englische Prompts funktionieren mit Wan meist besser.',style='Info.TLabel',wraplength=1000).pack(anchor='w',pady=5)
        label('Video fortsetzen')
        row=ttk.Frame(body); row.pack(fill='x')
        self.button(row,'Clip auswählen',self.choose_source_video).pack(side='left',padx=(0,8))
        self.button(row,'Clip entfernen',lambda:self.set_source_video(None)).pack(side='left')
        self.source_label=self.variable('Kein Clip zur Fortsetzung ausgewählt')
        self.localized(ttk.Label,body,textvariable=self.source_label,style='Info.TLabel',wraplength=720).pack(anchor='w',pady=(6,0))
        self.localized(ttk.Label,body,text='Beschreibe oben, was nach dem Clip passieren soll. Die letzten Bilder dienen als Ausgangspunkt. Musik und Länge gelten für den neuen Teil.',
                       style='Info.TLabel',wraplength=720).pack(anchor='w',pady=(4,0))
        label('Negativer Prompt')
        self.negative=tk.Text(body,height=2,wrap='word',bg='#252637',fg='white',insertbackground='white',relief='flat',padx=10,pady=8)
        self.negative.insert('1.0',NEGATIVE); self.negative.pack(fill='x'); self.controls.append(self.negative)
        row=ttk.Frame(body); row.pack(fill='x',pady=14)
        self.seed=tk.StringVar(value='42'); self.seconds=tk.StringVar(value='30'); self.format=tk.StringVar(value='16:9'); self.level=tk.IntVar(value=1)
        self.duration_label=self.variable('Eigene Länge (Sekunden)')
        for title,var in [(self.variable('Seed'),self.seed),(self.duration_label,self.seconds)]:
            ttk.Label(row,textvariable=title).pack(side='left',padx=(0,8))
            entry=ttk.Entry(row,textvariable=var,width=14); entry.pack(side='left',padx=(0,18)); self.controls.append(entry)
        self.localized(ttk.Label,row,text='Format').pack(side='left',padx=(0,8))
        combo=ttk.Combobox(row,textvariable=self.format,values=['16:9','9:16','1:1'],state='readonly',width=7)
        combo.pack(side='left'); self.controls.append(combo); combo.bind('<<ComboboxSelected>>',lambda e:self.describe())
        self.match=tk.BooleanVar(value=True)
        self.match_label=self.variable('Videolänge automatisch an die gesamte Musik anpassen')
        match_button=ttk.Checkbutton(body,textvariable=self.match_label,variable=self.match)
        match_button.pack(anchor='w'); self.controls.append(match_button)
        self.audio_label=self.variable('Keine Musik ausgewählt')
        self.localized(ttk.Label,body,textvariable=self.audio_label,style='Info.TLabel',wraplength=1000).pack(anchor='w',pady=6)
        buttons=ttk.Frame(body); buttons.pack(fill='x')
        self.button(buttons,'Musik hinzufügen',self.choose_audio).pack(side='left',padx=(0,8))
        self.button(buttons,'Musik entfernen',self.remove_audio).pack(side='left')
        label('Fester Avatar')
        row=ttk.Frame(body); row.pack(fill='x')
        self.avatar_preview=ttk.Label(row); self.avatar_photo=None
        self.avatar_preview.pack(side='left',padx=(0,8))
        avatar_controls=ttk.Frame(row); avatar_controls.pack(side='left',fill='x',expand=True)
        avatar_buttons=ttk.Frame(avatar_controls); avatar_buttons.pack(anchor='w')
        self.button(avatar_buttons,'Avatarbild auswählen',self.choose_avatar).pack(side='left',padx=(0,8))
        self.button(avatar_buttons,'Avatar entfernen',self.remove_avatar).pack(side='left')
        self.avatar_label=self.variable('Kein Avatar gespeichert')
        self.localized(ttk.Label,avatar_controls,textvariable=self.avatar_label,style='Info.TLabel').pack(anchor='w',pady=(4,0))
        self.use_avatar=tk.BooleanVar(value=True)
        self.check(avatar_controls,'Gespeicherten Avatar für alle Szenen verwenden',self.use_avatar)
        self.localized(ttk.Label,body,text='Der Avatar bleibt lokal gespeichert. Ist er aktiv, hat er bei jeder KI-Szene Vorrang vor anderen Motivbildern. Sein Aussehen kann zwischen Szenen variieren.',
                       style='Info.TLabel',wraplength=720).pack(anchor='w',pady=(4,0))
        self.refresh_avatar()
        label('Foto- und Videoreferenzen')
        row=ttk.Frame(body); row.pack(fill='x')
        self.button(row,'Fotos hinzufügen',lambda:self.choose_refs(False)).pack(side='left',padx=(0,8))
        self.button(row,'Video als Referenz',lambda:self.choose_refs(True)).pack(side='left',padx=(0,8))
        self.button(row,'Auswahl entfernen',self.remove_refs).pack(side='left')
        self.ref_time=tk.StringVar(value='0')
        self.localized(ttk.Label,row,text='  Videozeit (s)').pack(side='left',padx=8)
        ref_entry=ttk.Entry(row,textvariable=self.ref_time,width=8); ref_entry.pack(side='left'); self.controls.append(ref_entry)
        self.ref_list=tk.Listbox(body,height=3,selectmode='extended',bg='#252637',fg='white',borderwidth=0,highlightthickness=0)
        self.ref_list.pack(fill='x',pady=8); self.controls.append(self.ref_list)
        main_row=ttk.Frame(body); main_row.pack(fill='x')
        self.button(main_row,'Als Hauptmotiv wählen',self.main_reference).pack(side='left',pady=3)
        self.story=StoryEditor(self,body)
        self.localized(ttk.Label,body,text='Pro Video wird ein Einzelbild zur gewählten Zeit übernommen. Im festen Modus zählt die erste Referenz, sonst wechseln die Referenzen je Szene.',style='Info.TLabel',wraplength=1000).pack(anchor='w')
        label('Realismus / Rechenaufwand')
        scale=tk.Scale(body,from_=1,to=10,orient='horizontal',variable=self.level,command=lambda v:self.describe(),bg='#191b29',fg='white',highlightthickness=0,troughcolor='#34314c',activebackground='#b986ff')
        scale.pack(fill='x'); self.controls.append(scale)
        self.resident=tk.BooleanVar(value=False)
        self.check(body,'Diffusionsgewichte dauerhaft im VRAM halten (Vergleichsprofil)',self.resident)
        self.resident.trace_add('write',lambda *args:self.describe())
        self.description=self.variable(''); self.localized(ttk.Label,body,textvariable=self.description,wraplength=1000,style='Info.TLabel').pack(anchor='w')
        self.localized(ttk.Label,body,text='Auf der RTX 3080 zuerst Stufe 1 testen. Höhere Profile können die 10 GB Grafikspeicher überschreiten. Einzelne Szenen können sichtbare Schnitte haben.',wraplength=1000,foreground='#ffb86b').pack(anchor='w',pady=8)
        row=ttk.Frame(body); row.pack(fill='x',pady=12)
        self.button(row,'Modelle herunterladen',lambda:self.model_action(False)).pack(side='left',padx=(0,8))
        self.button(row,'Modelle importieren',lambda:self.model_action(True)).pack(side='left',padx=(0,8))
        self.button(row,'NVIDIA prüfen',self.check_hardware).pack(side='left')
        self.localized(ttk.Label,body,text='Modelle werden in deinem Windows-Benutzerordner gespeichert. Jeder Auftrag prüft die vollständigen SHA256-Prüfsummen.',style='Info.TLabel',wraplength=1000).pack(anchor='w')

        footer=ttk.Frame(root,padding=16); footer.pack(fill='x')
        row=ttk.Frame(footer); row.pack(fill='x')
        self.button(row,'2-Sekunden-Qualitätstest',lambda:self.start(True),'Accent.TButton').pack(side='left',padx=(0,8))
        self.button(row,'KI-Video generieren',lambda:self.start(False),'Accent.TButton').pack(side='left',padx=(0,8))
        self.cancel_button=self.localized(ttk.Button,row,text='Anhalten',command=self.cancel); self.cancel_button.pack(side='left',padx=(0,8)); self.cancel_button.state(['disabled'])
        self.button(row,'Auftrag fortsetzen',self.resume).pack(side='left')
        row=ttk.Frame(footer); row.pack(fill='x',pady=8)
        self.localized(ttk.Button,row,text='Szenenordner / Protokolle',command=self.open_job).pack(side='left',padx=(0,8))
        self.localized(ttk.Button,row,text='KI-Vorschau öffnen',command=self.open_output).pack(side='left',padx=(0,8))
        self.localized(ttk.Button,row,text='Projekte / Bildvergleich',command=self.browse).pack(side='left',padx=(0,8))
        self.localized(ttk.Button,row,text='Messbericht',command=self.report).pack(side='left')
        self.status=self.variable('Bereit. Zuerst Modelle laden oder importieren, dann den kurzen Qualitätstest starten.')
        self.localized(ttk.Label,footer,textvariable=self.status,wraplength=1040).pack(anchor='w',pady=6)
        self.metrics=self.variable('Messwerte erscheinen während eines KI-Auftrags. Restzeit gilt nur für die aktuelle KI-Berechnung.')
        self.localized(ttk.Label,footer,textvariable=self.metrics,wraplength=1040,style='Info.TLabel').pack(anchor='w',pady=3)
        self.progress=ttk.Progressbar(footer,mode='indeterminate'); self.progress.pack(fill='x')
        self.describe(); self.update_language_buttons(); root.after(100,self.poll); root.protocol('WM_DELETE_WINDOW',self.close)

    def localized(self, factory, *args, **kwargs):
        source=kwargs.get('text')
        if source is not None: kwargs['text']=self.language.render(source)
        widget=factory(*args,**kwargs)
        if source is not None: self.bindings.bind(lambda text:widget.configure(text=text) if widget.winfo_exists() else None,source)
        return widget

    def variable(self, source):
        variable=tk.StringVar()
        self.text_variables[str(variable)]=self.bindings.bind(variable.set,source)
        return variable

    def set_text(self, variable, source):
        self.text_variables[str(variable)].set(source)

    def update_language_buttons(self):
        for code,button in self.language_buttons.items():
            button.configure(style='Accent.TButton' if code==self.language.code else 'TButton')

    def set_language(self, code):
        error=None
        try: self.language.select(code)
        except OSError as e: error=e
        self.bindings.refresh(); self.update_language_buttons(); self.refresh_references()
        for view in self.views:
            if view.top.winfo_exists(): view.relocalize()
        if error:
            messagebox.showerror('AVEN',self.language.render(message('Sprache konnte nicht gespeichert werden: {detail}',detail=str(error))),parent=self.root)

    def refresh_references(self):
        selected=self.ref_list.curselection(); state=self.ref_list.cget('state'); position=self.ref_list.yview()
        self.ref_list.configure(state='normal'); self.ref_list.delete(0,'end')
        for path,seconds in self.references:
            is_video=path.suffix.lower() in {'.mp4','.mov','.mkv','.avi','.webm','.m4v'}
            caption=message('{name} · Video bei {seconds:g} s',name=path.name,seconds=seconds) if is_video else path.name
            self.ref_list.insert('end',self.language.render(caption))
        for index in selected: self.ref_list.selection_set(index)
        if position: self.ref_list.yview_moveto(position[0])
        self.ref_list.configure(state=state)

    def button(self,parent,text,command,style='TButton'):
        b=self.localized(ttk.Button,parent,text=text,command=command,style=style); self.controls.append(b); return b

    def check(self,parent,text,var):
        b=self.localized(ttk.Checkbutton,parent,text=text,variable=var); b.pack(anchor='w'); self.controls.append(b)

    def describe(self):
        if not hasattr(self,'resident') or not hasattr(self,'description'): return
        try:
            p=Plan.make(self.level.get(),self.format.get(),memory_mode='resident' if self.resident.get() else 'balanced',vram_mb=(self.hardware_info or {}).get('vram_mb',10240))
            self.set_text(self.hardware,message('RTX-Speicherprofil: {mode} · verwaltetes CUDA-Budget {budget:g} GiB · 2 GiB Reserve eingeplant. Kein harter VRAM-Grenzwert.',mode=message('Gewichte im VRAM' if p.memory_mode=='resident' else 'Gewichte im Arbeitsspeicher'),budget=p.vram_gb))
            self.set_text(self.description,message('Stufe {level}/10 · {width}×{height} · {steps} Schritte · 33 Originalbilder · 16 FPS · {tier} · CUDA0 + CPU',level=p.level,width=p.width,height=p.height,steps=p.steps,tier='Q8 + UMT5 Q5' if p.level>=8 else 'Q4 + UMT5 Q3'))
        except (ValueError,tk.TclError): pass

    def work(self, operation):
        if self.busy: return
        self.busy=True; self.token=Cancellation(); token=self.token
        for widget in self.controls: widget.configure(state='disabled')
        self.cancel_button.state(['!disabled']); self.progress.configure(mode='indeterminate'); self.progress.start(15)
        self.set_text(self.metrics,'Messwerte erscheinen während eines KI-Auftrags. Restzeit gilt nur für die aktuelle KI-Berechnung.')
        def log(text): self.events.put(('log',token,text))
        def worker():
            try: result=operation(token,log); self.events.put(('done',token,result))
            except Exception as e: self.events.put(('error',token,e))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        while not self.events.empty():
            kind,token,value=self.events.get()
            if token is not self.token: continue
            if kind=='log': self.set_text(self.status,value)
            elif kind=='metrics':
                self.set_text(self.metrics,status_text(value))
                self.progress.stop()
                if value['stage']=='sampling': self.progress.configure(mode='determinate',maximum=value['steps'],value=value['step'])
                else: self.progress.configure(mode='indeterminate'); self.progress.start(15)
            elif kind=='hardware': self.hardware_info=value; self.describe()
            elif kind=='job': self.job=value; self.output=None
            elif kind=='audio' and not token.event.is_set(): self.audio,self.audio_seconds=value; self.set_text(self.audio_label,message('Musik: {name} · {seconds:.3f} Sekunden',name=self.audio.name,seconds=self.audio_seconds))
            elif kind=='avatar': self.use_avatar.set(True); self.refresh_avatar()
            elif kind in ('done','error'):
                self.busy=False; self.progress.stop(); self.cancel_button.state(['disabled'])
                for widget in self.controls:
                    widget.configure(state='readonly' if isinstance(widget,ttk.Combobox) else 'normal')
                if token.event.is_set() or isinstance(value,Cancelled): self.set_text(self.status,'Angehalten. Fertige Szenen sind gespeichert.')
                elif kind=='error':
                    self.set_text(self.status,value)
                    if not self.closing: messagebox.showerror('AVEN',self.language.render(value),parent=self.root)
                elif isinstance(value,Path):
                    self.output=value; self.set_text(self.status,'KI-Vorschau erstellt. Originalbilder und Motivqualität bitte prüfen.')
                    if self.testing and not self.closing: self.browse(); show_report(self,self.job)
                elif isinstance(value,str): self.set_text(self.status,value)
                self.testing=False
                if self.closing: self.root.destroy(); return
        self.root.after(100,self.poll)

    def cancel(self): self.token.cancel(); self.set_text(self.status,'Anhalten angefordert …')

    def close(self):
        if self.busy:
            if not messagebox.askyesno('AVEN',self.language.render('Laufenden Vorgang anhalten und danach die App schließen?'),parent=self.root): return
            self.closing=True; self.cancel()
        else: self.root.destroy()

    def choose_audio(self):
        source=filedialog.askopenfilename(title=self.language.render('Musik auswählen'),filetypes=[(self.language.render('Musik'),'*.mp3 *.wav *.m4a *.aac *.flac *.ogg'),(self.language.render('Alle Dateien'),'*.*')])
        if not source: return
        def operation(c,log):
            log('Musikdauer wird vollständig geprüft …'); length=audio_duration(Path(source),c)
            c.check(); self.events.put(('audio',c,(Path(source),length))); return 'Musik importiert.'
        self.work(operation)

    def remove_audio(self): self.audio=None; self.audio_seconds=None; self.set_text(self.audio_label,'Keine Musik ausgewählt')

    def choose_source_video(self):
        source=filedialog.askopenfilename(title=self.language.render('Clip auswählen'),filetypes=[
            (self.language.render('Videos'),'*.mp4 *.mov *.mkv *.avi *.webm *.m4v'),
            (self.language.render('Alle Dateien'),'*.*')])
        if source: self.set_source_video(Path(source))

    def set_source_video(self, source):
        if source:
            if self.source_video is None and self.seconds.get()=='30': self.seconds.set('2')
            if self.prompt.get('1.0','end').strip()==DEFAULT_PROMPT: self.prompt.delete('1.0','end')
            self.set_text(self.source_label,message('Clip zur Fortsetzung: {name}',name=source.name))
        else:
            self.set_text(self.source_label,'Kein Clip zur Fortsetzung ausgewählt')
        self.source_video=source
        self.set_text(self.duration_label,'Zusätzliche Länge (Sekunden)' if source else 'Eigene Länge (Sekunden)')
        self.set_text(self.match_label,'Fortsetzung automatisch an die gesamte Musik anpassen' if source else
                      'Videolänge automatisch an die gesamte Musik anpassen')

    def choose_avatar(self):
        source=filedialog.askopenfilename(title=self.language.render('Avatarbild auswählen'),filetypes=[
            (self.language.render('Fotos'),'*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff'),
            (self.language.render('Alle Dateien'),'*.*')])
        if not source: return
        def operation(cancel,log):
            try: save_avatar(source,self.avatar_path,cancel)
            except (OSError,ValueError) as e:
                raise ValueError(message('Avatarbild konnte nicht gespeichert werden: {detail}',detail=str(e))) from e
            self.events.put(('avatar',cancel,None))
            return 'Avatar gespeichert.'
        self.work(operation)

    def remove_avatar(self):
        try: self.avatar_path.unlink(missing_ok=True)
        except OSError as e:
            messagebox.showerror('AVEN',self.language.render(message('Avatar konnte nicht entfernt werden: {detail}',detail=str(e))),parent=self.root)
            return
        self.refresh_avatar()

    def refresh_avatar(self):
        self.avatar_photo=None
        caption='Kein Avatar gespeichert'
        if self.avatar_path.is_file():
            try:
                with Image.open(self.avatar_path) as image:
                    image.thumbnail((60,60),Image.Resampling.LANCZOS)
                    self.avatar_photo=ImageTk.PhotoImage(image,master=self.avatar_preview)
                caption='Avatar gespeichert.'
            except OSError:
                caption='Gespeichertes Avatarbild ist nicht lesbar. Bitte erneut auswählen.'
        self.avatar_preview.configure(image=self.avatar_photo or '')
        self.set_text(self.avatar_label,caption)

    def choose_refs(self, video):
        try: seconds=float(self.ref_time.get()) if video else 0
        except ValueError: messagebox.showerror('AVEN',self.language.render('Bitte eine gültige Referenzzeit eingeben.')); return
        sources=filedialog.askopenfilenames(title=self.language.render('Referenzen auswählen'),filetypes=[(self.language.render('Videos' if video else 'Fotos'),'*.mp4 *.mov *.mkv *.avi *.webm *.m4v' if video else '*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff'),(self.language.render('Alle Dateien'),'*.*')])
        for source in sources:
            self.references.append((Path(source),seconds))
        self.refresh_references()

    def remove_refs(self):
        for i in reversed(self.ref_list.curselection()): self.ref_list.delete(i); self.references.pop(i)

    def main_reference(self):
        selected=self.ref_list.curselection()
        if selected:
            reference=self.references.pop(selected[0]); self.references.insert(0,reference)
            self.refresh_references(); self.ref_list.selection_clear(0,'end'); self.ref_list.selection_set(0)

    def model_action(self, importing):
        source=filedialog.askdirectory(title=self.language.render('Ordner mit vorhandenen AVEN-Modellen')) if importing else None
        if importing and not source: return
        level=self.level.get()
        def operation(c,log):
            ensure_models(self.models,level,c,log,import_from=source,allow_download=not importing)
            return 'Modelle vollständig geprüft. Jetzt den 2-Sekunden-Qualitätstest starten.'
        self.work(operation)

    def check_hardware(self):
        def operation(c,log):
            info=nvidia_info(); self.events.put(('hardware',c,info)); return message('{name} · {memory} MB Grafikspeicher · NVIDIA-Treiber {driver}',name=info['name'],memory=info['vram_mb'],driver=info['driver'])
        self.work(operation)

    def start(self, smoke):
        if self.busy: return
        try:
            level=1 if smoke else self.level.get(); fmt='16:9' if smoke else self.format.get()
            mode='resident' if self.resident.get() else 'balanced'
            prompt=SMOKE_PROMPT if smoke else self.prompt.get('1.0','end').strip()
            negative=NEGATIVE if smoke else self.negative.get('1.0','end').strip()
            seed=42 if smoke else int(self.seed.get())
            seconds=2 if smoke else target_duration(self.seconds.get(),self.audio_seconds,self.match.get() and self.audio is not None)
            story=None if smoke else self.story.value(seconds)
            refs=[] if smoke else list(self.references); sound=None if smoke else self.audio
            source=None if smoke else self.source_video
            avatar=self.avatar_path if not smoke and self.use_avatar.get() and self.avatar_path.is_file() else None
            # Validate input before opening a worker / allocating a saved job.
            from .policy import engine_arguments
            engine_arguments(Plan.make(level,fmt),prompt,negative,seed,['m','t','v'],Path('.'))
            def operation(c,log):
                info=nvidia_info(); c.check(); self.events.put(('hardware',c,info))
                plan=Plan.make(level,fmt,memory_mode=mode,vram_mb=info['vram_mb'])
                log('Clip und Referenzen werden vorbereitet …' if source else 'Referenzen und Musik werden im Auftrag gesichert …')
                job=create_job(self.jobs,plan,prompt,negative,seed,seconds,refs,sound,c,story=story,
                               source_video=source,avatar=avatar)
                self.events.put(('job',c,job))
                return generate(job,self.models,c,log,telemetry=lambda event:self.events.put(('metrics',c,event)))
            self.testing=smoke; self.work(operation)
        except (ValueError,tk.TclError) as e:
            messagebox.showerror(self.language.render('Eingabe prüfen'),self.language.render(e) if str(e) in ENGLISH or hasattr(e,'args') and e.args and hasattr(e.args[0],'source') else self.language.render('Bitte gültige Zahlen für Länge und Seed eingeben.'),parent=self.root)

    def resume(self):
        source=filedialog.askopenfilename(title=self.language.render('Gespeicherten Auftrag wählen'),initialdir=str(self.jobs),filetypes=[(self.language.render('AVEN-Auftrag'),'job.json')])
        if not source: return
        self.resume_job(Path(source).parent)

    def resume_job(self,job):
        def operation(c,log):
            load_job(job,c); self.events.put(('job',c,job))
            return generate(job,self.models,c,log,telemetry=lambda event:self.events.put(('metrics',c,event)))
        self.testing=False; self.work(operation)

    def browse(self):
        self.views=[v for v in self.views if v.top.winfo_exists()]
        view=ProjectBrowser(self); self.views.append(view); return view

    def report(self):
        if self.job: show_report(self,self.job)
        else: messagebox.showinfo('AVEN',self.language.render('Noch kein Messbericht vorhanden. Zuerst den Qualitätstest ausführen.'),parent=self.root)

    def open_path(self,path):
        if not path or not Path(path).exists(): messagebox.showinfo('AVEN',self.language.render('Noch keine entsprechende Ausgabe vorhanden.')); return
        if os.name=='nt': os.startfile(str(path))
        else: subprocess.Popen(['open' if sys.platform=='darwin' else 'xdg-open',str(path)])
    def open_job(self): self.open_path(self.job or self.jobs)
    def open_output(self): self.open_path(self.output)
