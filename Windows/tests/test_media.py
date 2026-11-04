import math
from pathlib import Path
import tempfile
import unittest
import wave
import struct
from PIL import Image, ImageDraw
from aven.media import inspect_frames, encode_scene, combine, probe, import_reference, audio_duration
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


if __name__=='__main__': unittest.main()
