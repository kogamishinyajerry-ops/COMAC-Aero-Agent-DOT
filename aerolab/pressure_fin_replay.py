"""Bounded, standard-library-only view of immutable pressure-fin research.

No numerical solver is imported. Every response audits the complete package and
uses the exact byte snapshot returned by the auditor, never reopening a record.
Heat presets select accepted records; they do not run CFD or fit coefficients.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "examples/pressure_fin_tradeoff/"
STUDY_PREFIX = "research/pressure_fin/original_freeze/study/"
EXPECTED_MANIFEST_SHA256 = "48a9e676091b680c355d25127f625c83130105fcfbbd16cfa1f088257f860b41"
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
DESIGN_IDS = tuple(f"n{n}_t{t}" for n in (12, 16, 20) for t in (600, 860, 1200))
CASE_IDS = ("nominal", "pressure_loss", "asymmetric_blockage", "combined_fault")
HEAT_LOADS_W = (40, 60, 80)


def _selection(design_id, case_id, heat_load_W):
    if not isinstance(design_id, str) or design_id not in DESIGN_IDS:
        raise ValueError("design_id must select one of the nine saved geometries")
    if not isinstance(case_id, str) or case_id not in CASE_IDS:
        raise ValueError("case_id must select one of the four saved fault states")
    if type(heat_load_W) is not int or heat_load_W not in HEAT_LOADS_W:
        raise ValueError("heat_load_W must be an integer saved preset: 40, 60 or 80")
    return {"design_id": design_id, "case_id": case_id, "heat_load_W": heat_load_W}


def read_pressure_fin_replay(design_id="n16_t860", case_id="combined_fault", heat_load_W=60, *, root=ROOT):
    """Return a byte-verified view. Bad selection is 400; failed audit is 503."""
    chosen = _selection(design_id, case_id, heat_load_W)
    try:
        # Import machinery writes bytecode before module-level code executes.
        # Disable it before loading an auditor whose own tree is immutable.
        sys.dont_write_bytecode = True
        from research.pressure_fin.audit_package import audit, strict_json
        accepted, records, manifest_sha = audit(
            Path(root).resolve(), expected_manifest_sha256=EXPECTED_MANIFEST_SHA256,
            return_verified_records=True)
        if accepted.get("status") != "passed" or manifest_sha != EXPECTED_MANIFEST_SHA256:
            raise ValueError("Package audit did not verify the pinned identity")
        def data(path):
            return strict_json(records[path])
        catalog = data(PREFIX + "catalog.json")
        plan = data(STUDY_PREFIX + "presweep_plan.json")
        verification = data(STUDY_PREFIX + "verification.json")
        review = data(STUDY_PREFIX + "review/final_review_gate.json")
        sensitivities = data(PREFIX + "sensitivity_records.json")
        designs = {entry["design_id"]: data(PREFIX + entry["file"]) for entry in catalog["candidates"]}
        if set(designs) != set(DESIGN_IDS):
            raise ValueError("Incomplete finite candidate set")
        candidates = []
        for entry in catalog["candidates"]:
            design = designs[entry["design_id"]]
            heat = next(row for row in design["cases"]["combined_fault"]["heat_load_records"]
                        if row["heat_load_W"] == heat_load_W)
            candidates.append({**entry,
                               "combined_temperature_at_selected_load_C": heat["required_uniform_base_temperature_C"]})
        selected = designs[design_id]
        requirements = plan["requirements_synthetic_not_aircraft"]
        allowed_rise = requirements["maximum_base_temperature_C"] - requirements["inlet_temperature_C"]
        selected_capacity = selected["cases"]["combined_fault"]["G_W_K"] * allowed_rise
        baseline_capacity = designs["n16_t860"]["cases"]["combined_fault"]["G_W_K"] * allowed_rise
        selected_case = selected["cases"][case_id]
        current = next(row for row in selected_case["heat_load_records"] if row["heat_load_W"] == heat_load_W)
        identity = {"selection": chosen, "package_manifest_sha256": manifest_sha,
                    "reader_source_sha256": SOURCE_SHA256,
                    "candidate_sha256": hashlib.sha256(records[PREFIX + f"candidates/{design_id}.json"]).hexdigest()}
        response = {
            "schema": "aerolab-pressure-fin-replay-v1",
            "execution": "verified_research_replay", "live_computation": False,
            "physical_validation_pass": None, "aircraft_transfer_authorized": False,
            "selection": chosen,
            "requirements_synthetic_not_aircraft": plan["requirements_synthetic_not_aircraft"],
            "selected": selected, "baseline": designs["n16_t860"],
            "current_heat_load_record": current, "candidates": candidates,
            "combined_capacity_at_synthetic_limit": {
                "selected_heat_rejection_W": selected_capacity,
                "baseline_heat_rejection_W": baseline_capacity,
                "required_heat_load_W": requirements["combined_fault_heat_load_W"],
                "selected_heat_shortfall_W": requirements["combined_fault_heat_load_W"] - selected_capacity,
                "derivation": "Saved combined-fault G times synthetic (85 C base minus 25 C inlet); fixed-property component arithmetic, not aircraft derating guidance",
            },
            "declared_60W_summary": catalog["summary"],
            "numerical": {"gate_count": len(verification["gates"]), "gates": verification["gates"],
                          "spatial_max_relative": catalog["summary"]["grid_max_spatial_relative"],
                          "axial_max_relative": catalog["summary"]["grid_max_axial_relative"],
                          "interpretation": "Numerical checks are separate from conditional requirement screening and physical validation"},
            "model_form_sensitivity": {
                "scope": "18 baseline-only illustrative scenarios, not confidence bounds or alternative requirement passes",
                "plug_profile_interpretation": "Same pressure-derived mean flux; changes thermal advection shape only, not a no-slip momentum solution",
                "rows": [{k: row[k] for k in ("case_id", "sensitivity_parameter", "sensitivity_value", "G_change_from_primary_percent", "Tb_at_60W_C")}
                         for row in sensitivities["rows"]],
            },
            "scope_boundaries": review["scope_boundaries"],
            "provenance": {
                **identity,
                "selection_sha256": hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
                "source_model_sha256": review["physics_model_sha256"],
                "presweep_plan_sha256": review["presweep_plan_sha256"],
                "source_design_results_sha256": review["design_results_sha256"],
                "numerical_verification_sha256": review["verification_sha256"],
                "independent_review_status": review["independent_review_status"],
                "verified_file_count": accepted["listed_file_count"],
                "byte_snapshot_policy": "All values parsed from one fully audited immutable byte snapshot; no solver or post-audit record reads",
            },
        }
        if response["numerical"]["gate_count"] != 19 or not all(verification["gates"].values()):
            raise ValueError("Saved numerical gates are incomplete")
        if len(json.dumps(response, ensure_ascii=False, allow_nan=False).encode()) >= 100_000:
            raise ValueError("Pressure-fin replay exceeds bounded response contract")
        return response
    except (ImportError, OSError, ValueError, KeyError, TypeError, ZeroDivisionError, StopIteration) as exc:
        raise RuntimeError("Pressure-fin research evidence is missing, stale or inconsistent; audit the pinned package before showing the replay") from exc
