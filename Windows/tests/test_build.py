import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import build


class PackagedCheckTests(unittest.TestCase):
    def check_app(self, args):
        return build.check_app(args, timeout=10)

    def test_windowed_child_error_reaches_build_failure(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, LOCALAPPDATA=temporary):
            script = (
                "from aven.runtime import user_root; "
                "p=user_root()/'app-error.log'; p.parent.mkdir(parents=True,exist_ok=True); "
                "p.write_text('Inner startup failure: missing engine contract',encoding='utf-8'); "
                "raise SystemExit(1)"
            )
            with self.assertRaisesRegex(RuntimeError, 'Inner startup failure: missing engine contract'):
                self.check_app([sys.executable, '-c', script])

    def test_previous_error_is_not_reported_for_new_child_failure(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, LOCALAPPDATA=temporary):
            error = Path(temporary)/'AVEN Video AI/app-error.log'
            error.parent.mkdir(parents=True); error.write_text('STALE FAILURE',encoding='utf-8')
            with self.assertRaises(RuntimeError) as failure:
                self.check_app([sys.executable, '-c', 'raise SystemExit(7)'])
            self.assertNotIn('STALE FAILURE',str(failure.exception))
            self.assertIn('7',str(failure.exception))
            self.assertFalse(error.exists())

    def test_successful_child_remains_successful(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, LOCALAPPDATA=temporary):
            self.check_app([sys.executable, '-c', 'pass'])


class RuntimeBundleTests(unittest.TestCase):
    def test_openmp_and_complete_crt_are_copied_from_same_redist_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); vs=root/'Visual Studio'; engine=root/'engine'; engine.mkdir()
            redist=vs/'2022/Enterprise/VC/Redist/MSVC/14.44.35211/x64'
            crt=redist/'Microsoft.VC143.CRT'; omp=redist/'Microsoft.VC143.OpenMP'
            crt.mkdir(parents=True); omp.mkdir()
            for name in ['msvcp140.dll','msvcp140_codecvt_ids.dll','vcruntime140.dll','vcruntime140_1.dll']:
                (crt/name).write_bytes(b'CRT 14.44')
            (omp/'vcomp140.dll').write_bytes(b'OpenMP 14.44')
            old=vs/'2022/Enterprise/VC/Redist/MSVC/14.9.1/x64/Microsoft.VC143.CRT'
            old.mkdir(parents=True); (old/'msvcp140.dll').write_bytes(b'old')
            build.copy_msvc_runtime(vs,engine)
            self.assertEqual((engine/'vcomp140.dll').read_bytes(),b'OpenMP 14.44')
            self.assertEqual((engine/'msvcp140.dll').read_bytes(),b'CRT 14.44')
            self.assertEqual((engine/'msvcp140_codecvt_ids.dll').read_bytes(),b'CRT 14.44')

    def test_missing_openmp_stops_packaging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); engine=root/'engine'; engine.mkdir()
            crt=root/'Visual Studio/2022/Enterprise/VC/Redist/MSVC/14.44.35211/x64/Microsoft.VC143.CRT'
            crt.mkdir(parents=True)
            for name in ['msvcp140.dll','msvcp140_codecvt_ids.dll','vcruntime140.dll','vcruntime140_1.dll']:
                (crt/name).write_bytes(b'CRT')
            with self.assertRaisesRegex(RuntimeError,'vcomp140.dll'):
                build.copy_msvc_runtime(root/'Visual Studio',engine)


class DriverContractTests(unittest.TestCase):
    def test_missing_support_dll_still_fails_media_smoke_without_nvidia_driver(self):
        import ctypes
        from aven import selftest
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,WINDIR=temporary), patch.object(selftest,'sys',SimpleNamespace(platform='win32')):
            with patch.object(selftest,'binary',return_value=Path(temporary)/'engine/sd-cli.exe'), patch.object(ctypes,'WinDLL',side_effect=OSError('missing OpenMP dependency'),create=True):
                with self.assertRaisesRegex(OSError,'missing OpenMP dependency'):
                    selftest.self_test(Path(temporary)/'smoke')

    def test_gpu_less_smoke_records_support_dlls_and_media_separately_from_cuda(self):
        import ctypes
        import json
        from aven import selftest
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,WINDIR=temporary), patch.object(selftest,'sys',SimpleNamespace(platform='win32')):
            folder=Path(temporary)/'smoke'
            with patch.object(selftest,'binary',return_value=Path(temporary)/'engine/sd-cli.exe'), patch.object(ctypes,'WinDLL',return_value=object(),create=True):
                selftest.self_test(folder)
            result=json.loads((folder/'self-test.json').read_text())
            self.assertEqual(result.get('engine_support_dlls'),'passed')
            self.assertEqual(result['synthetic_media'],'passed')
            self.assertEqual(result['engine_cli'],'not_run_no_nvidia_driver')
            self.assertEqual(result['cuda_inference'],'not_run')

    def test_gpu_less_windows_host_reports_driver_absence_without_starting_cuda_exe(self):
        from aven import selftest
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,WINDIR=temporary), patch.object(selftest,'sys',SimpleNamespace(platform='win32')):
            self.assertEqual(selftest.engine_contract(),'not_run_no_nvidia_driver')

    def test_installed_driver_requires_all_cli_flags_and_propagates_engine_errors(self):
        from aven import selftest
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,WINDIR=temporary), patch.object(selftest,'sys',SimpleNamespace(platform='win32')):
            root=Path(temporary); driver=root/'System32/nvcuda.dll'; driver.parent.mkdir(); driver.write_bytes(b'driver fixture')
            engine=root/'engine'; engine.mkdir(); (engine/'sd-cli.exe').write_bytes(b'engine fixture')
            flags='--backend --params-backend --video-frames --flow-shift --scheduler --auto-fit --temporal-tiling --max-vram --control-video'
            with patch.object(selftest,'binary',return_value=engine/'sd-cli.exe'), patch.object(selftest,'run',return_value=flags):
                self.assertEqual(selftest.engine_contract(),'passed')
            with patch.object(selftest,'binary',return_value=engine/'sd-cli.exe'), patch.object(selftest,'run',return_value=flags.replace('--max-vram','')):
                with self.assertRaisesRegex(ValueError,'--max-vram'):
                    selftest.engine_contract()
            with patch.object(selftest,'binary',return_value=engine/'sd-cli.exe'), patch.object(selftest,'run',side_effect=RuntimeError('engine dependency failed')):
                with self.assertRaisesRegex(RuntimeError,'engine dependency failed'):
                    selftest.engine_contract()


if __name__ == '__main__':
    unittest.main()
