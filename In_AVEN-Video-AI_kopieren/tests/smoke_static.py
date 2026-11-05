"""Build/package checks; behavior is tested by Swift executables, not source substrings."""
from pathlib import Path
import plistlib
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

class BuildChecks(unittest.TestCase):
    def test_info_plist(self):
        info = plistlib.loads((ROOT / 'Info.plist').read_bytes())
        self.assertEqual(info['CFBundleShortVersionString'], '3.4.0')
        self.assertEqual(info['LSMinimumSystemVersion'], '14.0')
        self.assertEqual(info['CFBundleExecutable'], 'AVEN Video AI')

    def test_engine_revision_is_pinned(self):
        revision = (ROOT / 'scripts/engine-revision.txt').read_text().strip()
        self.assertRegex(revision, r'^[a-f0-9]{40}$')

    def test_visible_workflow_copy_matches(self):
        self.assertEqual((ROOT / 'build-macos.yml').read_bytes(), (ROOT / '.github/workflows/build-macos.yml').read_bytes())

    def test_shell_scripts_parse(self):
        for file in sorted(ROOT.glob('scripts/*.sh')) + sorted(ROOT.glob('tests/*.sh')):
            with self.subTest(file=file.name):
                subprocess.run(['bash','-n', str(file)], check=True)

    def test_all_swift_sources_parse(self):
        import shutil, os
        compiler = os.environ.get('SWIFTC') or shutil.which('swiftc')
        if compiler is None: self.skipTest('Swift compiler unavailable on this host')
        subprocess.run([compiler, '-frontend', '-parse'] + [str(p) for p in sorted((ROOT / 'Sources').glob('*.swift'))], check=True)

if __name__ == '__main__':
    unittest.main()
