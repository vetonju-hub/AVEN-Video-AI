import json
import math
import os
from pathlib import Path
import re
import struct
import uuid
import zlib
from fractions import Fraction
from PIL import Image, ImageOps, ImageStat
from .runtime import Cancellation, binary, run
from .policy import duration


def probe(path, cancel=None):
    return json.loads(run([binary('ffprobe'),'-v','error','-count_frames','-show_streams','-show_format','-of','json',path],cancel,timeout=300))


def audio_duration(path, cancel=None):
    data=probe(path,cancel)
    audio=[s for s in data['streams'] if s['codec_type']=='audio']
    if not audio: raise ValueError('Die Datei enthält keine lesbare Audiospur.')
    # Decode the selected audio stream. Header/bitrate duration estimates can
    # be wrong by seconds for VBR MP3 without a Xing header.
    stats=run([binary('ffmpeg'),'-v','info','-nostats','-i',path,'-map','0:a:0',
               '-vn','-af','astats=measure_perchannel=none:measure_overall=Number_of_samples',
               '-f','null','-'],cancel)
    samples=re.findall(r'Number of samples:\s*(\d+)',stats)
    seconds=int(samples[-1])/int(audio[0]['sample_rate']) if samples else float('nan')
    return duration(seconds,None,False)


def png_integrity(path):
    with Path(path).open('rb') as f:
        if f.read(8)!=b'\x89PNG\r\n\x1a\n': raise ValueError('Ungültige PNG-Signatur.')
        first=True; data_seen=False
        while True:
            header=f.read(8)
            if len(header)!=8: raise ValueError('Abgeschnittenes PNG ohne IEND.')
            size,kind=struct.unpack('>I4s',header)
            if size>64*1024*1024: raise ValueError('Ungültige PNG-Chunkgröße.')
            data=f.read(size); checksum=f.read(4)
            if len(data)!=size or len(checksum)!=4 or struct.unpack('>I',checksum)[0] != zlib.crc32(kind+data):
                raise ValueError('PNG-Chunks oder Prüfsumme beschädigt.')
            if first and (kind!=b'IHDR' or size!=13): raise ValueError('PNG-Header fehlt.')
            first=False
            if kind==b'IDAT': data_seen=True
            if kind==b'IEND':
                if size or not data_seen or f.read(1): raise ValueError('Ungültiges PNG-Ende.')
                return


def inspect_frames(frames, width, height, cancel):
    differences=[]; previous=None; minimum=255.
    for path in frames:
        cancel.check(); png_integrity(path)
        with Image.open(path) as im:
            im.load()
            if im.size!=(width,height): raise ValueError('Ein KI-Bild hat die falsche Größe.')
            small=im.convert('L').resize((64,64))
            deviation=ImageStat.Stat(small).stddev[0]; minimum=min(minimum,deviation)
            if deviation<1: raise ValueError('Fast einfarbige KI-Ausgabe. Originalbilder und engine.log prüfen.')
            current=list(small.tobytes())
            if previous: differences.append(sum(abs(a-b) for a,b in zip(current,previous))/len(current))
            previous=current
    if not frames: raise ValueError('Keine Originalbilder vorhanden.')
    return {'count':len(frames),'minimum_luma_stddev':minimum,
            'mean_temporal_difference':sum(differences)/max(1,len(differences)),
            'note':'Technische Prüfung, kein Nachweis für erkennbare Motive oder Fotorealismus.'}


def import_reference(source, output, seconds, cancel):
    cancel.check()
    if not math.isfinite(seconds) or seconds<0: raise ValueError('Referenzzeit muss eine positive Sekundenzahl sein.')
    if Path(source).suffix.lower() in {'.mp4','.mov','.mkv','.avi','.webm','.m4v'}:
        data=probe(source,cancel)
        if not any(s['codec_type']=='video' for s in data['streams']): raise ValueError('Keine Videospur vorhanden.')
        if seconds>=float(data['format']['duration']): raise ValueError('Referenzzeit liegt hinter dem Videoende.')
        run([binary('ffmpeg'),'-v','error','-y','-i',source,'-ss',str(seconds),'-frames:v','1','-update','1',output],cancel,timeout=300)
    else:
        with Image.open(source) as im:
            im=ImageOps.exif_transpose(im).convert('RGB'); im.thumbnail((1920,1920))
            cancel.check(); im.save(output,format='PNG')
    png_integrity(output)


