"""Dependency-free, integrity-checked reader for the qualified experiment replay.

This module does not import NumPy/SciPy or rerun the research solver. It verifies
the packaged source/results, preserves the original precomparison freeze, and
checks displayed arithmetic. Hash consistency is not physical validation.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DATA_PREFIX = "examples/rectangular_experiment/"
RESEARCH_PREFIX = "research/rectangular_duct/"
SOURCE_DATA_PATH = RESEARCH_PREFIX + "inputs/experimental_source.json"
MANIFEST_PATH = DATA_PREFIX + "package_manifest.json"
EXPECTED_MANIFEST_SHA256 = "e4bc237ce84588f81bc2ebd17189449007523121a8edbe14a6849413bd210883"
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _reject_constant(value):
    raise ValueError("Non-finite JSON constant: " + value)


def _json(data):
    if len(data) >= 100_000:
        raise ValueError("Research JSON exceeds the bounded artifact contract")
    return json.loads(data, parse_constant=_reject_constant)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Research arithmetic requires finite numeric values")
    return float(value)


def _same(a, b):
    if not math.isclose(_number(a), _number(b), abs_tol=1e-12, rel_tol=1e-11):
        raise ValueError("Research displayed arithmetic does not reproduce")


def _verified_package(root):
    root = Path(root).resolve()
    manifest_path = root / MANIFEST_PATH
    if manifest_path.stat().st_size >= 100_000:
        raise ValueError("Research manifest exceeds its size limit")
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha != EXPECTED_MANIFEST_SHA256:
        raise ValueError("Research package manifest identity differs from this reader")
    manifest = _json(manifest_bytes)
    if (manifest["all_audits_passed"] is not True
            or manifest["physical_validation_pass"] is not None
            or manifest["aircraft_transfer_authorized"] is not False
            or manifest["application_dependencies_added"] is not False):
        raise ValueError("Research package scope or acceptance is inconsistent")
    records = {}
    total = 0
    for item in manifest["files"]:
        name = item["proposed_repository_path"]
        relative = PurePosixPath(name)
        if (relative.is_absolute() or ".." in relative.parts or name in records
                or not name.startswith((DATA_PREFIX, RESEARCH_PREFIX))):
            raise ValueError("Invalid research artifact path")
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Research artifact missing or outside package")
        if path.stat().st_size > 250_000 or path.stat().st_size != item["bytes"]:
            raise ValueError("Research artifact size differs from manifest")
        data = path.read_bytes()
        if len(data) > 250_000 or len(data) != item["bytes"]:
            raise ValueError("Research artifact size differs from manifest")
        digest = hashlib.sha256(data).hexdigest()
        if digest != item["sha256"]:
            raise ValueError("Research artifact content differs from manifest: " + name)
        records[name] = {"bytes": data, "sha256": digest}
        total += len(data)
    if len(records) != manifest["files_count"] or total != manifest["total_listed_bytes"]:
        raise ValueError("Research package inventory is incomplete")
    return manifest, manifest_sha, records


def _verify_arithmetic(comparison, source):
    rows = comparison["rows"]
    if comparison["count"] != 32 or len(rows) != 32 or len({r["id"] for r in rows}) != 32:
        raise ValueError("Expected all 32 distinct experimental records")
    source_rows = []
    for group in source["groups"]:
        for row in group["rows"]:
            source_rows.append((group["length_inches"], row))
    if len(source_rows) != len(rows):
        raise ValueError("Source and comparison row counts differ")
    residuals = []
    for row, (length, values) in zip(rows, source_rows):
        re, gz, tin, tout, tw, printed_nu = values
        if row["Re"] != re or row["length_inches"] != length:
            raise ValueError("Missing or recorded source values were altered")
        for name, expected in (("Gz", gz), ("Tin_F", tin), ("Tout_F", tout), ("Tw_F", tw), ("printed_Nu", printed_nu)):
            _same(row[name], expected)
        if not tin < tout < tw or _number(gz) <= 0:
            raise ValueError("Unexpected source heating or flow condition")
        observed = (tw - tout) / (tw - tin)
        predicted = _number(row["predicted_bulk_theta"])
        if not 0 <= predicted <= 1:
            raise ValueError("Predicted attenuation is inadmissible")
        residual = predicted - observed
        _same(row["observed_bulk_theta"], observed)
        _same(row["residual_theta_prediction_minus_observation"], residual)
        _same(row["tau"], (4 / 3) ** 2 / gz)
        residuals.append(residual)
    if sum(row["Re"] is None for row in rows) != 8:
        raise ValueError("Original missing Reynolds values must remain missing")
    _same(comparison["all_rows_mean_absolute_residual_theta"], math.fsum(abs(r) for r in residuals) / 32)
    _same(comparison["all_rows_maximum_absolute_residual_theta"], max(map(abs, residuals)))
    if {g["length_inches"] for g in comparison["groups"]} != {24, 13, 7.5}:
        raise ValueError("Experimental group definitions changed")
    for group in comparison["groups"]:
        values = [r["residual_theta_prediction_minus_observation"] for r in rows if r["length_inches"] == group["length_inches"]]
        if len(values) != group["count"]:
            raise ValueError("Experimental group count differs")
        _same(group["mean_absolute_residual_theta"], math.fsum(map(abs, values)) / len(values))
        _same(group["minimum_residual_theta"], min(values))
        _same(group["maximum_residual_theta"], max(values))


def read_experimental_evidence(root=ROOT):
    """Verify files and arithmetic, then return a bounded, explicitly saved replay."""
    try:
        manifest, manifest_sha, records = _verified_package(root)
        def data(name):
            return _json(records[DATA_PREFIX + name]["bytes"])
        comparison = data("experimental_comparison.json")
        source = _json(records[SOURCE_DATA_PATH]["bytes"])
        verification = data("verification.json")
        frozen = data("frozen_response.json")
        replay = data("packaging_replay.json")
        index = data("replay_index.json")
        independent = data("independent_continuum_comparison.json")
        if (comparison["physical_validation_pass"] is not None
                or verification["all_passed"] is not True
                or verification["experiment_used_for_selection"] is not False
                or not verification["gates"] or any(v is not True for v in verification["gates"].values())
                or frozen["all_mathematical_gates_passed"] is not True
                or frozen["experiment_used_for_selection"] is not False
                or replay["all_passed"] is not True or any(v is not True for v in replay["checks"].values())
                or replay["equations_grids_and_tolerances_changed"] is not False
                or index["live_computation"] is not False):
            raise ValueError("Research replay does not meet its stated mathematical/scope gates")
        solver_sha = records[RESEARCH_PREFIX + "rectangular_graetz.py"]["sha256"]
        if any(obj["provenance"]["code_sha256"] != solver_sha for obj in (comparison, verification, frozen)):
            raise ValueError("Research result and solver identities differ")
        links = ((comparison["frozen_response_sha256"], DATA_PREFIX + "frozen_response.json"),
                 (comparison["source_transcription_sha256"], SOURCE_DATA_PATH),
                 (frozen["verification_sha256"], DATA_PREFIX + "verification.json"),
                 (replay["packaged_verification_sha256"], DATA_PREFIX + "verification.json"),
                 (replay["packaged_frozen_response_sha256"], DATA_PREFIX + "frozen_response.json"),
                 (replay["packaged_experimental_comparison_sha256"], DATA_PREFIX + "experimental_comparison.json"))
        if any(expected != records[name]["sha256"] for expected, name in links):
            raise ValueError("Research provenance chain is inconsistent")
        for name, expected in manifest["original_freeze_anchors"].items():
            if records[RESEARCH_PREFIX + "original_freeze/" + name]["sha256"] != expected:
                raise ValueError("Original precomparison evidence was changed")
        _verify_arithmetic(comparison, source)
        result = {
            "schema": "aerolab-experiment-replay-v1", "execution": "verified_research_replay",
            "live_computation": False, "calibration_records": 0,
            "source": {"id": "wibulswas-1966-isothermal-duct", "title": index["source_title"],
                       "url": index["source_url"], "pdf_sha256": index["source_pdf_sha256"]},
            "comparison": comparison,
            "numerical": {"all_passed": True, "gates": verification["gates"],
                          "packaging_replay_verified": True,
                          "grid": {"ny": frozen["ny"], "nx": frozen["nx"]},
                          "independent_reference": independent,
                          "note": "Numerical verification and observed reference differences, not a physical-validation pass or total error bound."},
            "provenance": {"reader_source_sha256": SOURCE_SHA256,
                           "package_manifest_sha256": manifest_sha,
                           "verified_file_count": len(records),
                           "original_precomparison_frozen_response_sha256": replay["original_precomparison_frozen_response_sha256"],
                           "packaged_solver_sha256": solver_sha,
                           "packaged_comparison_sha256": records[DATA_PREFIX + "experimental_comparison.json"]["sha256"],
                           "chronology": manifest["chronology"]},
            "display_fields": data("display_fields.json"),
        }
        if len(json.dumps(result, allow_nan=False).encode()) >= 100_000:
            raise ValueError("Research replay exceeds the bounded response contract")
        return result
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise RuntimeError("Experimental research evidence is missing, stale or inconsistent; run its package audit before showing the replay") from exc
