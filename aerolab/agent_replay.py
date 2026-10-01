"""Read-only, standard-library view of the completed native-assistant trial.

This adapter verifies saved evidence. It never invokes an assistant, numerical
solver, CAD kernel, external API, or private evaluator. Original evidence files
are not rewritten. Hashes establish local consistency, not signed provenance.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
TRIAL_ROOT = ROOT / "research/native_agent_trial"
EVIDENCE_PREFIX = "/agent/evidence/"
REPORT = "report/native-agent-evidence.html"
AUDIT_SHA256 = "e52f83a5d85c145ff3d65fa3475334ee82df59fc04e4a0c41f2686545a6358a0"
PINNED = {
    "report/evidence-audit.json": AUDIT_SHA256,
    "heldout_execution_declaration.json": "67c5fd10479a64abe987547cc95514b8ee83fe7e98fe9f60f27e2299eb6fe365",
    "heldout_executor_declaration.json": "6859f3962a6ca4060fc223f64817c82428f4940a50a2b3236295fa407f4414f7",
    "HELDOUT_EVALUATION.md": "dac0fa7bba80d0640bbe12a9561b089f6c1c275a7086f5fbf8f904c9e916d24a",
}
RUNS = {"development": (11, "n16_t600"), "heldout": (17, "n12_t600")}
BASE_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")


def _operation(sequence, count):
    return {1: "init", 2: "inspect", count - 1: "cad", count: "finalize"}.get(sequence, "evaluate")


def _public_files():
    """An exact allowlist, never a filesystem route or a caller-supplied glob."""
    files = {name: "application/json; charset=utf-8" for name in (
        "protocol.json", "report/evidence-audit.json", "heldout_independent_grade.json",
        "heldout_execution_declaration.json", "heldout_executor_declaration.json")}
    files.update({REPORT: "text/html; charset=utf-8", "HELDOUT_EVALUATION.md": "text/plain; charset=utf-8"})
    for run, (count, design) in RUNS.items():
        prefix = f"runs/{run}"
        for name in ("task.json", "session.json"):
            files[f"{prefix}/{name}"] = "application/json; charset=utf-8"
        for sequence in range(1, count + 1):
            files[f"{prefix}/events/{sequence:03d}.json"] = "application/json; charset=utf-8"
            files[f"{prefix}/results/{sequence:03d}_{_operation(sequence, count)}.json"] = "application/json; charset=utf-8"
        files[f"{prefix}/cad/{count - 1:03d}_{design}/{design}.svg"] = "image/svg+xml"
        for kind, mime in (("step", "model/step"), ("stl", "model/stl")):
            files[f"report/{design}.{kind}"] = mime
    return files


PUBLIC_FILES = _public_files()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _safe_read(relative, limit=250000):
    """Reject traversal and symlinks before the existing verifier follows paths."""
    path = PurePosixPath(relative)
    _require(isinstance(relative, str) and not path.is_absolute()
             and str(path) == relative and not any(p in (".", "..") for p in path.parts)
             and not any(c in relative for c in ("\\", "%", "\x00")), "Invalid evidence path")
    root = TRIAL_ROOT.resolve()
    target = TRIAL_ROOT
    _require(not target.is_symlink(), "Evidence root cannot be a symlink")
    for part in path.parts:
        target = target / part
        _require(not target.is_symlink(), "Evidence symlinks are not allowed")
    _require(target.resolve().is_relative_to(root), "Evidence path escapes root")
    _require(target.is_file() and target.stat().st_size <= limit, "Evidence file missing or too large")
    raw = target.read_bytes()
    _require(len(raw) <= limit, "Evidence file too large")
    return raw


def _decode(raw):
    def reject_constant(value):
        raise ValueError("Non-finite evidence JSON")
    return json.loads(raw, parse_constant=reject_constant)


def _href(relative):
    return EVIDENCE_PREFIX + relative


def _load_verified():
    # The existing independent saved-evidence verifier uses assertions. Fail
    # closed under -O instead of silently skipping its arithmetic checks.
    _require(__debug__, "Evidence verification requires Python without -O")
    from scripts.verify_native_agent_trial import verify
    from .agent_trial import MODEL_PATHS, MODEL_SHAS, PROTOCOL_SHA

    blobs = {name: _safe_read(name, 99999 if name.endswith(".json") else 250000)
             for name in PUBLIC_FILES}
    for name, expected in PINNED.items():
        _require(_sha(blobs[name]) == expected, "Frozen evidence fingerprint mismatch")
    manifest = _decode(blobs["report/evidence-audit.json"])
    _require(_sha(blobs[REPORT]) == manifest["html_sha256"], "Report fingerprint mismatch")
    _require(_sha(blobs["protocol.json"]) == PROTOCOL_SHA, "Protocol fingerprint mismatch")
    _require(_sha(blobs["heldout_independent_grade.json"]) == manifest["independent_grade_sha256"],
             "Independent grade fingerprint mismatch")
    grade = _decode(blobs["heldout_independent_grade.json"])
    protocol = _decode(blobs["protocol.json"])
    runs = {}
    for run, (count, design) in RUNS.items():
        prefix = f"runs/{run}"
        saved_audit = next(a for a in manifest["runs"] if a["run"] == run)
        _require(saved_audit["events"] == count, "Event count mismatch")
        session = TRIAL_ROOT / prefix
        # Only known completed session files may be followed by the verifier.
        expected_events = {f"{n:03d}.json" for n in range(1, count + 1)}
        _require({p.name for p in (session / "events").glob("*.json")} == expected_events,
                 "Unexpected event files")
        for source, expected in zip(MODEL_PATHS, MODEL_SHAS):
            rel = str(PurePosixPath(source).relative_to("research/pressure_fin/original_freeze"))
            _require(_sha(_safe_read(f"{prefix}/staged/{rel}")) == expected, "Staged source mismatch")
        chain = []
        evaluations = []
        previous = None
        cad = None
        inspect = None
        final = None
        for sequence in range(1, count + 1):
            operation = _operation(sequence, count)
            event_name = f"{prefix}/events/{sequence:03d}.json"
            result_rel = f"results/{sequence:03d}_{operation}.json"
            result_name = f"{prefix}/{result_rel}"
            event = _decode(blobs[event_name])
            _require(event["sequence"] == sequence and event["operation"] == operation
                     and event["result_file"] == result_rel, "Unexpected recorded action path")
            _require(event["previous_event_sha256"] == previous, "Event chain mismatch")
            _require(event["result_sha256"] == _sha(blobs[result_name]), "Result fingerprint mismatch")
            previous = _sha(blobs[event_name])
            record = _decode(blobs[result_name])
            chain.append({**event, "event_href": _href(event_name), "result_href": _href(result_name)})
            if operation == "inspect":
                inspect = record
            elif operation == "evaluate":
                result = record["result"]
                evaluations.append({
                    "sequence": sequence, "design_id": record["design_id"], "case_id": record["case_id"],
                    "mesh_id": record["mesh_id"], "mesh": result["mesh"],
                    "fin_only_mass_g": result["fin_only_mass_kg"] * 1000,
                    **{key: record[key] for key in ("required_uniform_base_temperature_C", "temperature_margin_C",
                       "fin_mass_margin_g", "condition_gates", "numerical_gates", "conditional_pass",
                       "physical_validation_pass", "aircraft_transfer_authorized", "requirements")},
                    **{key: result[key] for key in ("G_W_K", "max_Re_Dh", "volume_flow_m3_s", "pressure_Pa")},
                    "recorded_execution": record["execution"], "live_computation": False,
                    "source_href": _href(result_name), "result_sha256": event["result_sha256"],
                })
            elif operation == "cad":
                _require(record["design_id"] == design, "Unexpected CAD design")
                preview = f"cad/{sequence:03d}_{design}/{design}.svg"
                _require(record["preview_file"] == preview, "Unexpected CAD preview path")
                _require(_sha(blobs[f"{prefix}/{preview}"]) == record["preview_sha256"], "CAD preview fingerprint mismatch")
                downloads = {}
                for kind in ("step", "stl"):
                    artifact = record["artifacts"][kind]
                    # Both frozen exports have exactly one chunk. Do not accept
                    # record-supplied filenames outside that exact public run.
                    chunk = f"cad/{sequence:03d}_{design}/{design}.{kind}.gz.part000"
                    _require(len(artifact["chunks"]) == 1 and artifact["chunks"][0]["file"] == chunk,
                             "Unexpected CAD chunk path")
                    _safe_read(f"{prefix}/{chunk}")
                    export = f"report/{design}.{kind}"
                    _require(_sha(blobs[export]) == artifact["raw_sha256"]
                             and len(blobs[export]) == artifact["raw_bytes"], "CAD download fingerprint mismatch")
                    downloads[kind] = {"href": _href(export), "sha256": artifact["raw_sha256"],
                                       "bytes": artifact["raw_bytes"]}
                cad = {**record, "source_href": _href(result_name), "preview_href": _href(f"{prefix}/{preview}"),
                       "downloads": downloads}
            elif operation == "finalize":
                final = record
                expected = (manifest["development_final_result_sha256"] if run == "development"
                            else grade["terminal_result_sha256"])
                _require(_sha(blobs[result_name]) == expected, "Terminal fingerprint mismatch")
        _require(previous == saved_audit["last_event_sha256"], "Frozen event chain head mismatch")
        audit = verify(session)
        task = _decode(blobs[f"{prefix}/task.json"])
        metadata = _decode(blobs[f"{prefix}/session.json"])
        _require(inspect["task"] == task and final["selected_design_id"] == design, "Trial summary mismatch")
        candidates = []
        for candidate in inspect["candidates"]:
            rows = [r for r in evaluations if r["design_id"] == candidate["design_id"]]
            candidates.append({**candidate, "selected": candidate["design_id"] == design,
                "evaluated": bool(rows), "evaluation_count": len(rows),
                "screen_pass": candidate["mass_requirement_pass"] and all(r["within_Re_scope"] for r in candidate["hydraulic_screen"]),
                "failed_gates": sorted({key for row in rows for key, value in row["condition_gates"].items() if not value}),
            })
        runs[run] = {"id": run, "task": task, "session": metadata, "audit": audit,
            "candidates": candidates, "candidate_screen_warning": inspect["warning"],
            "evaluations": evaluations, "events": chain, "final": final, "cad": cad,
            "links": {"task": _href(f"{prefix}/task.json"), "session": _href(f"{prefix}/session.json"),
                      "final": _href(f"{prefix}/results/{count:03d}_finalize.json")}}
    _require(grade["task_sha256"] == runs["heldout"]["session"]["task_sha256"]
             and grade["trace_head_sha256"] == _sha(blobs["runs/heldout/events/017.json"])
             and grade["selected_design_id"] == runs["heldout"]["final"]["selected_design_id"],
             "Independent grade identity mismatch")
    payload = {
        "schema": "native_agent_replay_v1", "execution": "recorded_native_assistant_trial", "live_computation": False,
        "protocol": protocol, "runs": runs, "independent_grade": grade,
        "provenance": {
            "verification": "passed", "report_audit_sha256": AUDIT_SHA256,
            "native_runtime_model_identity": runs["heldout"]["session"]["native_runtime_model_identity"],
            "execution_declaration": _decode(blobs["heldout_execution_declaration.json"]),
            "executor_declaration": _decode(blobs["heldout_executor_declaration.json"]),
            "scope": "Recorded assistant decisions and actual tool results; this request only verifies saved evidence. "
                     "No fresh assistant reasoning, PDE solve, CAD generation or physical validation. "
                     "Local hashes are consistency checks, not signatures or model-identity attestations.",
        },
        "links": {"report": _href(REPORT), "protocol": _href("protocol.json"),
                  "audit": _href("report/evidence-audit.json"),
                  "independent_grade": _href("heldout_independent_grade.json"),
                  "independent_evaluation": _href("HELDOUT_EVALUATION.md")},
    }
    return payload, blobs


def _verified():
    try:
        return _load_verified()
    except (OSError, ValueError, AssertionError, KeyError, TypeError, StopIteration, IndexError) as exc:
        # Never expose local paths or untrusted exception detail to a browser.
        raise RuntimeError("Native-agent replay evidence verification failed; no result is served") from exc


def read_agent_replay():
    """Return newly verified, JSON-serializable saved evidence; no cached pass."""
    return _verified()[0]


def read_agent_evidence(path):
    """Return (bytes, MIME type, CSP) for one exact same-server evidence URL."""
    if not isinstance(path, str) or not path.startswith(EVIDENCE_PREFIX):
        raise ValueError("Unknown evidence file")
    relative = path[len(EVIDENCE_PREFIX):]
    if relative not in PUBLIC_FILES:
        raise ValueError("Unknown evidence file")
    _, blobs = _verified()
    raw = blobs[relative]
    csp = BASE_CSP
    if relative == REPORT:
        # A single immutable report stylesheet is approved by hash. No unsafe
        # inline scripts/styles and no relaxation for any other app response.
        styles = re.findall(rb"<style>(.*?)</style>", raw, re.DOTALL)
        if len(styles) != 1:
            raise RuntimeError("Unexpected frozen report stylesheet")
        digest = base64.b64encode(hashlib.sha256(styles[0]).digest()).decode("ascii")
        csp = csp.replace("style-src 'self'", f"style-src 'self' 'sha256-{digest}'")
    return raw, PUBLIC_FILES[relative], csp
