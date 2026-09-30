"""Source-station identifiability checks, separate from the aircraft ROM.

NASA specifies cross-section-averaged CFD station summaries, but not the
averaging weights/operator.
These calculations therefore produce *flux-equivalent* area hypotheses and
conditional resistance diagnostics, never original CAD or measured validation.
Only initial climb is used to infer the fixed quantities. Other published cases
are retrospective cross-condition checks, not a blind or experimental holdout.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from .nacelle_geometry import nacelle_metrics, GEOMETRY_SOURCE_SHA256

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "nasa_x57_modii_stations.json"
DATA_BYTES = DATA_PATH.read_bytes()
SOURCE_DATA_SHA256 = hashlib.sha256(DATA_BYTES).hexdigest()
SOURCE_DATA = json.loads(DATA_BYTES)
SOURCE_CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
PSI_PA = 6894.757293168
LBM_KG = .45359237
FT_M = .3048
R_AIR = 287.05
GAMMA = 1.4
CP = 1007.0
INFERENCE_CASE = "initial_climb"
CHECK_CASES = ("cruise_climb", "dash")
AREA_STATIONS = {
    "main_inlet": "1_c", "motor_internal": "2a_g", "motor_slots": "2a_s",
    "motor_bypass_inlet": "1_b", "motor_bypass_core": "2a_b",
    "lv_fresh_left": "ME_L", "lv_fresh_right": "ME_R",
}
# These are scalar conditional paths, not mutually disjoint network edges.
# Actual downstream pressure is an input, so this does not predict that pressure.
PRESSURE_PATHS = {
    "main_to_gap": ("1_c", "4", "2a_g"),
    "main_to_slots": ("1_c", "4", "2a_s"),
    "bypass_to_mix": ("1_b", "4", "2a_b"),
    "gap_core": ("2a_g", "2c_g", "2a_g"),
    "slot_core": ("2a_s", "2c_s", "2a_s"),
}


def _valid_row(row):
    if not isinstance(row, (list, tuple)) or len(row) != 6:
        raise ValueError("A source station requires exactly six numeric fields")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in row):
        raise ValueError("Source station fields must be finite numbers")
    p, pt, t, tt, velocity, mass = row
    if p <= .005 or pt < p or t <= -273.145 or tt < t or velocity <= .05 or mass <= .0005:
        raise ValueError("Station must have positive pressure, temperature and resolved forward flow")


def station_properties(row):
    """Ideal-gas algebra on published averages, with printed-rounding bounds.

    The ranges below cover rounding only, not CFD error, unresolved profiles/averaging weights or
    uncertainty in treating cross-section-averaged p/T/u as products of local quantities.
    """
    _valid_row(row)
    p, pt, t, tt, velocity, mass = row
    p_pa, speed, mdot = p * PSI_PA, velocity * FT_M, mass * LBM_KG
    rho = p_pa / (R_AIR * (t + 273.15))
    area = mdot / (rho * speed)
    # Isentropic stagnation inversion is a diagnostic, not a resolved vector.
    mach2 = 2 / (GAMMA - 1) * ((pt / p) ** ((GAMMA - 1) / GAMMA) - 1)
    energy_speed = math.sqrt(max(0., mach2 * GAMMA * R_AIR * (t + 273.15)))
    temperature_speed = math.sqrt(2 * CP * (tt - t))
    rho_low = (p - .005) * PSI_PA / (R_AIR * (t + .005 + 273.15))
    rho_high = (p + .005) * PSI_PA / (R_AIR * (t - .005 + 273.15))
    area_low = (mass - .0005) * LBM_KG / (rho_high * (velocity + .05) * FT_M)
    area_high = (mass + .0005) * LBM_KG / (rho_low * (velocity - .05) * FT_M)
    return {
        "density_ideal_gas_kg_m3": rho,
        "density_printed_rounding_kg_m3": [rho_low, rho_high],
        "streamwise_velocity_m_s": speed, "mass_flow_kg_s": mdot,
        "flux_equivalent_area_m2": area,
        "area_printed_rounding_m2": [area_low, area_high],
        "pressure_energy_velocity_m_s": energy_speed,
        "temperature_energy_velocity_m_s": temperature_speed,
        "pressure_energy_to_streamwise_ratio": energy_speed / speed,
        "temperature_energy_to_streamwise_ratio": temperature_speed / speed,
    }


def _pressure_case(rows, path):
    inlet, outlet, flow_station = path
    inputs = station_properties(rows[inlet])
    mdot = rows[flow_station][5] * LBM_KG
    dp = (rows[inlet][1] - rows[outlet][1]) * PSI_PA
    # Subtracting independently rounded pressures adds their half resolutions.
    dp_low, dp_high = dp - .01 * PSI_PA, dp + .01 * PSI_PA
    if dp_low <= 0:
        raise ValueError("Printed pressure drop is not resolved above rounding")
    rho = inputs["density_ideal_gas_kg_m3"]
    rho_low, rho_high = inputs["density_printed_rounding_kg_m3"]
    m_low, m_high = mdot - .0005 * LBM_KG, mdot + .0005 * LBM_KG
    conductance = mdot / math.sqrt(2 * rho * dp)
    conductance_interval = [m_low / math.sqrt(2 * rho_high * dp_high),
                            m_high / math.sqrt(2 * rho_low * dp_low)]
    return {"inlet_station": inlet, "outlet_station": outlet,
            "flow_station": flow_station, "pressure_drop_pa": dp,
            "pressure_drop_printed_rounding_pa": [dp_low, dp_high],
            "inlet_density_kg_m3": rho, "inlet_density_printed_rounding_kg_m3": [rho_low, rho_high],
            "observed_mass_flow_kg_s": mdot,
            "observed_mass_flow_printed_rounding_kg_s": [m_low, m_high],
            "effective_area_over_sqrt_k_m2": conductance,
            "effective_area_over_sqrt_k_printed_rounding_m2": conductance_interval}


def conditional_resistance_check(cases=None):
    """Fit each A/sqrt(K) once, then use unchanged in other source conditions.

    This intentionally tests the assumption rather than improving the current
    nacelle. It uses published internal downstream pressure, not a ROM prediction.
    A and K are not separately identifiable from this fit.
    """
    cases = SOURCE_DATA["cases"] if cases is None else cases
    results = {}
    for name, path in PRESSURE_PATHS.items():
        training = _pressure_case(cases[INFERENCE_CASE], path)
        g = training["effective_area_over_sqrt_k_m2"]
        g_low, g_high = training["effective_area_over_sqrt_k_printed_rounding_m2"]
        values = {}
        for case in (INFERENCE_CASE,) + CHECK_CASES:
            item = _pressure_case(cases[case], path)
            rho, dp = item["inlet_density_kg_m3"], item["pressure_drop_pa"]
            rlo, rhi = item["inlet_density_printed_rounding_kg_m3"]
            plo, phi = item["pressure_drop_printed_rounding_pa"]
            mlo, mhi = item["observed_mass_flow_printed_rounding_kg_s"]
            predicted = g * math.sqrt(2 * rho * dp)
            pred_lo, pred_hi = g_low * math.sqrt(2 * rlo * plo), g_high * math.sqrt(2 * rhi * phi)
            item.update({"role": "inference" if case == INFERENCE_CASE else "retrospective_cross_condition_check",
                         "predicted_mass_flow_kg_s": predicted,
                         "relative_error_percent": 100 * (predicted / item["observed_mass_flow_kg_s"] - 1),
                         "prediction_printed_rounding_kg_s": [pred_lo, pred_hi],
                         "error_printed_rounding_percent": [100 * (pred_lo / mhi - 1), 100 * (pred_hi / mlo - 1)]})
            values[case] = item
        results[name] = {"fitted_case": INFERENCE_CASE, "fixed_effective_area_over_sqrt_k_m2": g,
                         "cases": values}
    return results


def _station_enthalpy_diagnostic(rows, heat_w):
    """Demonstrate why station means must not be used as exact heat integrals."""
    # Reference zero prevents small source mass differences from multiplying
    # an arbitrary absolute enthalpy datum. This remains only a diagnostic.
    reference = rows["1_c"][3]
    inlet = ("1_c", "1_b")
    outlet = ("2c_g", "2c_s", "2c_b")
    def energy(stations):
        return sum(rows[s][5] * LBM_KG * CP * (rows[s][3] - reference) for s in stations)
    mass_in = sum(rows[s][5] for s in inlet) * LBM_KG
    mass_out = sum(rows[s][5] for s in outlet) * LBM_KG
    apparent_heat = energy(outlet) - energy(inlet)
    return {"inlet_stations": list(inlet), "outlet_stations": list(outlet),
            "reference_total_temperature_c": reference,
            "apparent_enthalpy_gain_w": apparent_heat, "table4_motor_heat_w": heat_w,
            "apparent_difference_w": apparent_heat - heat_w,
            "apparent_relative_difference_percent": 100 * (apparent_heat / heat_w - 1),
            "mass_difference_kg_s": mass_out - mass_in,
            "is_integrated_control_volume_balance": False,
            "interpretation": "The product of reported station mass flow and reported total-temperature averages is not known to equal integrated enthalpy flux. Swirl work, spatial averaging, station coverage and rounding are unresolved. This discrepancy is not proof that NASA CFD violates conservation, and cannot identify wall heat fractions."}


def source_audit():
    cases = SOURCE_DATA["cases"]
    metrics = nacelle_metrics()
    selected = sorted(set(AREA_STATIONS.values()) | {"2c_g", "2c_s", "2c_b", "4"})
    stations = {case: {station: station_properties(rows[station]) for station in selected}
                for case, rows in cases.items()}
    areas = {}
    for name, station in AREA_STATIONS.items():
        inferred = stations[INFERENCE_CASE][station]["flux_equivalent_area_m2"]
        key = "motor_bypass" if name.startswith("motor_bypass") else name
        channel = metrics["channels"][key]
        current = (channel.get("heat_exchange", channel) if name == "motor_bypass_core" else channel)["area_m2"]
        observations = [stations[c][station]["flux_equivalent_area_m2"] for c in cases]
        areas[name] = {"station": station, "inference_case": INFERENCE_CASE,
            "inferred_flux_equivalent_area_m2": inferred, "current_rom_area_m2": current,
            "current_rom_area_relative_to_inference_percent": 100 * (current / inferred - 1),
            "cross_condition_relative_to_inference_percent": {
                c: 100 * (stations[c][station]["flux_equivalent_area_m2"] / inferred - 1) for c in CHECK_CASES},
            "three_case_span_percent_of_inferred": 100 * (max(observations) - min(observations)) / inferred}
    geometry_hypotheses = {}
    gap_area = areas["motor_internal"]["inferred_flux_equivalent_area_m2"]
    gap_channel = metrics["channels"]["motor_internal"]
    outer_radius = gap_channel["wetted_perimeter_m"] / (4 * math.pi) + gap_channel["hydraulic_diameter_m"] / 4
    # Interpret only within the ROM's own concentric-cylinder assumption.
    inferred_gap = outer_radius - math.sqrt(outer_radius ** 2 - gap_area / math.pi)
    geometry_hypotheses["concentric_gap_mm"] = inferred_gap * 1000
    geometry_hypotheses["status"] = "Illustrative inversion inside the ROM geometry assumption, not a NASA dimension or a design recommendation. No CAD or ROM input is changed."
    return {"schema": "aerolab-nacelle-source-audit-v1",
        "source_url": SOURCE_DATA["source_url"], "source_data_sha256": SOURCE_DATA_SHA256,
        "audit_source_sha256": SOURCE_CODE_SHA256, "geometry_source_sha256": GEOMETRY_SOURCE_SHA256,
        "geometry_fingerprint": metrics["fingerprint"],
        "inference_case": INFERENCE_CASE, "retrospective_check_cases": list(CHECK_CASES),
        "experimental_validation": False, "blind_holdout": False,
        "scope": ["Initial-climb-only inference; cruise and dash are retrospective consistency checks on the same published CFD geometry.",
                  "Printed-rounding intervals are not statistical uncertainty or bounds on nonuniform-profile/averaging errors.",
                  "Flux-equivalent m/(rho*u_stream) is not an independently measured geometric area.",
                  "Pressure-energy speed and temperature-energy speed are algebraic diagnostics; differences from streamwise speed suggest unresolved transverse kinetic energy and averaging, not a recovered swirl vector.",
                  "Conditional pressure tests input both published upstream and downstream pressures and therefore do not validate a predictive nacelle network.",
                  "No current CAD geometry, heat-transfer coefficient or successful-temperature threshold is adjusted."],
        "station_diagnostics": stations, "flow_area_constraints": areas,
        "geometry_hypotheses": geometry_hypotheses,
        "conditional_resistance_checks": conditional_resistance_check(),
        "station_enthalpy_diagnostic": {c: _station_enthalpy_diagnostic(cases[c], 4662. if c == "cruise_climb" else 5819.) for c in cases}}


def source_station_data():
    """Return a copy so consumers cannot mutate the source fixture in memory."""
    return deepcopy(SOURCE_DATA)
