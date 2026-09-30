import http.client
import json
import threading
from http.server import ThreadingHTTPServer
import unittest
from aerolab.server import Handler


class ServerTests(unittest.TestCase):
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
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=15)
        data = json.dumps(body) if body is not None else None
        conn.request(method, path, body=data, headers=headers or {})
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, raw, response.headers

    def test_catalog_and_replay(self):
        status, data, _ = self.request("GET", "/api/catalog")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(json.loads(data)["scenarios"]), 6)
        status, data, _ = self.request("GET", "/api/replay")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["baseline"]["meta"]["execution"], "replay")

    def test_live_compute(self):
        status, data, _ = self.request("POST", "/api/run", {"scenario_id": "nominal", "policy": "baseline"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)["summary"]["feasible"])
        self.assertEqual(json.loads(data)["meta"]["execution"], "computed")

    def test_comparison_uses_same_scenario_and_design(self):
        status, data, _ = self.request("POST", "/api/compare", {"scenario_id": "nominal"})
        result = json.loads(data)
        self.assertEqual(status, 200)
        self.assertEqual(result["baseline"]["scenario"], result["planner"]["scenario"])
        self.assertEqual(result["baseline"]["design"], result["planner"]["design"])

    def test_sweep_returns_independent_fixed_designs(self):
        status, data, _ = self.request("POST", "/api/sweep", {"scenario_id": "command_loss"})
        result = json.loads(data)
        self.assertEqual(status, 200)
        self.assertEqual(len(result["results"]), 4)
        self.assertEqual(len({r["run_id"] for r in result["results"]}), 4)
        self.assertTrue(all(r["summary"]["solver_valid"] for r in result["results"]))

    def test_unknown_fields_and_invalid_numbers(self):
        for body in ({"mass_kg": 1}, {"ambient_c": float('inf')}, {"dt_s": 0}, []):
            status, _, _ = self.request("POST", "/api/run", body)
            self.assertEqual(status, 400)

    def test_cross_origin_blocked(self):
        status, _, _ = self.request("POST", "/api/run", {}, {"Origin": "https://example.com"})
        self.assertEqual(status, 403)

    def test_arbitrary_files_not_exposed(self):
        for path in ("/aerolab/model.py", "/../README.md", "/.git/config", "/%2e%2e/README.md"):
            self.assertEqual(self.request("GET", path)[0], 404)

    def test_security_headers(self):
        _, _, headers = self.request("GET", "/api/catalog")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
