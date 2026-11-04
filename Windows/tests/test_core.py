import hashlib
import json
import math
from pathlib import Path
import tempfile
import threading
import unittest

from aven.policy import Plan, duration, engine_arguments, ordered_frames
from aven.runtime import Cancelled, Cancellation, local_path, run
from aven.models import verify_file


class PolicyTests(unittest.TestCase):
    def test_profiles_match_mac_quality(self):
        for level, steps in enumerate([20,22,24,26,28,32,36,40,44,50], 1):
            for fmt, dims in [('16:9',(832,480)),('9:16',(480,832)),('1:1',(640,640))]:
                p = Plan.make(level, fmt, cores=56)
                self.assertEqual(p.steps, steps)
                self.assertEqual((p.width,p.height), dims if level < 8 else {'16:9':(1024,576),'9:16':(576,1024),'1:1':(768,768)}[fmt])
                self.assertEqual((p.frames,p.fps,p.cfg,p.shift), (33,16,5.0,16.0))
                self.assertLessEqual(p.threads,16)
        self.assertEqual(Plan.make(1,'16:9',cores=1).threads,1)

    def test_literal_cuda_contract_and_unicode_prompt(self):
        p = Plan.make(1,'16:9')
        args = engine_arguments(p, 'Katze; $(echo test) ü', 'noise', 42, ['m','t','v'], Path('scene x'))
        self.assertEqual(args[args.index('--backend')+1], 'diffusion=cuda0,te=cpu,vae=cpu')
        self.assertEqual(args[args.index('--params-backend')+1], 'diffusion=cpu,te=cpu,vae=cpu')
        self.assertEqual(args[args.index('-p')+1], 'Katze; $(echo test) ü')
        self.assertEqual(args[args.index('--auto-fit')+1], 'off')
        self.assertEqual(args[args.index('--scheduler')+1], 'discrete')
        self.assertEqual(args[args.index('-o')+1], str(Path('scene x')/'generated_%03d.png'))
        for seed in [-1, 2**31]:
            with self.assertRaises(ValueError): engine_arguments(p,'cat','',seed,['m','t','v'],Path('.'))

    def test_music_and_invalid_input(self):
        self.assertEqual(duration(30,301.375,True),301.375)
        self.assertEqual(duration(6,5.375,False),6)
        for n in [0,-1,float('nan'),float('inf'),86401]:
            with self.assertRaises(ValueError): duration(n,None,False)
        with self.assertRaises(ValueError): duration(30,None,True)
        for n in [0,11]:
            with self.assertRaises(ValueError): Plan.make(n,'16:9')

    def test_music_mode_ignores_unused_manual_field(self):
        from aven.policy import target_duration
        self.assertEqual(target_duration('unused invalid field',301.375,True),301.375)
        self.assertEqual(target_duration('6',5.375,False),6)
        with self.assertRaises(ValueError): target_duration('invalid',None,False)

    def test_numbered_frames_no_lexical_sort_or_holes(self):
        files = [Path(f'generated_{i:03}.png') for i in reversed(range(33))]
        self.assertEqual(ordered_frames(files,33)[10].name,'generated_010.png')
        for bad in [files[:-1], files+[files[0]], files[:-1]+[Path('generated_099.png')]]:
            with self.assertRaises(ValueError): ordered_frames(bad,33)

    def test_manifest_paths_stay_inside_job(self):
        root = Path(tempfile.gettempdir())/'aven-job'
        self.assertEqual(local_path(root,'references/001.png'), root.resolve()/'references/001.png')
        for p in ['../bad','/tmp/bad','C:\\secret','references/../../bad','\\\\server\\share']:
            with self.assertRaises(ValueError): local_path(root,p)

    def test_checksum_reads_actual_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)/'model'; f.write_bytes(b'valid model')
            digest = hashlib.sha256(b'valid model').hexdigest()
            verify_file(f,11,digest,Cancellation())
            f.write_bytes(b'invalidmode')
            with self.assertRaises(ValueError): verify_file(f,11,digest,Cancellation())
            c = Cancellation(); c.cancel()
            with self.assertRaises(Cancelled): verify_file(f,11,digest,c)

    def test_cancelled_work_never_publishes(self):
        c = Cancellation(); c.cancel()
        seen = []
        with self.assertRaises(Cancelled): c.publish(lambda: seen.append(1))
        self.assertEqual(seen,[])
        with self.assertRaises(Cancelled): run(['unused'], c)


if __name__ == '__main__': unittest.main()
