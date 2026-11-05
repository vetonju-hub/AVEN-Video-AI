import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from aven.bundle import extract_checked, download_checked
from aven.runtime import Cancellation, Cancelled


class BundleTests(unittest.TestCase):
    def test_archive_rejects_traversal_windows_drives_and_links(self):
        for bad in ['../outside','/absolute','C:/Windows/bad','folder\\..\\bad']:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d); archive=root/'a.zip'
                with zipfile.ZipFile(archive,'w') as z: z.writestr(bad,b'bad')
                with self.assertRaises(ValueError): extract_checked(archive,root/'out')
    def test_archive_extracts_valid_bytes_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); archive=root/'a.zip'
            with zipfile.ZipFile(archive,'w') as z: z.writestr('bin/tool.exe',b'valid')
            extract_checked(archive,root/'out')
            self.assertEqual((root/'out/bin/tool.exe').read_bytes(),b'valid')
            with zipfile.ZipFile(archive,'w') as z: z.writestr('bin/tool.exe',b'other')
            with self.assertRaises(ValueError): extract_checked(archive,root/'out')
    def test_verified_download_and_failed_cache_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); src=root/'source'; src.write_bytes(b'content')
            target=root/'cache'; sha=hashlib.sha256(b'content').hexdigest()
            download_checked(src.as_uri(),target,sha,Cancellation())
            self.assertEqual(target.read_bytes(),b'content')
            target.unlink()
            with self.assertRaises(ValueError): download_checked(src.as_uri(),target,'0'*64,Cancellation())
            self.assertFalse(target.exists())
            c=Cancellation(); c.cancel()
            with self.assertRaises(Cancelled): download_checked(src.as_uri(),target,sha,c)


if __name__=='__main__': unittest.main()