def validate_clip(path, expected, cancel=None, frames=None, size=None, fps=None):
    data=probe(path,cancel)
    video=next((s for s in data['streams'] if s['codec_type']=='video'),None)
    if video is None or abs(float(video.get('duration','nan'))-expected)>.004 or not math.isfinite(float(video.get('duration','nan'))):
        raise ValueError('MP4 ist unvollständig oder hat eine falsche Dauer.')
    if frames is not None and int(video.get('nb_read_frames',-1))!=frames: raise ValueError('MP4 enthält nicht alle Originalbilder.')
    if size is not None and (video.get('width'),video.get('height'))!=tuple(size): raise ValueError('MP4 hat eine falsche Auflösung.')
    if video.get('codec_name')!='h264': raise ValueError('MP4 enthält nicht den erwarteten H.264-Videocodec.')
    if fps is not None:
        try: actual=float(Fraction(video.get('avg_frame_rate','0/1')))
        except (ValueError,ZeroDivisionError): raise ValueError('MP4-Bildrate ist ungültig.')
        if abs(actual-fps)>.001: raise ValueError('MP4 hat eine falsche Bildrate.')
    return data


def encode_scene(frames, fps, output, cancel):
    cancel.check()
    if fps!=16 or len(frames)!=33: raise ValueError('Ungültige Videobildfolge.')
    from .policy import ordered_frames
    ordered_frames(frames,33)
    with Image.open(frames[0]) as im: w,h=im.size
    inspect_frames(frames,w,h,cancel)
    output=Path(output); tmp=output.with_name('.encode-'+uuid.uuid4().hex+'.mp4')
    try:
        run([binary('ffmpeg'),'-v','error','-y','-framerate',str(fps),'-start_number','0',
             '-i',Path(frames[0]).parent/'generated_%03d.png','-frames:v',str(len(frames)),
             '-c:v','libx264','-preset','medium','-crf','17','-bf','0','-pix_fmt','yuv420p',
             '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
             '-video_track_timescale','48000','-movflags','+faststart',tmp],cancel)
        validate_clip(tmp,len(frames)/fps,cancel,len(frames),(w,h),fps)
        cancel.publish(lambda:os.replace(tmp,output))
    finally: tmp.unlink(missing_ok=True)


def combine(clips, output, seconds, soundtrack, cancel):
    duration(seconds,None,False); cancel.check()
    total=0
    for clip in clips:
        data=probe(clip,cancel)
        video=next(s for s in data['streams'] if s['codec_type']=='video')
        total+=float(video['duration'])
    if total+1e-5<seconds: raise ValueError('Die fertigen Szenen decken die gewünschte Videolänge nicht ab.')
    output=Path(output); token=uuid.uuid4().hex
    listing=output.with_name('.concat-'+token+'.txt'); tmp=output.with_name('.combine-'+token+'.mp4')
    def quote(path): return "'"+Path(path).resolve().as_posix().replace("'","'\\''")+"'"
    listing.write_text(''.join('file '+quote(c)+'\n' for c in clips),encoding='utf-8')
    try:
        args=[binary('ffmpeg'),'-v','error','-y','-f','concat','-safe','0','-i',listing]
        if soundtrack:
            audio_duration(soundtrack,cancel); args+=['-i',soundtrack,'-map','0:v:0','-map','1:a:0','-c:a','aac','-b:a','192k']
        else: args+=['-map','0:v:0','-an']
        # Scenes have no B frames. Clamp the last packet's duration to the exact
        # fractional target, rather than rounding the song end to a full frame.
        args+=['-c:v','copy','-bsf:v',f"setts=duration='min(DURATION,max(1,{seconds:.9f}/TB-PTS))'",
               '-t',f'{seconds:.9f}','-video_track_timescale','48000','-movflags','+faststart',tmp]
        run(args,cancel)
        validate_clip(tmp,seconds,cancel)
        cancel.publish(lambda:os.replace(tmp,output))
    finally:
        tmp.unlink(missing_ok=True); listing.unlink(missing_ok=True)
