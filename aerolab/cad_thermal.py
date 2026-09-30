"""Geometry-linked reduced-order controller cooling, SI units throughout.

This is a new engineering approximation, NOT HeaTSSPy or CFD reproduction.
A covered, no-bypass duct is assumed although the exported part has bare fins.
The optional CAD kernel verifies solids; it does not validate heat transfer.
"""
from __future__ import annotations
from dataclasses import asdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from .geometry import (Geometry, GEOMETRY_PRESETS, parse_geometry, geometry_metrics,
                       geometry_preview_svg, geometry_fingerprint, kernel_status)

DEFAULT_BOUNDARY = {"heat_w": 1080.0, "inlet_c": 63.0, "mass_flow_kg_s": .085}
MATERIAL = {"density_kg_m3": 2700.0, "conductivity_w_m_k": 167.0, "specific_heat_j_kg_k": 900.0}
AIR = {"reference_pressure_pa": 101325.0, "density_kg_m3": 1.05, "viscosity_pa_s": 2.05e-5, "conductivity_w_m_k": .029,
       "specific_heat_j_kg_k": 1007.0}
CONTACT_K_W = .001
BLOWER_EFFICIENCY = .5
CONTROLLER_PLATE_MASS_KG = .6
DUCT_MASS_KG = 1.0  # two-controller system, not part of bare-fin CAD
NASA_RTH_K_W = .0194
SOURCE_URL = "https://ntrs.nasa.gov/citations/20230011420"
CORRELATION_URL = "https://ansyshelp.ansys.com/public/Views/Secured/MotorCAD/v252/en/Motor-CAD_UG/MotorCAD/topics/enclosedchannelconvectioncorrelation.html"
ASSUMPTIONS = [
    "Uniform rectangular fins and flat base reconstruct published average dimensions; not original NASA CAD or final Mod II hardware.",
    "Ideal adiabatic lid closes each channel; no bypass or external-face cooling. Lid is not included in exported bare-fin STEP.",
    "Fully developed constant-wall-temperature rectangular-duct laminar correlation and smooth-duct Gnielinski turbulent correlation are approximations to three heated walls with an adiabatic roof.",
    "No developing-flow enhancement, spreading resistance, radiation, detailed contact map, altitude correction, or CFD. Fixed air/material properties are illustrative assumptions.",
    "Prescribed mass flow, not a fan operating point. Pressure-drop work / 50% efficiency is charged as electrical demand; no free cooling.",
    "Adiabatic-tip rectangular-fin efficiency is applied once. Inner fin sides plus exposed channel base exchange heat; fin tips and outer sides do not.",
    "Interface temperature adds a synthetic 0.001 K/W contact resistance; NASA comparison uses base-average proxy excluding contact.",
]


