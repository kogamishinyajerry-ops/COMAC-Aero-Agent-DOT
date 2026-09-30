"""Local physics evidence API: bounded inputs, honest scope and identities."""
from __future__ import annotations

import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch

from aerolab.physics_lab import physics_evidence, PRESETS
from aerolab.server import Handler


class PhysicsEvidenceTests(unittest.TestCase):
    def test_presets_preserve_three_distinct_scopes(self):
        for case in PRESETS:
            with self.subTest(case=case):
                r = physics_evidence(case)
                self.assertEqual(r["execution"], "computed")
                self.assertEqual(r["case"], case)
                self.assertFalse(any(r["claims"].values()))
                self.assertFalse(r["historical_motor"]["experimental_validation"])
                self.assertTrue(r["verification"]["numerical_source_matches"])
                self.assertLess(len(json.dumps(r).encode()), 100_000)
        zero = physics_evidence("zero_flow")["duct"]
        self.assertEqual(zero["status"], "no_steady_state_zero_flow")
        self.assertIsNone(zero["thermal"]["outlet_bulk_c"])
        self.assertEqual(zero["thermal"]["axial_samples"], [])

    def test_asymmetric_wall_below_bulk_is_actual_computed_result(self):
        r = physics_evidence("asymmetric")["duct"]
        self.assertGreater(r["thermal"]["wall_flux_w_m2"]["left"], 0)
        self.assertLess(r["thermal"]["outlet_wall_c"]["left"], r["thermal"]["outlet_bulk_c"])
        self.assertLess(abs(r["diagnostics"]["energy_residual_w"]), 1e-9)
        self.assertTrue(r["diagnostics"]["converged"])

    def test_stale_verification_is_not_claimed_as_valid(self):
        with patch("aerolab.physics_lab.DUCT_SOURCE_SHA256", "deliberately-stale"):
            with self.assertRaisesRegex(RuntimeError, "unavailable or stale"):
                physics_evidence()

    def test_unknown_case_rejected(self):
        for case in (None, {}, [], "unbounded", True):
            with self.subTest(case=case), self.assertRaises(ValueError):
                physics_evidence(case)


class PhysicsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=20)
        conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        status, headers = response.status, response.headers
        conn.close()
        return status, data, headers

    def test_live_evidence_and_static_page(self):
        status, data, _ = self.request("POST", "/api/physics/evaluate", {})
        self.assertEqual(status, 200)
        report = json.loads(data)
        self.assertEqual(report["schema"], "aerolab-physics-lab-v1")
        self.assertEqual(report["case"], "asymmetric")
        for path, mime in (("/physics", "text/html"), ("/physics.js", "text/javascript"), ("/physics.css", "text/css")):
            status, data, headers = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn(mime, headers["Content-Type"])
            self.assertGreater(len(data), 500)
        self.assertIn(b'/physics', self.request("GET", "/nacelle")[1])

    def test_strict_fields_and_cross_origin(self):
        for body in ({"case": "bad"}, {"case": None}, {"case": 1}, {"case": []}, {"grid": 999999}, {"geometry": {}}, []):
            with self.subTest(body=body):
                self.assertEqual(self.request("POST", "/api/physics/evaluate", body)[0], 400)
        self.assertEqual(self.request("POST", "/api/physics/evaluate", {}, {"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("GET", "/api/physics/evaluate")[0], 404)

    def test_server_discloses_stale_evidence(self):
        with patch("aerolab.physics_lab.DUCT_SOURCE_SHA256", "deliberately-stale"):
            status, data, _ = self.request("POST", "/api/physics/evaluate", {})
        self.assertEqual(status, 503)
        self.assertIn("stale", json.loads(data)["error"])


if __name__ == "__main__":
    unittest.main()
