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
from .policy import CONTINUATION_FRAMES, duration


BT709_TAGS = 'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709'
H264_OUTPUT = ('-c:v','libx264','-preset','medium','-crf','17','-bf','0','-pix_fmt','yuv420p',
               '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
               '-video_track_timescale','48000','-movflags','+faststart')


def probe(path, cancel=None, *, count_frames=True):
    args=[binary('ffprobe'),'-v','error']
    if count_frames: args+=['-count_frames']
    return json.loads(run([*args,'-show_streams','-show_format','-of','json',path],cancel,timeout=300))


def video_duration(path, cancel):
    streams=probe(path,cancel,count_frames=False)['streams']
    video=next((s for s in streams if s['codec_type']=='video'),None)
    if not video: raise ValueError('Keine Videospur vorhanden.')
    return duration(float(video.get('duration','nan')),None,False)


def prepare_source_video(source, output, audio, plan, cancel):
    """Transcode the prefix once, with the same size, frame rate and time base as the AI scenes."""
    streams=probe(source,cancel,count_frames=False)['streams']
    video=next((s for s in streams if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')),None)
    if not video:
        raise ValueError('Keine Videospur vorhanden.')
    has_audio=any(s['codec_type']=='audio' for s in streams)
    width,height=plan.width,plan.height
    # Use display aspect ratio, including non-square source pixels. FFmpeg applies rotation before scaling.
    fit=(f"scale=w='max(2,trunc(min({width},{height}*dar)/2)*2)':"
         f"h='max(2,trunc(min({height},{width}/dar)/2)*2)':out_color_matrix=bt709,setsar=1,"
         f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2')
    filters=f'fps={plan.fps}:start_time=0:eof_action=pass,'
    if video.get('color_transfer') in ('smpte2084','arib-std-b67'):
        defaults=[]
        unspecified=(None,'unknown','unspecified','reserved')
        if video.get('color_primaries') in unspecified: defaults.append('color_primaries=bt2020')
        if video.get('color_space') in unspecified: defaults.append('colorspace=bt2020nc')
        if defaults: filters+='setparams='+':'.join(defaults)+','
        filters+=('zscale=transfer=linear:npl=100,format=gbrpf32le,zscale=primaries=bt709,'
                  'tonemap=tonemap=mobius,zscale=transfer=bt709:matrix=bt709:range=limited,')
    args=[binary('ffmpeg'),'-v','error','-xerror','-y','-filter_threads','2','-i',source,
          '-map','0:V:0','-an','-map_metadata','-1',
          '-vf',filters+fit+',format=yuv420p,'+BT709_TAGS,*H264_OUTPUT,output]
    if has_audio:
        args+=['-map','0:a:0','-vn','-map_metadata','-1','-af','aresample=48000:async=1:first_pts=0',
               '-c:a','flac','-ac','2',audio]
    run(args,cancel)
    return has_audio


def write_control_video(clip, folder, fps, cancel):
    """Write the chronological tail of a normalized clip for Wan VACE."""
    length=video_duration(clip,cancel)
    count=min(CONTINUATION_FRAMES,round(length*fps))
    if count<1: raise ValueError('Keine Videospur vorhanden.')
    folder.mkdir()
    args=[binary('ffmpeg'),'-v','error','-xerror','-ss',f'{max(0,length-count/fps):.6f}',
          '-i',clip,'-map','0:v:0']
    if count<CONTINUATION_FRAMES:
        args+=['-vf',f'tpad=start={CONTINUATION_FRAMES-count}:start_mode=clone']
    run([*args,'-frames:v',str(CONTINUATION_FRAMES),'-start_number','0','-pix_fmt','rgb24',
         folder/'frame_%03d.png'],cancel)
    for index in range(CONTINUATION_FRAMES):
        cancel.check(); png_integrity(folder/f'frame_{index:03}.png')


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
        save_image_reference(source,output,cancel)
    png_integrity(output)


def save_image_reference(source, output, cancel):
    with Image.open(source) as im:
        im=ImageOps.exif_transpose(im).convert('RGB'); im.thumbnail((1920,1920))
        cancel.check(); im.save(output,format='PNG')


def save_avatar(source, output, cancel):
    output=Path(output); temp=output.with_name('.avatar-'+uuid.uuid4().hex+'.png')
    try:
        save_image_reference(source,temp,cancel)
        cancel.publish(lambda:os.replace(temp,output))
    finally: temp.unlink(missing_ok=True)


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
             '-vf','scale=out_color_matrix=bt709,format=yuv420p,'+BT709_TAGS,
             *H264_OUTPUT,tmp],cancel)
        validate_clip(tmp,len(frames)/fps,cancel,len(frames),(w,h),fps)
        cancel.publish(lambda:os.replace(tmp,output))
    finally: tmp.unlink(missing_ok=True)


def combine(clips, output, seconds, soundtrack, cancel, *, source_video=None, source_audio=None):
    duration(seconds,None,False); cancel.check()
    total=sum(video_duration(clip,cancel) for clip in clips)
    if total+1e-5<seconds: raise ValueError('Die fertigen Szenen decken die gewünschte Videolänge nicht ab.')
    prefix_seconds=video_duration(source_video,cancel) if source_video else 0
    full_seconds=duration(prefix_seconds+seconds,None,False)
    if source_video: clips=[source_video,*clips]
    output=Path(output); token=uuid.uuid4().hex
    listing=output.with_name('.concat-'+token+'.txt'); tmp=output.with_name('.combine-'+token+'.mp4')
    def quote(path): return "'"+Path(path).resolve().as_posix().replace("'","'\\''")+"'"
    listing.write_text(''.join('file '+quote(c)+'\n' for c in clips),encoding='utf-8')
    try:
        args=[binary('ffmpeg'),'-v','error','-y','-f','concat','-safe','0','-i',listing]
        if source_video and (source_audio or soundtrack):
            if soundtrack: audio_duration(soundtrack,cancel)
            filters=[]; input_index=1
            for index,(track,length) in enumerate(((source_audio,prefix_seconds),(soundtrack,seconds))):
                if track:
                    args+=['-i',track]
                    audio=f'[{input_index}:a:0]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={length:.9f}'
                    input_index+=1
                else:
                    audio='anullsrc=r=48000:cl=stereo'
                filters.append(f'{audio},atrim=duration={length:.9f},asetpts=N/SR/TB[a{index}]')
            filters.append('[a0][a1]concat=n=2:v=0:a=1[a]')
            args+=['-filter_complex',';'.join(filters),'-map','0:v:0','-map','[a]','-c:a','aac','-b:a','192k']
        elif soundtrack:
            audio_duration(soundtrack,cancel); args+=['-i',soundtrack,'-map','0:v:0','-map','1:a:0','-c:a','aac','-b:a','192k']
        else: args+=['-map','0:v:0','-an']
        # Scenes have no B frames. Clamp the last packet's duration to the exact
        # fractional target, rather than rounding the song end to a full frame.
        args+=['-c:v','copy','-bsf:v',f"setts=duration='min(DURATION,max(1,{full_seconds:.9f}/TB-PTS))'",
               '-t',f'{full_seconds:.9f}','-video_track_timescale','48000','-movflags','+faststart',tmp]
        run(args,cancel)
        validate_clip(tmp,full_seconds,cancel)
        cancel.publish(lambda:os.replace(tmp,output))
    finally:
        tmp.unlink(missing_ok=True); listing.unlink(missing_ok=True)
