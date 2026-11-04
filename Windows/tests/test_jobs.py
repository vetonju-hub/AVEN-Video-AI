from pathlib import Path
import json
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from aven.policy import Plan, ENGINE_TAG
from aven.runtime import Cancellation,Cancelled
from aven.jobs import create_job, load_job, generate
from aven.media import encode_scene, probe


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.fake=self.root/'fake.py'
        self.fake.write_text('''import sys
from pathlib import Path
from PIL import Image,ImageDraw
a=sys.argv
w=int(a[a.index('-W')+1]); h=int(a[a.index('-H')+1]); out=a[a.index('-o')+1]
for i in range(33):
 im=Image.new('RGB',(w,h),'red'); d=ImageDraw.Draw(im); d.rectangle((0,0,w//2,h),fill='green'); d.rectangle((i*2,20,i*2+30,90),fill='blue'); im.save(out % i)
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
