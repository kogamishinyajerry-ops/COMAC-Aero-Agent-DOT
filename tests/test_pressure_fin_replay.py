"""Saved pressure-fin UI: invariants, immutable identity and failure visibility.

These are reader/API tests, not browser evidence. Browser acceptance is separate.
"""
from __future__ import annotations

import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from aerolab import pressure_fin_replay as replay
from aerolab.server import Handler


class PressureFinReplayTests(unittest.TestCase):
    def test_all_saved_selections_keep_fixed_requirement_and_fit_bound(self):
        max_bytes = 0
        for ident in replay.DESIGN_IDS:
            for case in replay.CASE_IDS:
                for heat in replay.HEAT_LOADS_W:
                    with self.subTest(ident=ident, case=case, heat=heat):
                        r = replay.read_pressure_fin_replay(ident, case, heat)
                        self.assertEqual(r['selection'], {'design_id': ident, 'case_id': case, 'heat_load_W': heat})
                        self.assertFalse(r['live_computation'])
                        self.assertIsNone(r['physical_validation_pass'])
                        self.assertFalse(r['aircraft_transfer_authorized'])
                        self.assertEqual(r['execution'], 'verified_research_replay')
                        self.assertEqual(r['numerical']['gate_count'], 19)
                        self.assertEqual(len(r['model_form_sensitivity']['rows']), 18)
                        self.assertEqual(len(r['candidates']), 9)
                        self.assertEqual(sum(not x['all_cases_within_declared_Re_scope'] for x in r['candidates']), 2)
                        fixed = r['selected']['fixed_60W_combined_criterion']
                        self.assertEqual(fixed['heat_load_W'], 60)
                        self.assertFalse(fixed['Reynolds_qualified_conditional_pass'])
                        self.assertEqual(r['declared_60W_summary']['combined_conditional_screen_pass_design_ids'], [])
                        self.assertEqual(r['declared_60W_summary']['nominal_conditional_screen_pass_design_ids'], ['n16_t600', 'n16_t860', 'n20_t600'])
                        current = r['current_heat_load_record']
                        conductance = r['selected']['cases'][case]['G_W_K']
                        self.assertAlmostEqual(current['required_uniform_base_temperature_C'], 25 + heat / conductance, places=10)
                        max_bytes = max(max_bytes, len(json.dumps(r, ensure_ascii=False).encode()))
        self.assertLess(max_bytes, 100_000)

    def test_accepted_counterexample_is_prominent_and_load_does_not_redefine_it(self):
        r = replay.read_pressure_fin_replay('n16_t600', 'combined_fault', 40)
        self.assertAlmostEqual(r['selected']['fin_only_aluminum_mass_g'], 26.36064, places=7)
        self.assertAlmostEqual(r['baseline']['fin_only_aluminum_mass_g'], 37.783584, places=7)
        self.assertTrue(r['current_heat_load_record']['selected_scenario_condition_pass'])
        fixed = next(x for x in r['selected']['cases']['combined_fault']['heat_load_records'] if x['heat_load_W'] == 60)
        self.assertAlmostEqual(fixed['required_uniform_base_temperature_C'], 93.55992337793536, places=10)
        self.assertFalse(fixed['selected_scenario_condition_pass'])
        capacity = r['combined_capacity_at_synthetic_limit']
        self.assertAlmostEqual(capacity['selected_heat_rejection_W'], 60 * r['selected']['cases']['combined_fault']['G_W_K'], places=12)
        self.assertAlmostEqual(capacity['selected_heat_shortfall_W'], 60 - capacity['selected_heat_rejection_W'], places=12)
        self.assertAlmostEqual(capacity['baseline_heat_rejection_W'], 44.746732920572885, places=10)
        self.assertEqual(r['declared_60W_summary']['pareto_within_Re_scope_design_ids'], ['n16_t600'])
        self.assertEqual(r['requirements_synthetic_not_aircraft']['maximum_base_temperature_C'], 85)
        self.assertEqual(r['requirements_synthetic_not_aircraft']['fin_only_mass_budget_kg'], .04)

    def test_branch_network_and_fin_mass_remain_physically_interpretable(self):
        for ident in replay.DESIGN_IDS:
            r = replay.read_pressure_fin_replay(ident)
            d = r['selected']; g = d['geometry']; cases = d['cases']
            self.assertAlmostEqual(d['fin_only_aluminum_mass_g'], 2700 * g['N_fins'] * g['fin_thickness_m'] * g['fin_height_m'] * g['length_m'] * 1000, places=10)
            for source, fault in [('nominal', 'asymmetric_blockage'), ('pressure_loss', 'combined_fault')]:
                a, b = cases[source], cases[fault]
                self.assertEqual(len(b['branches']), g['N_fins'] + 1)
                self.assertEqual(b['branches'][1]['mass_flow_kg_s'], 0)
                self.assertTrue(b['branches'][1]['blocked'])
                self.assertAlmostEqual(sum(x['mass_flow_kg_s'] for x in b['branches']), b['mass_flow_kg_s'], places=14)
                self.assertAlmostEqual(a['mass_flow_kg_s'] - b['mass_flow_kg_s'], a['branches'][1]['mass_flow_kg_s'], places=14)
                for before, after in zip(a['branches'], b['branches']):
                    if after['index'] != 1:
                        self.assertAlmostEqual(before['mass_flow_kg_s'], after['mass_flow_kg_s'], places=14)
                self.assertAlmostEqual(b['hydraulic_dissipation_W'], b['supply_pressure_drop_Pa'] * b['volume_flow_m3_s'], places=14)
            for before, after in zip(cases['nominal']['branches'], cases['combined_fault']['branches']):
                if after['index'] != 1:
                    self.assertAlmostEqual(after['mass_flow_kg_s'], .6 * before['mass_flow_kg_s'], places=14)

    def test_selection_identity_covers_request_package_reader_and_candidate(self):
        r = replay.read_pressure_fin_replay()
        p = r['provenance']
        identity = {key: p[key] for key in ('selection', 'package_manifest_sha256', 'reader_source_sha256', 'candidate_sha256')}
        expected = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        self.assertEqual(p['selection_sha256'], expected)
        self.assertEqual(p['package_manifest_sha256'], replay.EXPECTED_MANIFEST_SHA256)
        different = replay.read_pressure_fin_replay(heat_load_W=40)
        self.assertNotEqual(expected, different['provenance']['selection_sha256'])
        self.assertEqual(p['source_model_sha256'], '24e1603c895e1f268a8aadcbc58a520fef606c108738d98f73898d89f873c08c')
        self.assertEqual(p['presweep_plan_sha256'], 'd517e0a8f6d3ee3ff0dd90783024ed7db8464e810f0479c1c8b6e2721586c29f')

    def test_reader_uses_verified_bytes_without_reopening_payload_files(self):
        from research.pressure_fin.audit_package import audit
        accepted = audit(replay.ROOT, expected_manifest_sha256=replay.EXPECTED_MANIFEST_SHA256, return_verified_records=True)
        with patch('research.pressure_fin.audit_package.audit', return_value=accepted), patch.object(Path, 'read_bytes', side_effect=AssertionError('Post-audit disk read')), patch.object(Path, 'read_text', side_effect=AssertionError('Post-audit disk read')):
            self.assertEqual(replay.read_pressure_fin_replay()['selection']['design_id'], 'n16_t860')

    def test_stale_manifest_and_failed_snapshot_are_never_successful(self):
        with patch.object(replay, 'EXPECTED_MANIFEST_SHA256', '0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'stale or inconsistent'):
                replay.read_pressure_fin_replay()
        with patch('research.pressure_fin.audit_package.audit', side_effect=ValueError('source/result arithmetic mismatch')):
            with self.assertRaisesRegex(RuntimeError, 'stale or inconsistent'):
                replay.read_pressure_fin_replay()

    def test_strict_bounded_discrete_inputs(self):
        for values in [('bogus', 'nominal', 60), (None, 'nominal', 60), ('n16_t600', [], 60), ('n16_t600', 'combined_fault', True), ('n16_t600', 'combined_fault', 60.0), ('n16_t600', 'combined_fault', '60'), ('n16_t600', 'combined_fault', 1000000)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                replay.read_pressure_fin_replay(*values)

    def test_stdlib_runtime_has_no_optional_solver_import(self):
        code = "import sys; from aerolab.pressure_fin_replay import read_pressure_fin_replay; r=read_pressure_fin_replay(); assert r['live_computation'] is False; assert not any(x.split('.')[0] in {'numpy','scipy','matplotlib'} for x in sys.modules); print('stdlib saved replay passed')"
        env = {key: value for key, value in os.environ.items() if key != 'PYTHONDONTWRITEBYTECODE'}
        result = subprocess.run([sys.executable, '-S', '-c', code], cwd=replay.ROOT, env=env, check=True, text=True, capture_output=True)
        self.assertIn('stdlib saved replay passed', result.stdout)


class PressureFinReplayApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self, method, path, body=None):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=30)
        c.request(method, path, body=body)
        r = c.getresponse(); data = r.read(); status, headers = r.status, r.headers; c.close()
        return status, data, headers

    def test_get_selection_matches_saved_record_and_live_post_is_unsupported(self):
        status, data, headers = self.request('GET', '/api/physics/tradeoff?design_id=n16_t600&case_id=combined_fault&heat_load_W=40')
        self.assertEqual(status, 200)
        self.assertLess(len(data), 100_000)
        r = json.loads(data)
        self.assertEqual(r['selection'], {'design_id': 'n16_t600', 'case_id': 'combined_fault', 'heat_load_W': 40})
        self.assertFalse(r['live_computation'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(self.request('POST', '/api/physics/tradeoff', '{}')[0], 404)

    def test_default_get_accepts_empty_query_on_supported_python_versions(self):
        for path in ('/api/physics/tradeoff', '/api/physics/tradeoff?'):
            with self.subTest(path=path):
                status, data, _ = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(data)['selection'],
                                 {'design_id': 'n16_t860', 'case_id': 'combined_fault', 'heat_load_W': 60})

    def test_unknown_duplicate_blank_and_nonpreset_queries_are_rejected(self):
        for query in ['bogus=x', 'design_id=n16_t600&design_id=n16_t860', 'heat_load_W=60.0', 'heat_load_W=61', 'heat_load_W=', 'case_id=', 'design_id=..%2F..%2F', 'heat_load_W=60&case_id=nominal&design_id=n16_t600&extra=1', 'heat_load_W', 'heat_load_W=NaN']:
            with self.subTest(query=query):
                self.assertEqual(self.request('GET', '/api/physics/tradeoff?' + query)[0], 400)

    def test_stale_package_returns_503_without_unverified_payload(self):
        with patch.object(replay, 'EXPECTED_MANIFEST_SHA256', '0' * 64):
            status, data, _ = self.request('GET', '/api/physics/tradeoff')
        self.assertEqual(status, 503)
        self.assertEqual(set(json.loads(data)), {'error'})

    def test_consolidated_page_assets_and_distinct_replay_controls(self):
        for path, mime in [('/physics', 'text/html'), ('/tradeoff.js', 'text/javascript'), ('/tradeoff.css', 'text/css')]:
            status, data, headers = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertIn(mime, headers['Content-Type'])
            self.assertNotIn(b'cdn.', data)
        html = self.request('GET', '/physics')[1].decode()
        for value in ('id="tab-tradeoff"', 'id="panel-tradeoff"', 'id="live-toolbar"', 'id="tradeoff-export"', 'id="tradeoff-requirement"'):
            self.assertIn(value, html)


if __name__ == '__main__':
    unittest.main()
