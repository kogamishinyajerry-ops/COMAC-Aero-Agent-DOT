"""A bounded, live engineering story; no fitted coefficients or agent claims.

The synthetic hot-day perturbation holds density/flow boundaries fixed to isolate
ambient temperature. Reduced heat is explicit and never represents shaft power.
The alternatives are named candidates, not optimizer-selected recommendations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .nacelle_thermal import evaluate_nacelle, nacelle_boundary_catalog

STORY_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CASE_INPUTS = {
    "source_load": {"geometry": {}, "boundary": {}},
    "source_pressure": {"geometry": {}, "boundary": next(p["boundary"] for p in nacelle_boundary_catalog()["presets"] if p["id"] == "source_pressure_initial_climb")},
    "baseline": {"geometry": {}, "boundary": {"heat_scale": .25}},
    "hot_day": {"geometry": {}, "boundary": {"heat_scale": .25, "ambient_c": 45.9}},
    "more_fins": {"geometry": {"hv_fin_count": 36}, "boundary": {"heat_scale": .25, "ambient_c": 45.9}},
    "redistributed_cooling": {"geometry": {"hv_fin_count": 12, "motor_exhaust_area_mm2": 16000}, "boundary": {"heat_scale": .25, "ambient_c": 45.9}},
}


def _summary(run):
    components = run["thermal"]["components"]
    corners = run["uncertainty"]["scenarios"]
    eligible = [s["min_margin_c"] for s in corners if s["within_model_limits"] and s["min_margin_c"] is not None]
    return {
        "geometry_fingerprint": run["metrics"]["fingerprint"],
        "input_hash": run["input_hash"],
        "mass_kg": run["metrics"]["mass_kg"],
        "hv_pair_mass_kg": sum(run["metrics"]["components"][k]["mass_kg"] for k in ("cmc_left_hv", "cmc_right_hv")),
        "motor_temperature_c": components["motor_winding"]["temperature_c"],
        "hv_temperature_c": max(components[k]["temperature_c"] for k in ("cmc_left_hv", "cmc_right_hv")),
        "motor_flow_kg_s": sum(run["flow"]["branches"][k]["mass_flow_kg_s"] for k in ("motor_internal", "motor_slots")),
        "motor_mix_pressure_pa": run["flow"]["nodes"]["motor_mix"]["pressure_pa"],
        "hydraulic_dissipation_w": run["flow"]["hydraulic_dissipation_w"],
        "min_margin_c": run["thermal"]["summary"]["min_margin_c"],
        "within_model_limits": run["thermal"]["summary"]["within_model_limits"],
        "physically_validated": False,
        "scenario_min_margin_c": run["uncertainty"]["min_margin_c"],
        "out_of_domain_corner_count": sum(not item["within_model_limits"] for item in run["uncertainty"]["scenarios"]),
        "negative_reference_corner_count": sum(s["min_margin_c"] is not None and s["min_margin_c"] < 0 for s in corners),
        "in_domain_negative_reference_corner_count": sum(s["within_model_limits"] and s["min_margin_c"] is not None and s["min_margin_c"] < 0 for s in corners),
        "in_domain_corner_min_margin_c": min(eligible) if eligible else None,
        "corner_count": run["uncertainty"]["scenario_count"],
    }


def engineering_story():
    """Recompute all six cases, retaining full inputs and solver evidence."""
    cases = {name: evaluate_nacelle(**inputs) for name, inputs in CASE_INPUTS.items()}
    summaries = {name: _summary(run) for name, run in cases.items()}
    deltas = {}
    for name in ("more_fins", "redistributed_cooling"):
        base, alternative = summaries["hot_day"], summaries[name]
        deltas[name] = {key: alternative[key] - base[key] for key in (
            "mass_kg", "hv_pair_mass_kg", "motor_temperature_c", "hv_temperature_c",
            "motor_flow_kg_s", "motor_mix_pressure_pa", "hydraulic_dissipation_w")}
    evidence = {"story_source_sha256": STORY_SOURCE_SHA256,
                "case_input_hashes": {name: run["input_hash"] for name, run in cases.items()}}
    return {"schema": "x57-modii-engineering-story-v1", "execution": "computed",
            "story_source_sha256": STORY_SOURCE_SHA256,
            "story_hash": hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest(),
            "cases": cases, "summaries": summaries, "deltas_vs_hot_day": deltas,
            "claims": {"physically_validated": False, "design_selected_for_aircraft": False,
                       "optimization_performed": False, "llm_used": False},
            "scope": [
                "The full published heat-load case is shown first as a credibility gate, never replaced by a hidden lower-load default.",
                "The separate full-load source-pressure case uses published pressure increments with declared approximation, not a matched CFD boundary or calibration.",
                "Subsequent teaching cases use exactly 0.25 times the Table 4 heat loads, not 25 percent motor or aircraft power.",
                "The 10 C ambient perturbation is synthetic and holds density and pressure assumptions fixed to isolate a single cause.",
                "Both geometry alternatives use identical hot-day boundaries and losses; their pressure networks are solved independently.",
                "Scenario corners are assumption sensitivity checks, not probabilities, calibrated error bars or guaranteed extrema.",
                "No aircraft design recommendation follows from nominal reference margins; geometry tolerances and rotation remain unvalidated.",
                "Reported pressure-loss power is passive hydraulic dissipation, not fan electrical energy or total cooling drag.",
            ]}
