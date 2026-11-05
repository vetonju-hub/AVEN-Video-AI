from pathlib import Path
import json
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from aven.policy import Plan, ENGINE_TAG
from aven.runtime import Cancellation,Cancelled,binary,run
from aven.jobs import create_job, load_job, generate
from aven.media import encode_scene, probe
from aven.gallery import list_projects, reference_path


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name).resolve()
        self.fake=self.root/'fake.py'
        self.fake.write_text('''import sys
from pathlib import Path
from PIL import Image,ImageDraw
a=sys.argv
w=int(a[a.index('-W')+1]); h=int(a[a.index('-H')+1]); out=a[a.index('-o')+1]
for i in range(int(a[a.index('--video-frames')+1])):
 im=Image.new('RGB',(w,h),'red'); d=ImageDraw.Draw(im); d.rectangle((0,0,w//2,h),fill='green'); d.rectangle((i*2,20,i*2+30,90),fill='blue')
 if '--control-video' in a and i<4: d.rectangle((0,0,w//2,h),fill='yellow')
 im.save(out % i)
''')
        self.plan=Plan.make(1,'16:9')
    def tearDown(self): self.tmp.cleanup()

    def test_end_to_end_and_resume_keeps_completed_scene(self):
        story={'style':'same light','motif':'ginger cat','reference_mode':'fixed','sections':[{'start':0,'title':'Intro','prompt':'wide shot'},{'start':2,'title':'Chorus','prompt':'close-up'}]}
        job=create_job(self.root,self.plan,'cat','noise',42,3.375,[],None,Cancellation(),story=story)
        story['style']='changed after snapshot'
        token=Cancellation()
        def progress(s):
            if s=='Szene 1 gespeichert.': token.cancel()
        with patch('aven.jobs.ensure_models',return_value=[Path('m'),Path('t'),Path('v')]), patch('aven.jobs.cuda_preflight',return_value={'name':'test-only synthetic fixture'}):
            with self.assertRaises(Cancelled): generate(job,self.root/'models',token,progress,engine=[sys.executable,str(self.fake)])
            manifest=load_job(job)
            self.assertEqual(manifest['completed'],1)
            first=job/'scene_000001/clip.mp4'; modified=first.stat().st_mtime_ns
            result=generate(job,self.root/'models',Cancellation(),lambda s:None,engine=[sys.executable,str(self.fake)])
            self.assertTrue(result.exists()); self.assertEqual(first.stat().st_mtime_ns,modified)
            benchmark=json.loads((job/'benchmark.json').read_text())
            self.assertEqual(benchmark['inference'],'synthetic_fixture')
            self.assertEqual(benchmark['visual_assessment'],'pending_user_review')
            self.assertEqual(benchmark['status'],'completed')
            self.assertGreater(benchmark['elapsed_seconds'],0)
            self.assertEqual(load_job(job)['completed'],2)
            first_command=json.loads((job/'scene_000001/command.json').read_text())['argv']
            second_command=json.loads((job/'scene_000002/command.json').read_text())['argv']
            self.assertIn('wide shot',first_command[first_command.index('-p')+1])
            self.assertIn('close-up',second_command[second_command.index('-p')+1])
            self.assertIn('same light',second_command[second_command.index('-p')+1])
            self.assertNotIn('changed after snapshot',second_command[second_command.index('-p')+1])

    def test_legacy_and_outside_reference_rejected(self):
        job=create_job(self.root,self.plan,'cat','',42,2,[],None,Cancellation())
        p=job/'job.json'; data=json.loads(p.read_text())
        data['version']=0; p.write_text(json.dumps(data))
        with self.assertRaises(ValueError): load_job(job)
        data['version']=1; data['references']=['../secret']; p.write_text(json.dumps(data))
        with self.assertRaises(ValueError): load_job(job)

    def test_reference_is_snapshotted_and_tampering_rejected(self):
        src=self.root/'source.png'; Image.new('RGB',(64,32),'red').save(src)
        job=create_job(self.root,self.plan,'cat','',42,2,[(src,0)],None,Cancellation())
        src.unlink(); data=load_job(job)
        self.assertTrue((job/data['references'][0]).exists())
        (job/data['references'][0]).write_bytes(b'changed')
        with self.assertRaises(ValueError): load_job(job)

    def test_continue_clip_and_reuse_avatar_across_resume(self):
        source=self.root/'original clip.mp4'; music=self.root/'song.wav'; avatar=self.root/'avatar.png'
        run([binary('ffmpeg'),'-v','error','-f','lavfi','-i','color=c=red:s=160x90:r=24:d=1',
             '-f','lavfi','-i','sine=frequency=330:sample_rate=48000:duration=1',
             '-c:v','libx264','-c:a','aac','-shortest',source])
        run([binary('ffmpeg'),'-v','error','-f','lavfi','-i','sine=frequency=660:sample_rate=48000:duration=1',music])
        original_bytes=source.read_bytes()
        Image.new('RGB',(64,32),'red').save(avatar)
        token=Cancellation()
        job=create_job(self.root,self.plan,'continue the scene','',42,2.5,[],music,token,
                       source_video=source,avatar=avatar)
        self.assertEqual(source.read_bytes(),original_bytes)
        source.unlink()
        Image.new('RGB',(64,32),'blue').save(avatar)
        def pause_after_first(text):
            if text=='Szene 1 gespeichert.': token.cancel()
        with patch('aven.jobs.ensure_models',return_value=[Path('m'),Path('t'),Path('v')]), patch('aven.jobs.cuda_preflight',return_value={'name':'synthetic fixture'}):
            with self.assertRaises(Cancelled):
                generate(job,self.root/'models',token,pause_after_first,engine=[sys.executable,str(self.fake)])
            first=job/'scene_000001/clip.mp4'; modified=first.stat().st_mtime_ns
            result=generate(job,self.root/'models',Cancellation(),lambda _:None,engine=[sys.executable,str(self.fake)])
            self.assertEqual(first.stat().st_mtime_ns,modified)
        state=load_job(job)
        self.assertEqual(state['completed'],2)
        with Image.open(job/state['references'][0]) as saved:
            self.assertEqual(saved.getpixel((0,0)),(255,0,0))
        for number in (1,2):
            scene=job/f'scene_{number:06}'
            argv=json.loads((scene/'command.json').read_text())['argv']
            self.assertEqual(argv[argv.index('--video-frames')+1],'37')
            self.assertEqual(Path(argv[argv.index('-i')+1]),job/state['references'][0])
            controls=sorted(Path(argv[argv.index('--control-video')+1]).glob('*.png'))
            self.assertEqual(len(controls),4)
            with Image.open(controls[-1]) as context:
                red,green,_=context.getpixel((10,10))
                self.assertGreater(red if number==1 else green,90)
            with Image.open(scene/'generated_000.png') as frame:
                self.assertEqual(frame.getpixel((10,10)),(0,128,0))
        info=probe(result)
        video=next(s for s in info['streams'] if s['codec_type']=='video')
        self.assertAlmostEqual(float(video['duration']),3.5,places=3)
        for seconds in (0.4,1.4):
            frame=self.root/f'frame-{seconds}.png'
            run([binary('ffmpeg'),'-v','error','-ss',str(seconds),'-i',result,'-frames:v','1','-update','1',frame])
            with Image.open(frame) as image:
                red,green,_=image.getpixel((10,10))
                self.assertGreater(red-green if seconds<1 else green-red,90)
        audio=next(s for s in info['streams'] if s['codec_type']=='audio')
        self.assertAlmostEqual(float(audio['duration']),3.5,places=2)
        from array import array
        for seconds,expected in [(0.25,330),(1.25,660),(2.25,0)]:
            samples=self.root/f'audio-{seconds}.raw'
            run([binary('ffmpeg'),'-v','error','-ss',str(seconds),'-i',result,'-map','0:a:0',
                 '-t','0.25','-ac','1','-ar','48000','-f','s16le',samples])
            signal=array('h',samples.read_bytes())
            if expected:
                crossings=sum(a<0<=b for a,b in zip(signal,signal[1:]))
                self.assertAlmostEqual(crossings*4,expected,delta=12)
            else:
                self.assertLess(max(map(abs,signal)),20)
        (job/state['source_video']).write_bytes(b'changed')
        with self.assertRaises(ValueError): load_job(job)

    def test_avatar_is_reused_without_a_source_clip(self):
        avatar=self.root/'avatar.png'; other=self.root/'other.png'
        Image.new('RGB',(32,64),'red').save(avatar); Image.new('RGB',(64,32),'blue').save(other)
        job=create_job(self.root,self.plan,'cat','',42,2,[(other,0)],None,Cancellation(),avatar=avatar)
        state=load_job(job)
        self.assertEqual(len(state['references']),1)
        with Image.open(job/state['references'][0]) as saved:
            self.assertEqual(saved.getpixel((0,0)),(255,0,0))

    def test_continuation_defaults_to_last_source_frame_without_avatar(self):
        source=self.root/'silent.mp4'
        run([binary('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=16:d=0.5',
             '-c:v','libx264',source])
        job=create_job(self.root,self.plan,'continue the scene','',42,1,[],None,Cancellation(),source_video=source)
        with patch('aven.jobs.ensure_models',return_value=[Path('m'),Path('t'),Path('v')]), patch('aven.jobs.cuda_preflight',return_value={}):
            result=generate(job,self.root/'models',Cancellation(),lambda _:None,engine=[sys.executable,str(self.fake)])
        self.assertEqual([s['codec_type'] for s in probe(result)['streams']],['video'])
        projects=list_projects(self.root)
        self.assertEqual(len(projects),1)
        self.assertTrue(projects[0]['valid'])
        reference=reference_path(job,projects[0]['data'],None,scene=1)
        argv=json.loads((job/'scene_000001/command.json').read_text())['argv']
        self.assertEqual(reference,job/'scene_000001/control/frame_003.png')
        self.assertEqual(Path(argv[argv.index('-i')+1]),reference)

    def test_wrong_resolution_cached_clip_rebuilt_without_neural_work(self):
        job=create_job(self.root,self.plan,'cat','',42,2,[],None,Cancellation())
        with patch('aven.jobs.ensure_models',return_value=[Path('m'),Path('t'),Path('v')]), patch('aven.jobs.cuda_preflight',return_value={'name':'test-only synthetic fixture'}):
            generate(job,self.root/'models',Cancellation(),lambda s:None,engine=[sys.executable,str(self.fake)])
            low=self.root/'low'; low.mkdir(); frames=[]
            for i in range(33):
                im=Image.new('RGB',(64,64),'red'); ImageDraw.Draw(im).rectangle((0,0,31,63),fill='white')
                f=low/f'generated_{i:03}.png'; im.save(f); frames.append(f)
            encode_scene(frames,16,low/'clip.mp4',Cancellation())
            shutil.copy2(low/'clip.mp4',job/'scene_000001/clip.mp4')
            result=generate(job,self.root/'models',Cancellation(),lambda s:None,engine=[sys.executable,str(self.root/'must-not-run.py')])
            video=next(s for s in probe(result)['streams'] if s['codec_type']=='video')
            self.assertEqual((video['width'],video['height']),(832,480))


if __name__=='__main__': unittest.main()
