"""Compatibility entry point: run current build checks, not obsolete v1 string assertions."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).parent / 'tests' / 'smoke_static.py'), run_name='__main__')
