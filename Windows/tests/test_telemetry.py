import sys
import threading
import time
import unittest
from pathlib import Path
from aven.policy import Plan, engine_arguments
from aven.runtime import run, Cancellation


class TelemetryTests(unittest.TestCase):
    def test_live_callback_arrives_before_child_exit(self):
        seen=threading.Event(); finished=threading.Event(); errors=[]
        def worker():
            try: run([sys.executable,'-u','-c',"import time; print('sampling using Euler method',flush=True); time.sleep(.8)"],on_output=lambda s:seen.set())
            except Exception as e: errors.append(e)
            finally: finished.set()
        t=threading.Thread(target=worker); t.start()
        try:
            self.assertTrue(seen.wait(.6),errors)
            self.assertFalse(finished.is_set())
        finally: t.join(3)
        self.assertEqual(errors,[])

    def test_sampling_parser_excludes_loading_and_vae(self):
        from aven.telemetry import SamplingProgress
        p=SamplingProgress(20)
        p.feed('\r |==>| 1/20 - 5.0s/it - ETA 01:35\x1b[K\r')
        self.assertEqual(p.step,0)
        p.feed('[I] sampling using Euler method\n[V] VAE encode tile size: 256x256\n |==>| 1/20 - 5.0s/it\r')
        self.assertEqual(p.step,0)
        p.feed('[V] sample 104x60x9 --- video.cpp:1742\n')
        p.feed('\r |==>| 2/20 - '); p.feed('5.0s/it - ETA 01:30\x1b[K\r')
        self.assertEqual(p.step,2); self.assertEqual(p.remaining_seconds,90)
        p.feed('\r |==>| 1/104 - 80MB/s\r')
        self.assertEqual(p.step,2)
        p.feed('[I] sampling completed, taking 100s\n\r |==>| 18/20 - 1.0s/it\r')
        self.assertEqual(p.step,20); self.assertIsNone(p.remaining_seconds)

    def test_unknown_or_nonfinite_rate_has_no_eta(self):
        from aven.telemetry import SamplingProgress
        p=SamplingProgress(20); p.feed('[V] sample 104x60x9 --- video.cpp:1742\n')
        self.assertIsNone(p.remaining_seconds)
        p.feed(' |==>| 1/20 - nans/it\r')
        self.assertIsNone(p.remaining_seconds)
        p.feed(' |==>| 3/20 - 4.0s/it\r')
        self.assertEqual(p.remaining_seconds,68)
        p.feed(' |==>| 2/20 - 1.0s/it\r')
        self.assertEqual(p.step,3)

    def test_3080_ram_staging_preserves_quality_and_resident_choice(self):
        p=Plan.make(1,'16:9',memory_mode='balanced',vram_mb=10240)
        a=engine_arguments(p,'cat','',42,['m','t','v'],Path('.'))
        self.assertEqual((p.width,p.height,p.steps,p.frames),(832,480,20,33))
        self.assertEqual(a[a.index('--params-backend')+1],'diffusion=cpu,te=cpu,vae=cpu')
        self.assertEqual(a[a.index('--max-vram')+1],'cuda0=8')
        q=Plan.make(1,'16:9',memory_mode='resident',vram_mb=8192)
        b=engine_arguments(q,'cat','',42,['m','t','v'],Path('.'))
        self.assertEqual(b[b.index('--max-vram')+1],'cuda0=6')
        self.assertEqual(b[b.index('--params-backend')+1],'diffusion=cuda0,te=cpu,vae=cpu')
        with self.assertRaises(ValueError): Plan.make(1,'16:9',memory_mode='bad')


if __name__=='__main__': unittest.main()

class MonitorTests(unittest.TestCase):
    def test_missing_gpu_metrics_do_not_fail_or_block_generation(self):
        from unittest.mock import patch
        from aven.telemetry import Tracker
        seen=threading.Event()
        tracker=Tracker(20,lambda event:seen.set())
        with patch('aven.telemetry.nvidia_sample',side_effect=ValueError('unsupported metric')):
            tracker.start()
            self.assertTrue(seen.wait(1))
            tracker.close()
        self.assertFalse(tracker.thread.is_alive())
        self.assertIsNone(tracker.snapshot()['gpu'])
        self.assertEqual(tracker.snapshot()['gpu_samples'],0)

    def test_streamed_utf8_and_cancel_stop_child(self):
        from aven.runtime import Cancelled
        token=Cancellation(); chunks=[]
        def output(text):
            chunks.append(text)
            if 'ü' in ''.join(chunks): token.cancel()
        script="import os,time; os.write(1,b'\\xc3'); time.sleep(.05); os.write(1,b'\\xbc\\r'); time.sleep(5)"
        start=time.monotonic()
        with self.assertRaises(Cancelled): run([sys.executable,'-u','-c',script],token,on_output=output)
        self.assertIn('ü',''.join(chunks)); self.assertLess(time.monotonic()-start,3)


class TerminalProgressTests(unittest.TestCase):
    def test_terminal_transition_is_emitted_even_inside_throttle_window(self):
        from aven.telemetry import Tracker
        events=[]; tracker=Tracker(20,events.append)
        tracker.phase('muxing')
        tracker.phase('completed')
        self.assertEqual(events[-1]['stage'],'completed')
        tracker.phase('cancelled')
        self.assertEqual(events[-1]['stage'],'cancelled')
