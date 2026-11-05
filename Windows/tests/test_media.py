import math
from pathlib import Path
import tempfile
import unittest
import wave
import struct
from PIL import Image, ImageDraw
from aven.media import (inspect_frames, encode_scene, combine, probe, import_reference, audio_duration,
                        prepare_source_video, write_control_video, save_avatar)
from aven.policy import Plan
from aven.runtime import Cancellation, Cancelled, run, binary


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)/"Müller s' test"
        self.root.mkdir(); self.frames=[]
        for i in range(33):
            im=Image.new('RGB',(64,64),'red'); d=ImageDraw.Draw(im)
            d.rectangle((0,0,63,31),fill='green'); d.rectangle((i%16,40,i%16+15,55),fill='blue')
            p=self.root/f'generated_{i:03}.png'; im.save(p); self.frames.append(p)
        self.clip=self.root/'clip.mp4'

    def tearDown(self): self.tmp.cleanup()

    def test_png_integrity_and_no_blank_success(self):
        report=inspect_frames(self.frames,64,64,Cancellation())
        self.assertEqual(report['count'],33)
        self.frames[5].write_bytes(self.frames[5].read_bytes()[:-12])
        with self.assertRaises(ValueError): inspect_frames(self.frames,64,64,Cancellation())
        Image.new('RGB',(64,64),'black').save(self.frames[5])
        with self.assertRaises(ValueError): inspect_frames(self.frames,64,64,Cancellation())

    def test_actual_video_pixels_count_and_fractional_cut(self):
        encode_scene(self.frames,16,self.clip,Cancellation())
        p=probe(self.clip)
        video=next(s for s in p['streams'] if s['codec_type']=='video')
        self.assertEqual(int(video['nb_read_frames']),33)
        self.assertAlmostEqual(float(video['duration']),2.0625,places=3)
        out=self.root/'fractional.mp4'
        combine([self.clip],out,1.337,None,Cancellation())
        self.assertAlmostEqual(float(probe(out)['format']['duration']),1.337,delta=.004)
        photo=self.root/'reference.png'; import_reference(self.clip,photo,.5,Cancellation())
        with Image.open(photo) as image: im=image.convert('RGB')
        self.assertGreater(im.getpixel((50,10))[1],80)
        self.assertGreater(im.getpixel((50,50))[0],150)

    def test_full_music_and_no_loop(self):
        encode_scene(self.frames,16,self.clip,Cancellation())
        song=self.root/'song.wav'; rate=16000
        with wave.open(str(song),'wb') as f:
            f.setparams((1,2,rate,0,'NONE','not compressed'))
            f.writeframes(b''.join(struct.pack('<h',int(5000*math.sin(i*2*math.pi*440/rate))) for i in range(86000)))
        self.assertAlmostEqual(audio_duration(song),5.375,places=3)
        out=self.root/'music.mp4'
        combine([self.clip]*3,out,5.375,song,Cancellation())
        self.assertAlmostEqual(float(probe(out)['format']['duration']),5.375,delta=.004)
        raw=self.root/'decoded.raw'
        run([binary('ffmpeg'),'-v','error','-y','-i',out,'-vn','-f','f32le','-ac','1','-ar','16000',raw])
        values=struct.unpack('<'+'f'*(raw.stat().st_size//4),raw.read_bytes())
        crossings=sum(a<=0<b for a,b in zip(values[16000:32000],values[16001:32001]))
        self.assertAlmostEqual(crossings,440,delta=8)
        self.assertGreater(sum(x*x for x in values[84000:85000])/1000,.001)
        manual=self.root/'manual.mp4'; combine([self.clip]*3,manual,6,song,Cancellation())
        audio=next(s for s in probe(manual)['streams'] if s['codec_type']=='audio')
        self.assertLess(float(audio['duration']),5.5)
        with self.assertRaises(ValueError): combine([self.clip],self.root/'short.mp4',6,None,Cancellation())

    def test_exif_and_cancel(self):
        source=self.root/'rotated.jpg'; im=Image.new('RGB',(80,40),'red')
        exif=im.getexif(); exif[274]=6; im.save(source,exif=exif)
        out=self.root/'oriented.png'; import_reference(source,out,0,Cancellation())
        with Image.open(out) as image: self.assertEqual(image.size,(40,80))
        c=Cancellation(); c.cancel()
        with self.assertRaises(Cancelled): encode_scene(self.frames,16,self.clip,c)
        self.assertFalse(self.clip.exists())

    def test_vbr_music_without_duration_header(self):
        fixtures=Path(__file__).resolve().parents[2]/'tests/Fixtures'
        expected=float((fixtures/'vbr-duration.txt').read_text())
        self.assertAlmostEqual(audio_duration(fixtures/'vbr-no-xing.mp3'),expected,delta=.04)

    def test_single_frame_portrait_clip_can_supply_four_context_frames(self):
        source=self.root/'portrait.mov'; output=self.root/'source.mp4'; audio=self.root/'source.flac'
        plan=Plan.make(1,'16:9'); cancel=Cancellation()
        run([binary('ffmpeg'),'-v','error','-f','lavfi','-i','color=c=red:s=48x80:r=120',
             '-frames:v','1','-c:v','libx264',source])
        self.assertFalse(prepare_source_video(source,output,audio,plan,cancel))
        self.assertFalse(audio.exists())
        control=self.root/'control'; write_control_video(output,control,plan.fps,cancel)
        frames=sorted(control.glob('*.png'))
        self.assertEqual(len(frames),4)
        for frame in frames:
            with Image.open(frame) as image:
                self.assertEqual(image.size,(plan.width,plan.height))
                self.assertGreater(image.getpixel((plan.width//2,plan.height//2))[0],200)
                self.assertLess(max(image.getpixel((10,10))),20)

    def test_avatar_replacement_is_local_and_atomic(self):
        portrait=self.root/'portrait.png'; avatar=self.root/'avatar.png'
        Image.new('RGB',(30,50),'red').save(portrait)
        save_avatar(portrait,avatar,Cancellation())
        original=avatar.read_bytes()
        Image.new('RGB',(30,50),'blue').save(portrait)
        cancelled=Cancellation(); cancelled.cancel()
        with self.assertRaises(Cancelled): save_avatar(portrait,avatar,cancelled)
        self.assertEqual(avatar.read_bytes(),original)
        save_avatar(portrait,avatar,Cancellation())
        with Image.open(avatar) as image: self.assertEqual(image.getpixel((0,0)),(0,0,255))

    def test_continuation_normalizes_source_colors(self):
        plan=Plan.make(1,'16:9'); cancel=Cancellation()
        fixtures = [
            ('sdr', 'setparams=colorspace=smpte170m', ['-colorspace','smpte170m'], 'color_space', 'smpte170m'),
            ('hdr', 'format=yuv420p10le,setparams=color_trc=smpte2084',
             ['-color_trc','smpte2084','-pix_fmt','yuv420p10le'], 'color_transfer', 'smpte2084'),
        ]
        for mode, color_filter, color_args, color_key, color_value in fixtures:
            with self.subTest(mode=mode):
                source=self.root/f'{mode}.mp4'; output=self.root/f'{mode}-normalized.mp4'
                run([binary('ffmpeg'),'-v','error','-f','lavfi','-i','color=c=red:s=160x90:r=16:d=0.25',
                     '-vf',color_filter,'-c:v','libx264',*color_args,source])
                self.assertEqual(probe(source)['streams'][0].get(color_key), color_value)
                prepare_source_video(source,output,self.root/'source.flac',plan,cancel)
                video=probe(output)['streams'][0]
                self.assertEqual((video['color_space'],video['color_primaries'],video['color_transfer'],video['pix_fmt']),
                                 ('bt709','bt709','bt709','yuv420p'))
                if mode=='sdr':
                    control=self.root/'control'; write_control_video(output,control,plan.fps,cancel)
                    with Image.open(control/'frame_003.png') as image:
                        red,green,blue=image.getpixel((plan.width//2,plan.height//2))
                        self.assertGreater(red,245); self.assertLess(max(green,blue),8)


if __name__=='__main__': unittest.main()