def finite(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high or not math.isfinite(value):
        raise ValueError(f"{name} must be finite in [{low}, {high}]")
    return float(value)


def parse_boundary(value=None):
    if value is None:
        return DEFAULT_BOUNDARY.copy()
    if not isinstance(value, dict) or set(value) - set(DEFAULT_BOUNDARY):
        raise ValueError("Unknown boundary fields")
    data = DEFAULT_BOUNDARY | value
    return {"heat_w": finite(data["heat_w"], "heat_w", 0, 10000),
            "inlet_c": finite(data["inlet_c"], "inlet_c", -10, 100),
            "mass_flow_kg_s": finite(data["mass_flow_kg_s"], "mass_flow_kg_s", 0, .5)}


def _laminar_nu(alpha):
    # Shah/London fully developed constant-wall-temperature rectangular duct.
    return 7.541 * (1 - 2.610*alpha + 4.970*alpha**2 - 5.119*alpha**3 + 2.702*alpha**4 - .548*alpha**5)


def _laminar_po(alpha):
    # Darcy f*Re, not Fanning (factor of four matters).
    return 96 * (1 - 1.3553*alpha + 1.9467*alpha**2 - 1.7012*alpha**3 + .9564*alpha**4 - .2537*alpha**5)


def _turbulent(reynolds, prandtl):
    friction = (.790 * math.log(reynolds) - 1.64)**-2
    nu = (friction/8)*(reynolds-1000)*prandtl / (1+12.7*math.sqrt(friction/8)*(prandtl**(2/3)-1))
    return friction, nu


@lru_cache(maxsize=16384)
def flow_properties(geometry: Geometry, mass_flow_kg_s: float):
    """Independent of heat load/inlet temperature under fixed-property assumption."""
    g = geometry_metrics(geometry)
    flow = finite(mass_flow_kg_s, "mass_flow_kg_s", 0, .5)
    rho, mu, k, cp = (AIR[x] for x in ("density_kg_m3", "viscosity_pa_s", "conductivity_w_m_k", "specific_heat_j_kg_k"))
    dh, length = g["hydraulic_diameter_m"], g["length_m"]
    velocity = flow / (rho*g["flow_area_m2"])
    reynolds = rho*velocity*dh/mu
    prandtl = cp*mu/k
    alpha = min(g["gap_m"], g["fin_height_m"]) / max(g["gap_m"], g["fin_height_m"])
    warnings = ["Covered no-bypass duct assumed; bare-fin solid is not a CFD fluid domain.",
                "Correlation boundary-condition mismatch: adiabatic roof / three heated walls approximated by standard duct correlations."]
    if reynolds == 0:
        friction = nu = 0.0
        regime = "no_forced_flow"
    elif reynolds < 2300:
        friction, nu = _laminar_po(alpha)/reynolds, _laminar_nu(alpha)
        regime = "laminar_fully_developed_approximation"
    elif reynolds < 3000:
        blend = (reynolds-2300)/700
        ft, nt = _turbulent(3000, prandtl)
        friction = (1-blend)*_laminar_po(alpha)/2300 + blend*ft
        nu = (1-blend)*_laminar_nu(alpha) + blend*nt
        regime = "transition_unvalidated_interpolation"
        warnings.append("2300 <= Re < 3000: transition interpolation is not a validated correlation.")
    else:
        friction, nu = _turbulent(reynolds, prandtl)
        regime = "turbulent_gnielinski_hydraulic_diameter_approximation"
        if reynolds > 1e6:
            warnings.append("Re > 1e6: outside selected Gnielinski correlation range.")
    entrance_length = .05*reynolds*prandtl*dh if reynolds < 3000 else 10*dh
    if entrance_length > length:
        warnings.append("Estimated thermal entrance length exceeds fin length; fully-developed approximation may be poor.")
    mach = velocity/367.0  # approximate sound speed near the fixed air-property reference
    within_flow_limits = mach < .3 and reynolds <= 1e6
    if mach >= .3:
        warnings.append("Mach >= 0.3: incompressible pressure/heat-transfer model is outside applicability; results are not usable for design.")
    h = nu*k/dh
    m_height = math.sqrt(2*h/(MATERIAL["conductivity_w_m_k"]*g["fin_thickness_m"])) * g["fin_height_m"]
    efficiency = math.tanh(m_height)/m_height if m_height else 1.0
    effective_area = g["channel_base_area_m2"] + efficiency*g["channel_fin_area_m2"]
    ua = h*effective_area
    air_capacity = flow*cp
    # Exact constant-base-temperature heat-exchanger limit, not unbounded h*A.
    conv_g = -air_capacity*math.expm1(-ua/air_capacity) if air_capacity else 0.0
    base_r = g["base_thickness_m"]/(MATERIAL["conductivity_w_m_k"]*g["base_footprint_area_m2"])
    conv_r = 1/conv_g if conv_g else None
    total_r = conv_r + base_r + CONTACT_K_W if conv_r is not None else None
    dynamic = .5*rho*velocity**2
    pressure = (friction*length/dh + 1.5)*dynamic if flow else 0.0
    pressure_fraction = pressure/AIR["reference_pressure_pa"]
    within_flow_limits = within_flow_limits and pressure_fraction < .1
    if pressure_fraction >= .1:
        warnings.append("Pressure drop >= 10% of reference absolute pressure: fixed-density incompressible model is outside applicability.")
    fluid_power = pressure*flow/rho
    return {"mass_flow_kg_s": flow, "velocity_m_s": velocity, "mach_approx": mach, "within_flow_limits": within_flow_limits, "reynolds": reynolds,
            "prandtl": prandtl, "regime": regime, "nusselt": nu, "darcy_friction_factor": friction,
            "h_w_m2_k": h, "fin_efficiency": efficiency, "effective_area_m2": effective_area,
            "ua_w_k": ua, "air_capacity_w_k": air_capacity, "convective_conductance_w_k": conv_g,
            "interface_conductance_w_k": 1/total_r if total_r else 0.0,
            "base_resistance_k_w": base_r, "contact_resistance_k_w": CONTACT_K_W,
            "convective_resistance_k_w": conv_r, "interface_resistance_k_w": total_r,
            "base_to_inlet_resistance_k_w": conv_r+base_r if conv_r is not None else None,
            "pressure_drop_pa": pressure, "pressure_drop_fraction": pressure_fraction, "fluid_power_w": fluid_power,
            "blower_electrical_w": fluid_power/BLOWER_EFFICIENCY,
            "thermal_capacitance_j_k": (g["mass_kg"]+CONTROLLER_PLATE_MASS_KG)*MATERIAL["specific_heat_j_kg_k"],
            "sink_capacitance_j_k": g["mass_kg"]*MATERIAL["specific_heat_j_kg_k"],
            "thermal_entrance_length_m": entrance_length, "warnings": warnings}


def thermal_benchmark(geometry=None, boundary=None):
    geometry, boundary = parse_geometry(geometry), parse_boundary(boundary)
    result = dict(flow_properties(geometry, boundary["mass_flow_kg_s"]))
    result["warnings"] = result["warnings"].copy()
    q, inlet = boundary["heat_w"], boundary["inlet_c"]
    base_r, interface_r = result["base_to_inlet_resistance_k_w"], result["interface_resistance_k_w"]
    result.update({"boundary": boundary,
                   "base_temperature_c": inlet+q*base_r if base_r is not None else (inlet if q == 0 else None),
                   "interface_temperature_c": inlet+q*interface_r if interface_r is not None else (inlet if q == 0 else None),
                   "air_outlet_c": inlet+q/result["air_capacity_w_k"] if result["air_capacity_w_k"] else (inlet if q == 0 else None),
                   "steady_state_exists": bool(result["air_capacity_w_k"] or q == 0),
                   "nasa_reference": {"applicable_geometry_and_boundary": geometry == parse_geometry() and boundary == DEFAULT_BOUNDARY,
                                      "cfd_rth_k_w": NASA_RTH_K_W, "cfd_base_average_c": 63+1080*NASA_RTH_K_W,
                                      "not_validation": True, "note": "Published older-X57 CFD comparison only; no calibration or CFD performed here.",
                                      "base_rth_difference_percent": 100*(base_r/NASA_RTH_K_W-1) if base_r is not None and geometry == parse_geometry() and boundary == DEFAULT_BOUNDARY else None}})
    finite_thermal = result["interface_temperature_c"] is not None and result["interface_temperature_c"] <= 150 and -10 <= inlet <= 100
    result["within_model_limits"] = result["within_flow_limits"] and finite_thermal
    if not finite_thermal:
        result["warnings"].append("No finite forced-flow equilibrium or interface proxy exceeds 150 C: fixed-property reduced model is outside declared temperature applicability.")
    result["uncertainty_note"] = "Numerical limits do not establish physical validation; transition, entrance and boundary-condition warnings still apply."
    return result


def evaluate(geometry=None, boundary=None):
    geo = parse_geometry(geometry)
    b = parse_boundary(boundary)
    inputs = {"geometry": asdict(geo), "boundary": b, "model": "cad-controller-rom-v1"}
    model_hash = hashlib.sha256(b''.join(Path(__file__).with_name(p).read_bytes() for p in ("geometry.py", "cad_thermal.py"))).hexdigest()
    identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()+model_hash.encode()).hexdigest()
    status = kernel_status()
    # Geometry export metadata is supplied by the geometry engine, not inferred
    # from analytic math or kernel presence alone.
    from .geometry import cad_status
    return {"geometry": asdict(geo), "metrics": geometry_metrics(geo), "thermal": thermal_benchmark(geo, b),
            "preview_svg": geometry_preview_svg(geo), "cad": cad_status(geo),
            "input_hash": identity, "model_sha256": model_hash, "execution": "computed",
            "provenance": {"source_facts": {"source": SOURCE_URL, "location": "NASA/TM-20230011420 Table 2, printed p.13", "scope": "Older X-57 heat sink, not final Mod II"},
                           "assumptions": ASSUMPTIONS, "material": MATERIAL, "air": AIR,
                           "correlation_reference": {"turbulent_gnielinski": CORRELATION_URL, "laminar_darcy": SOURCE_URL + " (Eq. 27)", "laminar_constant_temperature": "https://eng-web77-v02.ocio.monash.edu/intranet/proceedings/fedsm_icnmm2010/data/pdfs/trk-2/FEDSM-ICNMM2010-30031.pdf"},
                           "computed": "Analytic geometry + optional independently verified BRep; reduced-order heat/pressure model, not CFD."}}


def compare_geometry(geometry=None, boundary=None):
    reference, candidate = evaluate(None, boundary), evaluate(geometry, boundary)
    delta = {}
    for field in ("mass_kg", "flow_area_m2", "channel_heated_area_m2", "hydraulic_diameter_m"):
        delta[field] = candidate["metrics"][field]-reference["metrics"][field]
    for field in ("base_temperature_c", "interface_temperature_c", "pressure_drop_pa", "blower_electrical_w"):
        a, b = candidate["thermal"][field], reference["thermal"][field]
        delta[field] = a-b if a is not None and b is not None else None
    return {"reference": reference, "candidate": candidate, "delta": delta,
            "note": "Independent offline designs at identical prescribed heat/inlet/flow. No guaranteed improvement."}


def cad_catalog():
    return {"defaults": asdict(parse_geometry()), "boundary": DEFAULT_BOUNDARY,
            "presets": [{"id": name, "geometry": asdict(parse_geometry(g))} for name, g in GEOMETRY_PRESETS.items()],
            "kernel": kernel_status(), "assumptions": ASSUMPTIONS, "source_url": SOURCE_URL,
            "fields": [{"name": name, "unit": "count" if name == "fin_count" else "mm"} for name in asdict(parse_geometry())]}
