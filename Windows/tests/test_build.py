import os
from pathlib import Path
import sys
import tempfile
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


if __name__ == '__main__':
    unittest.main()
