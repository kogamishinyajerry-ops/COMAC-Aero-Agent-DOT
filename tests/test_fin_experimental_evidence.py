"""Bounded standard-library replay of the independently reviewed plate-fin study."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from aerolab.fin_experimental_evidence import (ROOT, PREFIX, MANIFEST_PATH,
    EXPECTED_MANIFEST_SHA256, read_fin_experimental_evidence)
from aerolab.server import Handler
from research.plate_fin.audit_package import audit, strict_json


def copied_package(directory):
    root = Path(directory)
    manifest = json.loads((ROOT / MANIFEST_PATH).read_text())
    for name in [r['proposed_repository_path'] for r in manifest['files']] + [MANIFEST_PATH]:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return root


class FinExperimentalEvidenceTests(unittest.TestCase):
    def test_all_points_models_and_scope_remain(self):
        r = read_fin_experimental_evidence()
        self.assertFalse(r['live_computation'])
        self.assertIsNone(r['physical_validation_pass'])
        self.assertFalse(r['aircraft_transfer_authorized'])
        self.assertEqual(r['calibration_records'], 0)
        self.assertEqual(len(r['rows']), 12)
        self.assertEqual(r['research_report']['source']['author_claimed_run_count'], 13)
        self.assertEqual(r['research_report']['scope_counts'], {
            'robustly_in_declared_laminar_scope': 3,
            'nominally_laminar_boundary_uncertain': 1,
            'nominally_outside_laminar_scope': 8,
        })
        self.assertEqual(len(r['numerical']['gates']), 17)
        self.assertTrue(all(r['numerical']['gates'].values()))
        self.assertEqual(r['provenance']['package_manifest_sha256'], EXPECTED_MANIFEST_SHA256)
        self.assertLess(len(json.dumps(r).encode()), 100_000)

    def test_arithmetic_and_uncertainty_are_separate(self):
        r = read_fin_experimental_evidence()
        for row in r['rows']:
            self.assertAlmostEqual(row['relative_Rth_discrepancy'], row['fd_Rth_K_W'] / row['observed_Rth_K_W'] - 1, places=14)
            self.assertAlmostEqual(row['author_Rth_absolute_uncertainty_K_W'], .012 * row['observed_Rth_K_W'], places=14)
            self.assertGreater(row['graphical_Rth_allowance_K_W'], 0)
            self.assertGreater(row['graphical_V_allowance_m_s'], 0)
            self.assertNotEqual(row['fd_Rth_K_W'], row['plug_Rth_K_W'])
        self.assertAlmostEqual(r['rows'][0]['relative_Rth_discrepancy'] * 100, .5068388486081599, places=12)
        self.assertIn('four nominally', r['topology_range_scope'])
        self.assertGreater(r['side_channel_heat_fraction_range'][0], .06)
        self.assertLess(r['side_channel_heat_fraction_range'][1], .065)

    def test_no_scientific_runtime_dependency(self):
        command = "from aerolab.fin_experimental_evidence import read_fin_experimental_evidence; import sys; r=read_fin_experimental_evidence(); assert not any(x in sys.modules for x in ('numpy','scipy','matplotlib')); print(len(r['rows']))"
        p = subprocess.run([sys.executable, '-S', '-c', command], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), '12')

    def test_pin_mismatch_rejected(self):
        with patch('aerolab.fin_experimental_evidence.EXPECTED_MANIFEST_SHA256', 'bad'):
            with self.assertRaisesRegex(RuntimeError, 'missing, stale or inconsistent'):
                read_fin_experimental_evidence()

    def test_artifact_tamper_and_missing_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = copied_package(directory)
            target = root / PREFIX / 'plate_fin_report.json'
            target.write_bytes(target.read_bytes() + b' ')
            with self.assertRaises(RuntimeError):
                read_fin_experimental_evidence(root)
            target.unlink()
            with self.assertRaises(RuntimeError):
                read_fin_experimental_evidence(root)

    def test_audited_snapshot_not_reread(self):
        expected = read_fin_experimental_evidence()
        with tempfile.TemporaryDirectory() as directory:
            root = copied_package(directory)
            def audit_then_replace(*args, **kwargs):
                verified = audit(*args, **kwargs)
                (root / PREFIX / 'plate_fin_report.json').write_text('{"unaudited":true}')
                return verified
            with patch('research.plate_fin.audit_package.audit', audit_then_replace):
                actual = read_fin_experimental_evidence(root)
            self.assertEqual(actual, expected)
            with self.assertRaises(RuntimeError):
                read_fin_experimental_evidence(root)

    def test_invalid_paths_and_oversized_manifest_fail(self):
        manifest = json.loads((ROOT / MANIFEST_PATH).read_text())
        manifest['files'][0]['proposed_repository_path'] = '../outside.json'
        raw = json.dumps(manifest).encode()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / MANIFEST_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
            with self.assertRaises(ValueError):
                audit(directory, expected_manifest_sha256=hashlib.sha256(raw).hexdigest())
            target.write_bytes(b' ' * 100_001)
            with self.assertRaises(ValueError):
                audit(directory)

    def test_all_nonfinite_json_forms_fail(self):
        for value in ['NaN', 'Infinity', '-Infinity', '1e400']:
            with self.assertRaises(ValueError):
                strict_json(('{"nested":[{"value":' + value + '}]}').encode())


class FinExperimentalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=30)
        conn.request(method, path)
        response = conn.getresponse()
        result = response.status, response.read(), response.headers
        conn.close()
        return result

    def test_complete_get_and_script(self):
        code, raw, _ = self.request('GET', '/api/physics/fin-experiment')
        self.assertEqual(code, 200)
        self.assertEqual(len(json.loads(raw)['rows']), 12)
        self.assertLess(len(raw), 100_000)
        code, raw, headers = self.request('GET', '/fin_experiment.js')
        self.assertEqual(code, 200)
        self.assertIn('text/javascript', headers['Content-Type'])
        self.assertIn(b'fin-comparison-chart', raw)

    def test_saved_replay_cannot_be_tuned(self):
        self.assertEqual(self.request('GET', '/api/physics/fin-experiment?ks=1000')[0], 400)
        self.assertEqual(self.request('POST', '/api/physics/fin-experiment')[0], 404)

    def test_stale_evidence_http_error(self):
        with patch('aerolab.fin_experimental_evidence.EXPECTED_MANIFEST_SHA256', 'bad'):
            code, raw, _ = self.request('GET', '/api/physics/fin-experiment')
            self.assertEqual(code, 503)
            self.assertIn('stale or inconsistent', json.loads(raw)['error'])


if __name__ == '__main__':
    unittest.main()
