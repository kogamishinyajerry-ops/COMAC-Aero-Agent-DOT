"""Saved-evidence and HTTP regression checks; no numerical/CAD dependencies."""
import base64
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urljoin

from aerolab import agent_replay as replay
from aerolab.server import Handler


class AgentReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = replay.read_agent_replay()

    def test_truthful_execution_and_independent_grade(self):
        data = self.payload
        self.assertEqual(data["schema"], "native_agent_replay_v1")
        self.assertEqual(data["execution"], "recorded_native_assistant_trial")
        self.assertIs(data["live_computation"], False)
        self.assertEqual(data["provenance"]["native_runtime_model_identity"], "unverified")
        grade = data["independent_grade"]
        self.assertEqual(grade["result"], "PASS")
        self.assertEqual(len(grade["checks"]), 23)
        self.assertTrue(all(grade["checks"].values()))
        self.assertTrue(grade["limitations"])

    def test_both_fixed_tasks_and_recorded_actions(self):
        for name, expected in (("development", (11, 7, 2, "n16_t600", 30)),
                               ("heldout", (17, 13, 4, "n12_t600", 25))):
            with self.subTest(run=name):
                run = self.payload["runs"][name]
                actions, solves, cases, selected, mass_cap = expected
                self.assertEqual(len(run["events"]), actions)
                self.assertEqual(len(run["evaluations"]), solves)
                self.assertEqual(len(run["task"]["cases"]), cases)
                self.assertEqual(run["task"]["max_fin_mass_g"], mass_cap)
                self.assertEqual(run["final"]["selected_design_id"], selected)
                self.assertIs(run["final"]["physical_validation_pass"], None)
                self.assertIs(run["final"]["global_optimum_established"], False)
                self.assertEqual(run["audit"]["saved_solver_records_checked"], solves)
                self.assertEqual(run["audit"]["status"], "passed")
                for action in run["events"]:
                    raw = json.loads((replay.TRIAL_ROOT / action["event_href"].removeprefix(replay.EVIDENCE_PREFIX)).read_bytes())
                    self.assertEqual({k: action[k] for k in raw}, raw)

    def test_candidates_and_rejected_evaluations_remain_visible(self):
        for name, run in self.payload["runs"].items():
            self.assertEqual(len(run["candidates"]), 9)
            self.assertEqual(sum(c["evaluated"] for c in run["candidates"]), 2)
            self.assertEqual(sum(c["selected"] for c in run["candidates"]), 1)
            rejects = [row for row in run["evaluations"] if not row["conditional_pass"]]
            self.assertEqual(len(rejects), 1)
            self.assertFalse(rejects[0]["condition_gates"]["fin_mass"])
            self.assertTrue(rejects[0]["condition_gates"]["base_temperature"])
            if name == "heldout":
                self.assertEqual(rejects[0]["design_id"], "n16_t600")
                self.assertAlmostEqual(rejects[0]["fin_only_mass_g"], 26.36064)
            selected = run["final"]["selected_design_id"]
            for case in run["task"]["cases"]:
                rows = [r for r in run["evaluations"] if r["design_id"] == selected and r["case_id"] == case["case_id"]]
                self.assertEqual({r["mesh_id"] for r in rows}, {"primary", "spatial", "axial"})
                self.assertTrue(all(r["conditional_pass"] for r in rows))

    def test_numbers_come_from_saved_results(self):
        for run in self.payload["runs"].values():
            for row in run["evaluations"]:
                record = json.loads((replay.TRIAL_ROOT / row["source_href"].removeprefix(replay.EVIDENCE_PREFIX)).read_bytes())
                self.assertEqual(row["required_uniform_base_temperature_C"], record["required_uniform_base_temperature_C"])
                self.assertEqual(row["G_W_K"], record["result"]["G_W_K"])
                self.assertEqual(row["mesh"], record["result"]["mesh"])
                self.assertEqual(row["fin_only_mass_g"], record["result"]["fin_only_mass_kg"] * 1000)
                self.assertEqual(row["recorded_execution"], "live_frozen_PDE_solve")
                self.assertFalse(row["live_computation"])

    def test_cad_downloads_and_previews_match_frozen_bytes(self):
        for run in self.payload["runs"].values():
            cad = run["cad"]
            for kind, download in cad["downloads"].items():
                raw, mime, _ = replay.read_agent_evidence(download["href"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), download["sha256"])
                self.assertEqual(len(raw), download["bytes"])
                self.assertEqual(mime, "model/" + kind)
            raw, mime, _ = replay.read_agent_evidence(cad["preview_href"])
            self.assertEqual(mime, "image/svg+xml")
            self.assertEqual(hashlib.sha256(raw).hexdigest(), cad["preview_sha256"])

    def test_replay_never_invokes_live_tools_or_changes_saved_files(self):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in replay.TRIAL_ROOT.rglob("*") if p.is_file()}
        with patch("aerolab.agent_trial.evaluate", side_effect=AssertionError("live solve")), \
             patch("aerolab.agent_trial.cad", side_effect=AssertionError("live CAD")), \
             patch("aerolab.agent_trial.inspect_tool", side_effect=AssertionError("live inspect")), \
             patch("aerolab.agent_trial.finalize", side_effect=AssertionError("live finalize")):
            replay.read_agent_replay()
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in replay.TRIAL_ROOT.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_runs_under_stdlib_only_and_does_not_load_numeric_dependencies(self):
        code = ("import sys; from aerolab.agent_replay import read_agent_replay; read_agent_replay(); "
                "assert not any(n in sys.modules for n in ('numpy','scipy','cadquery')); print('verified')")
        result = subprocess.run([sys.executable, "-S", "-c", code], cwd=replay.ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "verified")

    def test_optimized_python_fails_closed(self):
        result = subprocess.run([sys.executable, "-S", "-O", "-c",
                                 "from aerolab.agent_replay import read_agent_replay; read_agent_replay()"],
                                cwd=replay.ROOT, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("verification failed", result.stderr)

    def test_tampered_evidence_fails_without_stale_cached_pass(self):
        names = ("runs/development/task.json", "runs/heldout/results/004_evaluate.json",
                 "runs/development/events/001.json", "heldout_independent_grade.json",
                 "report/evidence-audit.json", "report/n16_t600.step",
                 "report/native-agent-evidence.html", "runs/heldout/cad/016_n12_t600/n12_t600.svg",
                 "runs/development/cad/010_n16_t600/n16_t600.step.gz.part000")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "trial"
            shutil.copytree(replay.TRIAL_ROOT, root)
            with patch.object(replay, "TRIAL_ROOT", root):
                replay.read_agent_replay()
                for name in names:
                    with self.subTest(file=name):
                        file = root / name
                        original = file.read_bytes()
                        file.write_bytes(original + b" ")
                        with self.assertRaisesRegex(RuntimeError, "verification failed"):
                            replay.read_agent_replay()
                        file.write_bytes(original)

    def test_record_path_injection_rejected_before_existing_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "trial"
            shutil.copytree(replay.TRIAL_ROOT, root)
            path = root / "runs/development/events/001.json"
            record = json.loads(path.read_bytes())
            record["result_file"] = "../../../../private/secret.json"
            path.write_text(json.dumps(record))
            with patch.object(replay, "TRIAL_ROOT", root), patch("scripts.verify_native_agent_trial.verify") as verify:
                with self.assertRaisesRegex(RuntimeError, "verification failed"):
                    replay.read_agent_replay()
                verify.assert_not_called()

    def test_symlinked_evidence_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "trial"
            shutil.copytree(replay.TRIAL_ROOT, root)
            path = root / "runs/development/task.json"
            path.unlink()
            try:
                path.symlink_to(replay.TRIAL_ROOT / "runs/development/task.json")
            except (OSError, NotImplementedError):
                self.skipTest("Platform does not permit symlinks")
            with patch.object(replay, "TRIAL_ROOT", root):
                with self.assertRaisesRegex(RuntimeError, "verification failed"):
                    replay.read_agent_replay()

    def test_exact_allowlist_rejects_private_code_and_traversal_without_reads(self):
        names = ("../protocol.json", "%2e%2e/protocol.json", "report/../../heldout_independent_grade.json",
                 "runs/heldout/staged/study/pressure_fin.py", "heldout_private/reference.json",
                 "/etc/passwd", "report\\native-agent-evidence.html", "report/build_report.py",
                 "report/native-agent-evidence.html?download=1")
        with patch.object(replay, "_verified", side_effect=AssertionError("should reject before reading")):
            for name in names:
                with self.subTest(path=name), self.assertRaises(ValueError):
                    replay.read_agent_evidence(replay.EVIDENCE_PREFIX + name)

    def test_report_links_are_allowlisted_and_csp_approves_only_exact_style(self):
        url = self.payload["links"]["report"]
        raw, _, csp = replay.read_agent_evidence(url)
        styles = re.findall(rb"<style>(.*?)</style>", raw, re.DOTALL)
        digest = base64.b64encode(hashlib.sha256(styles[0]).digest()).decode("ascii")
        self.assertIn("'sha256-" + digest + "'", csp)
        self.assertNotIn("unsafe-inline", csp)
        for href in re.findall(r'(?:href|src)="([^"]+)"', raw.decode()):
            if href.startswith("data:"):
                continue
            resolved = urljoin(url, href)
            self.assertTrue(resolved.startswith(replay.EVIDENCE_PREFIX))
            self.assertIn(resolved.removeprefix(replay.EVIDENCE_PREFIX), replay.PUBLIC_FILES)


class AgentReplayHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class QuietHandler(Handler):
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, method="GET"):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=15)
        conn.request(method, path)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, raw, response.headers

    def test_api_and_raw_grade(self):
        status, raw, headers = self.request("/api/agent/replay")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw)["live_computation"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Content-Security-Policy"], replay.BASE_CSP)
        status, raw, _ = self.request("/agent/evidence/heldout_independent_grade.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["result"], "PASS")

    def test_new_routes_and_original_home(self):
        # UI belongs to a separate author; exercise routing with private fixtures.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web").mkdir()
            for name in ("index.html", "agent.html", "agent.js", "agent.css"):
                (root / "web" / name).write_text(name)
            with patch("aerolab.server.ROOT", root):
                for path, expected, mime in (("/", "index.html", "text/html"),
                        ("/agent", "agent.html", "text/html"), ("/agent.html", "agent.html", "text/html"),
                        ("/agent.js", "agent.js", "text/javascript"), ("/agent.css", "agent.css", "text/css")):
                    with self.subTest(path=path):
                        status, raw, headers = self.request(path)
                        self.assertEqual(status, 200)
                        self.assertEqual(raw.decode(), expected)
                        self.assertTrue(headers["Content-Type"].startswith(mime))
                        self.assertNotIn("sha256-", headers["Content-Security-Policy"])

    def test_unknown_parameters_and_mutations_rejected(self):
        for path in ("/api/agent/replay?run=heldout", "/api/agent/replay?x=", "/api/agent/replay;anything",
                     "/agent?live=true", "/agent.js?x=1", "/agent.css?x=1",
                     "/agent/evidence/protocol.json?path=private", "/agent/evidence/protocol.json;anything"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 400)
        self.assertEqual(self.request("/api/agent/replay", "POST")[0], 404)

    def test_http_private_files_and_traversal_rejected(self):
        for path in ("/agent/evidence/../protocol.json", "/agent/evidence/%2e%2e/protocol.json",
                     "/agent/evidence/runs/heldout/staged/study/pressure_fin.py",
                     "/agent/evidence/private/reference.json", "/agent/evidence/report/build_report.py",
                     "/agent/evidence//protocol.json", "/research/native_agent_trial/heldout_task.json"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_verification_failure_is_503_without_partial_evidence(self):
        with patch.object(replay, "TRIAL_ROOT", Path("/no-such-agent-evidence")):
            for path in ("/api/agent/replay", "/agent/evidence/report/n12_t600.step"):
                status, raw, _ = self.request(path)
                self.assertEqual(status, 503)
                self.assertIn("verification failed", json.loads(raw)["error"])
                self.assertNotIn("no-such-agent-evidence", raw.decode())

    def test_report_csp_is_specific_to_verified_report(self):
        status, _, headers = self.request("/agent/evidence/report/native-agent-evidence.html")
        self.assertEqual(status, 200)
        self.assertIn("sha256-", headers["Content-Security-Policy"])
        self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])
        _, _, headers = self.request("/api/agent/replay")
        self.assertEqual(headers["Content-Security-Policy"], replay.BASE_CSP)


if __name__ == "__main__":
    unittest.main()
