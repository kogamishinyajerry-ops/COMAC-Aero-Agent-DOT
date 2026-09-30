"""Offline standard-library experimental replay acceptance, never solver fitting."""
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

from aerolab.experimental_evidence import (ROOT, MANIFEST_PATH, SOURCE_DATA_PATH,
    EXPECTED_MANIFEST_SHA256, read_experimental_evidence, _verify_arithmetic, _verified_package, _json)
from aerolab.server import Handler


class ExperimentalEvidenceTests(unittest.TestCase):
    def test_complete_read_only_replay_has_qualified_scope(self):
        r = read_experimental_evidence()
        self.assertEqual(r["execution"], "verified_research_replay")
        self.assertFalse(r["live_computation"])
        self.assertEqual(r["calibration_records"], 0)
        self.assertIsNone(r["comparison"]["physical_validation_pass"])
        self.assertEqual(r["comparison"]["count"], 32)
        self.assertEqual(sum(x["Re"] is None for x in r["comparison"]["rows"]), 8)
        self.assertEqual(len(r["numerical"]["gates"]), 11)
        self.assertTrue(r["numerical"]["packaging_replay_verified"])
        self.assertEqual(r["provenance"]["package_manifest_sha256"], EXPECTED_MANIFEST_SHA256)
        self.assertLess(len(json.dumps(r).encode()), 100_000)

    def test_no_optional_research_dependency_required(self):
        command = "from aerolab.experimental_evidence import read_experimental_evidence; print(read_experimental_evidence()['comparison']['count'])"
        result = subprocess.run([sys.executable, "-S", "-c", command], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "32")

    def test_arithmetic_is_independently_checked(self):
        r = read_experimental_evidence()["comparison"]
        source = json.loads((ROOT / SOURCE_DATA_PATH).read_text(encoding="utf-8"))
        self.assertAlmostEqual(r["rows"][0]["observed_bulk_theta"], (143.3 - 107.5) / (143.3 - 70.0), places=14)
        for mutate in (
            lambda d: d["rows"][0].update(observed_bulk_theta=.6),
            lambda d: d["rows"][0].update(predicted_bulk_theta=float("nan")),
            lambda d: d["rows"][0].update(id=d["rows"][1]["id"]),
            lambda d: d.update(all_rows_mean_absolute_residual_theta=0),
            lambda d: d["groups"][0].update(count=11),
        ):
            changed = deepcopy(r)
            mutate(changed)
            with self.assertRaises(ValueError):
                _verify_arithmetic(changed, source)

    def test_missing_source_values_are_not_filled(self):
        r = read_experimental_evidence()["comparison"]
        source = json.loads((ROOT / SOURCE_DATA_PATH).read_text(encoding="utf-8"))
        next(row for row in r["rows"] if row["Re"] is None)["Re"] = 1000
        with self.assertRaises(ValueError):
            _verify_arithmetic(r, source)

    def test_nonfinite_json_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(ValueError):
                _json(("{\"value\":" + value + "}").encode())

    def test_manifest_change_is_not_silently_accepted(self):
        with patch("aerolab.experimental_evidence.EXPECTED_MANIFEST_SHA256", "bad"):
            with self.assertRaisesRegex(RuntimeError, "missing, stale or inconsistent"):
                read_experimental_evidence()

    def test_artifact_change_or_missing_file_is_rejected(self):
        manifest = json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = [item["proposed_repository_path"] for item in manifest["files"]] + [MANIFEST_PATH]
            for name in names:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            self.assertEqual(read_experimental_evidence(root)["comparison"]["count"], 32)
            target = root / "examples/rectangular_experiment/experimental_comparison.json"
            original = target.read_bytes()
            target.write_bytes(original.replace(b"0.4884038199181447", b"0.5884038199181447"))
            with self.assertRaises(RuntimeError):
                read_experimental_evidence(root)
            target.unlink()
            with self.assertRaises(RuntimeError):
                read_experimental_evidence(root)

    def test_paths_cannot_leave_research_package(self):
        manifest = json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))
        manifest["files"][0]["proposed_repository_path"] = "../outside.json"
        encoded = json.dumps(manifest).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / MANIFEST_PATH
            path.parent.mkdir(parents=True)
            path.write_bytes(encoded)
            with patch("aerolab.experimental_evidence.EXPECTED_MANIFEST_SHA256", hashlib.sha256(encoded).hexdigest()):
                with self.assertRaisesRegex(ValueError, "Invalid research artifact path"):
                    _verified_package(directory)


class ExperimentalApiTests(unittest.TestCase):
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

    def request(self, method, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=20)
        conn.request(method, path)
        response = conn.getresponse()
        result = response.status, response.read(), response.headers
        conn.close()
        return result

    def test_get_replay_and_ui(self):
        status, raw, _ = self.request("GET", "/api/physics/experiment")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw)["live_computation"])
        for path, mime in (("/experiments", "text/html"), ("/experiments.js", "text/javascript"), ("/experiments.css", "text/css")):
            status, raw, headers = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn(mime, headers["Content-Type"])
        self.assertIn(b'/experiments', self.request("GET", "/physics")[1])

    def test_cannot_tune_replay_from_request(self):
        self.assertEqual(self.request("GET", "/api/physics/experiment?heat_factor=2")[0], 400)
        self.assertEqual(self.request("POST", "/api/physics/experiment")[0], 404)

    def test_stale_package_gives_visible_server_error(self):
        with patch("aerolab.experimental_evidence.EXPECTED_MANIFEST_SHA256", "bad"):
            status, raw, _ = self.request("GET", "/api/physics/experiment")
        self.assertEqual(status, 503)
        self.assertIn("stale", json.loads(raw)["error"])


if __name__ == "__main__":
    unittest.main()
