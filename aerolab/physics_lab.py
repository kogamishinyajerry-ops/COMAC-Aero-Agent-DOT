"""Bounded source/physics evidence for the local engineering explanation page.

This joins three explicitly separate models. It never substitutes a verified
laminar subcase or a historical component hypothesis for aircraft validation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .duct_finite_volume import solve_duct, SOURCE_SHA256 as DUCT_SOURCE_SHA256
from .nacelle_source_audit import source_audit

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
PRESETS = {
    "asymmetric": {"left_heat_flux_w_m2": 20., "right_heat_flux_w_m2": 200.},
    "equal": {"left_heat_flux_w_m2": 200., "right_heat_flux_w_m2": 200.},
    "one_wall": {"left_heat_flux_w_m2": 0., "right_heat_flux_w_m2": 200.},
    "balanced": {"left_heat_flux_w_m2": -200., "right_heat_flux_w_m2": 200.},
    "reversed": {"left_heat_flux_w_m2": 20., "right_heat_flux_w_m2": 200., "mean_velocity_m_s": -1.},
    "zero_flow": {"left_heat_flux_w_m2": 20., "right_heat_flux_w_m2": 200., "mean_velocity_m_s": 0.},
}


def _verified_subcase_record():
    path = ROOT / "examples" / "duct_verification.json"
    try:
        payload = path.read_bytes()
        evidence = json.loads(payload)
        samples = evidence["visual_cases"].values()
        if any(sample["provenance"]["source_sha256"] != DUCT_SOURCE_SHA256 for sample in samples):
            raise ValueError("Duct verification belongs to a different numerical model")
        generator = ROOT / "scripts" / "generate_duct_verification.py"
        generator_hash = hashlib.sha256(generator.read_bytes()).hexdigest()
        if evidence["reference"]["source_sha256"] != generator_hash:
            raise ValueError("Duct verification reference source has changed")
        if not evidence["gates"] or not all(evidence["gates"].values()):
            raise ValueError("Duct verification gates have not passed")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Verified subcase evidence is unavailable or stale; regenerate it before showing verification status") from exc
    keys = ("schema", "purpose", "sources", "gates", "fully_developed_grid_convergence",
            "transverse_nusselt_observed_orders", "axial_grid_convergence",
            "axial_observed_orders_from_successive_differences", "developing_spectral_comparison")
    return {**{key: evidence[key] for key in keys},
            "execution": "verified_saved_record", "artifact_sha256": hashlib.sha256(payload).hexdigest(),
            "numerical_source_matches": True, "model_source_sha256": DUCT_SOURCE_SHA256,
            "analytical_equal_flux_nusselt": evidence["reference"]["analytical_equal_flux_nusselt"],
            "analytical_darcy_f_re": evidence["reference"]["analytical_darcy_f_re"],
            "reference_method": evidence["reference"]["method"]}


def physics_evidence(case="asymmetric"):
    if not isinstance(case, str) or case not in PRESETS:
        raise ValueError("case must be one of: " + ", ".join(PRESETS))
    from .historical_motor import historical_motor_benchmark
    audit = source_audit()
    source = {key: audit[key] for key in (
        "source_url", "source_data_sha256", "audit_source_sha256", "geometry_fingerprint",
        "inference_case", "retrospective_check_cases", "scope", "flow_area_constraints",
        "conditional_resistance_checks", "geometry_hypotheses")}
    result = {
        "schema": "aerolab-physics-lab-v1", "execution": "computed",
        "source_sha256": SOURCE_SHA256, "case": case,
        "claims": {"aircraft_physically_validated": False, "calibration_transferred_to_nacelle": False,
                   "new_cad_dimensions_verified": False, "source_cases_blind_holdout": False},
        "source_audit": source, "historical_motor": historical_motor_benchmark(),
        "duct": solve_duct(PRESETS[case]), "verification": _verified_subcase_record(),
        "next_evidence_needed": [
            "Final-configuration stator heat-sink passage geometry, face exposure and flow measurement definitions",
            "Directional winding/potting/contact properties and component-node definitions",
            "Matched pressure, flow and temperature measurements with recorded rotational and heat-load conditions",
        ],
    }
    if len(json.dumps(result, allow_nan=False).encode()) > 100_000:
        raise RuntimeError("Physics evidence exceeds the bounded response contract")
    return result
