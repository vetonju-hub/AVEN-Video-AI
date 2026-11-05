"""Regression checks for the active Windows-only project layout."""
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]


class WindowsLayoutTests(unittest.TestCase):
    def test_entrypoint_and_workflow(self):
        self.assertTrue((ROOT / 'Windows' / 'main.py').is_file())
        self.assertTrue((ROOT / '.github' / 'workflows' / 'build-windows.yml').is_file())

    def test_icon_is_native_project_asset(self):
        path = ROOT / 'Windows' / 'assets' / 'aven-icon.png'
        data = path.read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        width, height = struct.unpack('>II', data[16:24])
        self.assertGreaterEqual(width, 256)
        self.assertGreaterEqual(height, 256)

    def test_no_duplicate_source_trees(self):
        for old in ('In_AVEN-Video-AI_kopieren', 'Sources', 'Assets', 'scripts', 'tests'):
            with self.subTest(old=old):
                self.assertFalse((ROOT / old).exists())
