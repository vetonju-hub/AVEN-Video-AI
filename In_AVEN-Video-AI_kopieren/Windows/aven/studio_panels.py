"""Tk scene editor, original-frame comparison and saved project browser."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from .gallery import list_projects, scene_frames, reference_path, report_caption
from .story import parse_sections, suggested_sections, scene_spec, preview_text
from .runtime import atomic_json
from .telemetry import clock
from .i18n import message


def text_box(parent, height=4):
    return tk.Text(parent,height=height,wrap='word',bg='#252637',fg='white',insertbackground='white',relief='flat',padx=10,pady=8)


class StoryEditor:
    def __init__(self,studio,parent):
        self.studio=studio; loc=studio.localized
        loc(ttk.Label,parent,text='Gemeinsamer Stil und wiederkehrendes Motiv',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(14,6))
        self.style=tk.StringVar(value='Natural lighting, sharp focus, consistent cinematic color palette.')
        self.motif=tk.StringVar(value='')
        for caption,var in [('Gemeinsamer Stil',self.style),('Motiv / Figur (Merkmale, Kleidung, Farben)',self.motif)]:
            loc(ttk.Label,parent,text=caption).pack(anchor='w')
            entry=ttk.Entry(parent,textvariable=var); entry.pack(fill='x',pady=(2,6)); studio.controls.append(entry)
        self.fixed=tk.BooleanVar(value=True)
        studio.check(parent,'Erste Referenz als festes Hauptmotiv für alle Szenen',self.fixed)
        loc(ttk.Label,parent,text='Wiederkehrende Beschreibung und feste Referenz unterstützen den Zusammenhang. Identische Gesichter oder Kleidung sind nicht garantiert.',style='Info.TLabel',wraplength=1000).pack(anchor='w',pady=4)
        loc(ttk.Label,parent,text='Musik-Szenenplan',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(12,6))
        row=ttk.Frame(parent); row.pack(fill='x')
        studio.button(row,'Abschnitte vorschlagen',self.suggest).pack(side='left',padx=(0,8))
        studio.button(row,'Szenenplan prüfen',self.preview).pack(side='left')
        self.sections=text_box(parent,4); self.sections.pack(fill='x',pady=6); studio.controls.append(self.sections)
        loc(ttk.Label,parent,text='Optional: Startsekunde | Abschnitt | Szenenprompt. Vorschläge richten sich nach der Laufzeit, nicht nach erkannten Beats. Änderungen greifen ab dem nächsten KI-Szenenbeginn (ca. 2,06 s). Leer = nur Hauptprompt.',style='Info.TLabel',wraplength=1000).pack(anchor='w')

    def seconds(self):
        from .policy import target_duration
        s=self.studio
        return target_duration(s.seconds.get(),s.audio_seconds,s.match.get() and s.audio is not None)

    def value(self,seconds):
        return {'style':self.style.get().strip(),'motif':self.motif.get().strip(),
                'reference_mode':'fixed' if self.fixed.get() else 'alternate',
                'sections':parse_sections(self.sections.get('1.0','end'),seconds)}

    def suggest(self):
        try:
            rows=suggested_sections(self.seconds())
            if self.sections.get('1.0','end').strip() and not messagebox.askyesno('AVEN',self.studio.language.render('Vorhandenen Szenenplan durch Vorschläge ersetzen?'),parent=self.studio.root): return
            self.sections.delete('1.0','end')
            self.sections.insert('1.0','\n'.join(f"{r['start']:g} | {r['title']} | {r['prompt']}" for r in rows))
        except (ValueError,tk.TclError) as e: messagebox.showerror('AVEN',self.studio.language.render(e),parent=self.studio.root)

    def preview(self):
        from .policy import Plan
        try:
            seconds=self.seconds(); story=self.value(seconds); s=self.studio
            data={'plan':Plan.make(s.level.get(),s.format.get()).__dict__,'prompt':s.prompt.get('1.0','end').strip(),
                  'seconds':seconds,'references':list(s.references),'story':story}
            # Display representative scene beginnings for each section, bounded for long songs.
            import math
            indices={0}
            for row in story['sections']: indices.add(math.ceil(row['start']/(33/16)))
            lines=[]
            for index in sorted(indices):
                if index*33/16>=seconds: continue
                spec=scene_spec(data,index)
                lines.append((index+1,spec))
            show_text(s,'Szenenplan prüfen',preview_text(lines))
        except (ValueError,tk.TclError) as e: messagebox.showerror('AVEN',self.studio.language.render(e),parent=self.studio.root)


def show_text(studio,title,text):
    top=tk.Toplevel(studio.root); studio.bindings.bind(lambda v:top.title(v) if top.winfo_exists() else None,title)
    top.geometry('850x530')
    field=text_box(top,20); field.pack(fill='both',expand=True,padx=12,pady=12)
    def update(value):
        if field.winfo_exists():
            field.configure(state='normal'); field.delete('1.0','end'); field.insert('1.0',value); field.configure(state='disabled')
    studio.bindings.bind(update,text)
    return top


class FramePane:
    def __init__(self,studio,parent,title):
        self.studio=studio; self.job=None; self.path=None; self.photo=None
        self.frame=studio.localized(ttk.LabelFrame,parent,text=title,padding=8)
        self.frame.pack(side='left',fill='both',expand=True,padx=4)
        self.caption=studio.variable('Noch keine Originalbilder vorhanden.')
        studio.localized(ttk.Label,self.frame,textvariable=self.caption,wraplength=460).pack(anchor='w')
        self.image=ttk.Label(self.frame,anchor='center'); self.image.pack(fill='both',expand=True)
        self.scene=tk.IntVar(value=1); self.index=tk.IntVar(value=0); self.reference=tk.BooleanVar(value=False)
        row=ttk.Frame(self.frame); row.pack(fill='x')
        studio.localized(ttk.Label,row,text='Szene').pack(side='left')
        self.scene_picker=ttk.Spinbox(row,from_=1,to=1,textvariable=self.scene,width=7,command=self.reset_frame)
        self.scene_picker.pack(side='left',padx=5); self.scene_picker.bind('<Return>',lambda e:self.reset_frame())
        studio.localized(ttk.Checkbutton,row,text='Referenz zeigen',variable=self.reference,command=self.render).pack(side='left')
        self.slider=tk.Scale(self.frame,from_=0,to=32,orient='horizontal',variable=self.index,command=lambda v:self.render(),bg='#191b29',fg='white',highlightthickness=0)
        self.slider.pack(fill='x')
        studio.localized(ttk.Button,self.frame,text='Originalgröße (100 %)',command=self.native).pack(anchor='w')

    def set_job(self,job):
        self.job=job; self.scene.set(1); self.index.set(0)
        self.scene_picker.configure(to=max(1,job['total']))
        self.render()

    def reset_frame(self): self.index.set(0); self.render()

    def render(self):
        if not self.job: return
        self.path=None
        try:
            number=self.scene.get(); index=self.index.get()
            if self.reference.get():
                spec=scene_spec(self.job['data'],number-1)
                path=reference_path(self.job['folder'],self.job['data'],spec['reference'],scene=number)
            else:
                files=scene_frames(self.job['folder'],number)
                path=next((p for p in files if p.name==f'generated_{index:03}.png'),None)
            if path is None:
                self.image.configure(image=''); self.photo=None
                self.studio.set_text(self.caption,'Noch keine Originalbilder vorhanden.'); return
            with Image.open(path) as source:
                source.load(); dimensions=source.size
                image=source.convert('RGB'); image.thumbnail((460,270),Image.Resampling.LANCZOS)
            self.path=path; self.photo=ImageTk.PhotoImage(image,master=self.image)
            self.image.configure(image=self.photo)
            self.studio.set_text(self.caption,message('{job} · {width}×{height} · {file}',job=self.job['name'],width=dimensions[0],height=dimensions[1],file=path.name))
        except (OSError,ValueError,KeyError,TypeError,tk.TclError) as e:
            self.image.configure(image=''); self.photo=None
            self.studio.set_text(self.caption,message('Bild nicht lesbar: {detail}',detail=str(e)))

    def native(self):
        if not self.path: return
        try:
            top=tk.Toplevel(self.studio.root); top.title(self.path.name+' · 100 %'); top.geometry('1000x720')
            with Image.open(self.path) as source: photo=ImageTk.PhotoImage(source.convert('RGB'),master=top)
            canvas=tk.Canvas(top,bg='#11121c',scrollregion=(0,0,photo.width(),photo.height()))
            x=ttk.Scrollbar(top,orient='horizontal',command=canvas.xview); y=ttk.Scrollbar(top,orient='vertical',command=canvas.yview)
            canvas.configure(xscrollcommand=x.set,yscrollcommand=y.set)
            x.pack(side='bottom',fill='x'); y.pack(side='right',fill='y'); canvas.pack(fill='both',expand=True)
            canvas.create_image(0,0,image=photo,anchor='nw'); canvas.original_photo=photo
        except (OSError,ValueError) as e: messagebox.showerror('AVEN',self.studio.language.render(e),parent=self.studio.root)


class ProjectBrowser:
    def __init__(self,studio):
        self.studio=studio; self.rows={}
        self.top=tk.Toplevel(studio.root); self.top.geometry('1150x780'); self.top.minsize(800,650)
        studio.bindings.bind(lambda v:self.top.title(v) if self.top.winfo_exists() else None,'Projekte und Originalbilder')
        header=ttk.Frame(self.top,padding=10); header.pack(fill='x')
        for i,(title,command) in enumerate([('Aktualisieren',self.refresh),('Als Vergleich B wählen',self.compare),('Ausgewählten Auftrag fortsetzen',self.resume),('Video öffnen',self.open_video),('Messbericht / Qualität bewerten',self.report)]):
            studio.localized(ttk.Button,header,text=title,command=command).grid(row=i//3,column=i%3,sticky='w',padx=3,pady=2)
        self.table=ttk.Treeview(self.top,columns=('prompt','scenes','status'),show='tree headings',height=6,selectmode='browse')
        for key,title,width in [('#0','Projekt',205),('prompt','Szenenbeschreibung',410),('scenes','Szenen',90),('status','Status',170)]:
            self.table.column(key,width=width,minwidth=60)
            studio.bindings.bind(lambda v,key=key:self.table.heading(key,text=v) if self.table.winfo_exists() else None,title)
        self.table.pack(fill='x',padx=12); self.table.bind('<<TreeviewSelect>>',lambda e:self.select())
        studio.localized(ttk.Label,self.top,text='Original-PNGs vergleichen: A und B unabhängig wählen. Die Anzeige ist verkleinert; „Originalgröße“ zeigt echte Pixel. MP4 spielt im Standard-Videoplayer.',wraplength=1080,style='Info.TLabel').pack(anchor='w',padx=12,pady=8)
        frames=ttk.Frame(self.top); frames.pack(fill='both',expand=True,padx=8,pady=8)
        self.a=FramePane(studio,frames,'A · ausgewähltes Projekt')
        self.b=FramePane(studio,frames,'B · Vergleich')
        self.refresh(studio.job)

    def selected(self):
        selected=self.table.selection()
        return self.rows.get(selected[0]) if selected else None

    def refresh(self,preferred=None):
        self.table.delete(*self.table.get_children()); self.rows={}
        for i,row in enumerate(list_projects(self.studio.jobs)):
            key=str(i); self.rows[key]=row
            state='Auftragsdatei prüfen' if not row['valid'] else ('MP4 vorhanden' if row['output_exists'] else 'Noch kein MP4')
            self.table.insert('','end',iid=key,text=row['name'],values=(row['prompt'],f"{row['completed']}/{row['total']}",self.studio.language.render(state)))
            if preferred and row['folder']==preferred: self.table.selection_set(key)
        if not self.table.selection() and self.rows: self.table.selection_set(next(iter(self.rows)))
        self.select()

    def relocalize(self):
        for key,row in self.rows.items():
            state='Auftragsdatei prüfen' if not row['valid'] else ('MP4 vorhanden' if row['output_exists'] else 'Noch kein MP4')
            self.table.set(key,'status',self.studio.language.render(state))

    def select(self):
        row=self.selected()
        if row and row['valid']: self.a.set_job(row)

    def compare(self):
        row=self.selected()
        if row and row['valid']: self.b.set_job(row)

    def resume(self):
        row=self.selected()
        if row and row['valid'] and not self.studio.busy: self.studio.resume_job(row['folder'])

    def open_video(self):
        row=self.selected()
        if row: self.studio.open_path(row['folder']/'AVEN_KI_VORSCHAU.mp4')

    def report(self):
        row=self.selected()
        if row: show_report(self.studio,row['folder'])


def show_report(studio,folder):
    path=Path(folder)/'benchmark.json'
    try:
        if path.stat().st_size>1024*1024: raise ValueError('Messbericht ist ungültig.')
        report=json.loads(path.read_text(encoding='utf-8'))
        caption=report_caption(report)
    except FileNotFoundError:
        messagebox.showinfo('AVEN',studio.language.render('Noch kein Messbericht vorhanden. Zuerst den Qualitätstest ausführen.'),parent=studio.root); return
    except (OSError,ValueError):
        messagebox.showerror('AVEN',studio.language.render('Messbericht ist ungültig.'),parent=studio.root); return
    top=tk.Toplevel(studio.root); top.geometry('860x580')
    studio.bindings.bind(lambda v:top.title(v) if top.winfo_exists() else None,'Messbericht / Qualität bewerten')
    studio.localized(ttk.Label,top,text=caption,wraplength=800,padding=16).pack(anchor='w')
    studio.localized(ttk.Label,top,text='Messwerte sind keine automatische Qualitätsbewertung. Fehlende GPU-Werte bedeuten „nicht gemessen“. Bei Fehlern bleiben Protokolle erhalten.',wraplength=800,padding=16).pack(anchor='w')
    notes=text_box(top,4); notes.pack(fill='x',padx=16,pady=4)
    notes.insert('1.0',report.get('visual_notes','') if isinstance(report.get('visual_notes',''),str) else '')
    def save(choice):
        try:
            from .gallery import save_assessment
            save_assessment(folder,choice,notes.get('1.0','end').strip())
            top.destroy()
        except (ValueError,OSError) as e: messagebox.showerror('AVEN',studio.language.render(e),parent=top)
    row=ttk.Frame(top,padding=16); row.pack(fill='x')
    for caption,choice in [('Motiv und Bewegung gut','accepted'),('Unscharf / falsches Motiv / Bewegung fehlerhaft','needs_work'),('Später prüfen','pending_user_review')]:
        studio.localized(ttk.Button,row,text=caption,command=lambda choice=choice:save(choice)).pack(anchor='w',pady=3)
    studio.localized(ttk.Button,top,text='Berichtdatei öffnen',command=lambda:studio.open_path(path)).pack(anchor='w',padx=16)
    return top
