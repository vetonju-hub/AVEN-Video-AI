"""Editable, deterministic scene sections. Suggestions use time, not music analysis."""
import math
from .policy import Plan, duration
from .i18n import message


def validate_story(story, seconds):
    duration(seconds,None,False)
    error='Szenenplan ungültig. Zeiten müssen bei 0 beginnen, aufsteigen und innerhalb der Videolänge liegen.'
    if not isinstance(story,dict) or story.get('reference_mode') not in ('fixed','alternate'): raise ValueError(error)
    if any(not isinstance(story.get(k),str) or len(story[k])>4000 for k in ('style','motif')): raise ValueError(error)
    rows=story.get('sections')
    if not isinstance(rows,list) or len(rows)>128: raise ValueError(error)
    previous=-1
    for i,row in enumerate(rows):
        if not isinstance(row,dict): raise ValueError(error)
        start=row.get('start')
        if type(start) not in (float,int) or not math.isfinite(start) or not previous<start<seconds or (i==0 and start!=0): raise ValueError(error)
        for key in ('title','prompt'):
            if not isinstance(row.get(key),str) or not row[key].strip() or len(row[key])>4000: raise ValueError(error)
        previous=start
    return story


def parse_sections(text, seconds):
    rows=[]
    for number,line in enumerate(text.splitlines(),1):
        if not line.strip(): continue
        try:
            at,title,prompt=line.split('|',2)
            rows.append({'start':float(at.strip().replace(',','.')),'title':title.strip(),'prompt':prompt.strip()})
        except ValueError as e:
            raise ValueError(message('Szenenplan, Zeile {number}: Startsekunde | Abschnitt | Szenenprompt eingeben.',number=number)) from e
    validate_story({'style':'','motif':'','reference_mode':'fixed','sections':rows},seconds)
    return rows


def suggested_sections(seconds):
    duration(seconds,None,False)
    candidates=[(0,'Intro','A slow wide establishing shot, gentle camera movement.'),
        (.15,'Verse','A medium shot following the subject, calm deliberate motion.'),
        (.4,'Chorus','A closer dynamic shot, expressive motion, keep the same visual style.'),
        (.6,'Verse','A new side angle of the same subject and setting, steady motion.'),
        (.8,'Chorus','Return to the expressive main motif, a smooth tracking camera.'),
        (.93,'Outro','A slow wide closing shot, the camera gently pulls away.')]
    result=[]
    # Section boundaries follow existing 33/16-second scene cuts; no fake beat detection.
    for fraction,title,prompt in candidates:
        start=math.floor(seconds*fraction/(33/16))*(33/16)
        if result and start<=result[-1]['start']: continue
        result.append({'start':start,'title':title,'prompt':prompt})
    return result


def scene_spec(data, index):
    plan=Plan(**data['plan']); start=index*plan.frames/plan.fps
    if type(index) is not int or index<0 or start>=data['seconds']: raise ValueError('Ungültige Szenennummer.')
    story=data.get('story')
    prompt=data['prompt']; title=''; reference=index%len(data['references']) if data['references'] else None
    if story:
        validate_story(story,data['seconds'])
        section=next((row for row in reversed(story['sections']) if row['start']<=start),None)
        parts=[prompt,story['style'],story['motif'],section['prompt'] if section else '']
        prompt='\n'.join(x.strip() for x in parts if x.strip())
        title=section['title'] if section else ''
        if reference is not None and story['reference_mode']=='fixed': reference=0
    return {'start':start,'seconds':min(plan.frames/plan.fps,data['seconds']-start),
            'title':title,'prompt':prompt,'reference':reference}


def preview_text(specs):
    """Keep generated captions translatable while leaving prompt/section content intact."""
    result=''
    for number,spec in specs:
        caption=message('Szene {number} · {time} s · {title}',number=number,time=f"{spec['start']:.3f}",title=spec['title'])
        block=message('{caption}\n{prompt}',caption=caption,prompt=spec['prompt'])
        result=message('{previous}\n\n{next}',previous=result,next=block) if result else block
    return result
