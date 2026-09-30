"""Supported optional research replay cannot overwrite accepted application data."""
from __future__ import annotations
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ResearchReplayPathTests(unittest.TestCase):
    def test_rectangular_default_output_is_fresh_and_separate(self):
        loaded = runpy.run_path(str(ROOT / 'research/rectangular_duct/prepare_replay.py'))
        prepare = loaded['prepare_output']
        with tempfile.TemporaryDirectory() as directory:
            prepare.__globals__['REPO_ROOT'] = Path(directory)
            with patch.dict(os.environ, {}, clear=True):
                a, b = prepare(), prepare()
            self.assertNotEqual(a, b)
            self.assertEqual(a.parent, Path(directory) / 'output')
            self.assertEqual((a / 'README.md').read_bytes(), (ROOT / 'examples/rectangular_experiment/README.md').read_bytes())

    def test_rectangular_fresh_requested_output_gets_readme(self):
        loaded = runpy.run_path(str(ROOT / 'research/rectangular_duct/prepare_replay.py'))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'new' / 'results'
            with patch.dict(os.environ, {'RECTANGULAR_OUTPUT_DIR': str(target)}):
                self.assertEqual(loaded['prepare_output'](), target.resolve())
            self.assertTrue((target / 'README.md').is_file())

    def test_rectangular_refuses_accepted_or_code_output(self):
        loaded = runpy.run_path(str(ROOT / 'research/rectangular_duct/prepare_replay.py'))
        for path in (ROOT, ROOT / 'examples/rectangular_experiment', ROOT / 'examples/rectangular_experiment/new', ROOT / 'research/rectangular_duct'):
            with self.subTest(path=path), patch.dict(os.environ, {'RECTANGULAR_OUTPUT_DIR': str(path)}):
                with self.assertRaises(ValueError):
                    loaded['prepare_output']()
