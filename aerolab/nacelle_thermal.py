"""CAD-linked, uncalibrated X-57 Mod II nacelle pressure/thermal network.

This is a passive ram/suction reduced-order demonstrator, not NASA's CFD or
ICPT model. Geometry, pressure, mixing, and heat balances are computed; missing
pressure recovery, local losses, contacts and board splits remain assumptions.
Only the Python standard library is required. SI units except temperatures C.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import itertools
import json
import math
from pathlib import Path

from .nacelle_geometry import parse_nacelle, nacelle_metrics, GEOMETRY_SOURCE_SHA256

# Bind identities to the code imported into this process, not later disk edits.
THERMAL_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
MODULE_SOURCE_SHA256 = {"nacelle_geometry.py": GEOMETRY_SOURCE_SHA256, "nacelle_thermal.py": THERMAL_SOURCE_SHA256}
MODEL_SOURCE_SHA256 = hashlib.sha256(json.dumps(MODULE_SOURCE_SHA256, sort_keys=True).encode()).hexdigest()

MODEL_ID = "x57-mod-ii-nacelle-pressure-thermal-rom-v1"
SOURCE_URL = "https://ntrs.nasa.gov/api/citations/20230006888/downloads/Borer_Bui_Smith_X-57_thermal_analysis.pdf"
CORRELATION_URL = "https://ansyshelp.ansys.com/public/Views/Secured/MotorCAD/v252/en/Motor-CAD_UG/MotorCAD/topics/enclosedchannelconvectioncorrelation.html"
AIR = {"specific_heat_j_kg_k": 1007.0, "viscosity_pa_s": 1.90e-5,
       "conductivity_w_m_k": .027, "reference_pressure_pa": 101325.0}
DEFAULT_BOUNDARY = {
    "airspeed_m_s": 39.1, "ambient_c": 35.9, "density_kg_m3": 1.02,
    "ram_recovery": .65, "bypass_ram_recovery": .65, "lv_ram_recovery": .55,
    "main_propeller_pressure_pa": 0.0, "bypass_propeller_pressure_pa": 0.0, "lv_propeller_pressure_pa": 0.0,
    "exhaust_suction_coefficient": .15, "motor_exhaust_suction_coefficient": .10,
    "heat_load": "peak", "heat_scale": 1.0, "loss_multiplier": 1.0,
    "contact_multiplier": 1.0,
}
BOUNDARY_LIMITS = {
    "airspeed_m_s": (0, 120), "ambient_c": (-30, 60), "density_kg_m3": (.3, 1.4),
    "ram_recovery": (0, 1), "bypass_ram_recovery": (0, 1), "lv_ram_recovery": (0, 1),
    "main_propeller_pressure_pa": (0, 3000), "bypass_propeller_pressure_pa": (0, 3000), "lv_propeller_pressure_pa": (0, 3000),
    "exhaust_suction_coefficient": (0, 1), "motor_exhaust_suction_coefficient": (-.25, 1),
    "heat_scale": (0, 2), "loss_multiplier": (.25, 4), "contact_multiplier": (.25, 4),
}
# NASA Table 4, per one nacelle: two controllers, one motor.
HEAT_LOADS = {"peak": {"winding_w": 5237.0, "magnet_w": 582.0, "hv_each_w": 810.0, "lv_each_w": 30.0},
              "mcp": {"winding_w": 4196.0, "magnet_w": 466.0, "hv_each_w": 679.0, "lv_each_w": 30.0}}
# Fixed values below are explicitly inferred, NOT NASA measurements/calibration.
# Darcy f uses hydraulic geometry; K covers unresolved entrances, exits and bends.
BRANCHES = {
    "main_inlet": ("main_ram", "inlet_plenum", .8),
    "motor_internal": ("inlet_plenum", "motor_mix", 2.5),
    "motor_slots": ("inlet_plenum", "motor_mix", 2.5),
    "motor_bypass": ("bypass_ram", "motor_mix", 1.3),
    "motor_top_exhaust": ("motor_mix", "top_exhaust", 2.0),
    "cmc_hv_left": ("motor_mix", "lower_mix", 2.2),
    "cmc_hv_right": ("motor_mix", "lower_mix", 2.2),
    "cmc_bypass": ("motor_mix", "lower_mix", 1.8),
    "lv_fresh_left": ("lv_ram", "lower_mix", 3.0),
    "lv_fresh_right": ("lv_ram", "lower_mix", 3.0),
    "lower_outlet": ("lower_mix", "lower_exhaust", 1.1),
}
INTERNAL_NODES = ("inlet_plenum", "motor_mix", "lower_mix")
# Bulk equivalent conductivities and contact resistances, not measured hardware.
MATERIAL_K = {"motor_winding": 8.0, "motor_magnet": 8.0,
              "cmc_left_hv": 167.0, "cmc_right_hv": 167.0,
              "cmc_left_lv": 167.0, "cmc_right_lv": 167.0,
              "cmc_left_cpu": 1.5, "cmc_right_cpu": 1.5,
              "cmc_left_acdc": 1.5, "cmc_right_acdc": 1.5}
CONTACT_K_W = {"motor_winding": .0015, "motor_magnet": .01,
               "cmc_left_hv": .025, "cmc_right_hv": .025,
               "cmc_left_lv": .005, "cmc_right_lv": .005,
               "cmc_left_cpu": 1.5, "cmc_right_cpu": 1.5,
               "cmc_left_acdc": 1.2, "cmc_right_acdc": 1.2}
MARGINED_LIMITS = {"motor_winding": 124.0, "motor_magnet": 83.0,
                  "cmc_left_hv": 150.0, "cmc_right_hv": 150.0,
                  "cmc_left_cpu": 74.0, "cmc_right_cpu": 74.0,
                  "cmc_left_acdc": 74.0, "cmc_right_acdc": 74.0}
ASSUMPTIONS = [
    "Public-source Mod II topology with dimensionally inferred CAD; this is not original NASA CAD, NASA CFD, ICPT, or a calibrated prediction.",
    "One nacelle: internal motor flow and motor bypass mix behind the motor, then divide among top exhaust, left/right HV fins and CMC bypass. Two separate fresh LV inlets rejoin the lower outlet.",
    "Main cooling and outer bypass have separate external intake reservoirs. Ram recovery, exhaust suction and branch minor losses are inferred; optional explicit propeller-pressure additions represent a boundary assumption, not a propeller solution or blower.",
    "Fixed-density incompressible pressure network uses Darcy friction and analytic hydraulic dimensions; smooth equivalent ducts replace complex rotating passages, scoops, baffles and jets.",
    "Turbulent Gnielinski/hydraulic-diameter convection and circular-equivalent fully developed laminar Nu=3.66 are approximate; the 2300-4000 transition is an unvalidated smooth interpolation.",
    "Motor cooling slots and rotor-stator gap are parallel CAD-derived paths. Stator heat is apportioned by exposed winding surface area; half the magnet heat goes to the gap and half to the external motor bypass, following NASA Table 4.",
    "Each motor path has uniform heated wall patches exchanging with a common axial air stream. Unequal winding and magnet surface temperatures are solved; winding and magnet reports are the maximum modeled patches, not spatial fields.",
    "Motor magnet temperature reports the hotter inner/outer surface proxy; it is not a single solved isothermal magnet nor a spatial field. Cross-conduction between those two patches is omitted.",
    "Straight-fin efficiency is applied once to HV fin area. L/(k A) uses CAD component dimensions plus declared inferred contact and bulk-material properties.",
    "Each LV backplate rejects 30 W at unit heat scale, split into inferred CPU 8 W, AC/DC 12 W and other boards 10 W. Board-to-backplate resistances are illustrative and explicitly uncalibrated.",
    "NASA Table 1 margined limits are comparison references. Our HV temperature is a lumped FET/contact proxy, motor and board values are lumped proxies; none establish certified component margins.",
    "No natural convection, radiation, thermal transient, recirculation, leakage, rotation enhancement, conjugate field, mesh convergence or experimental validation. Zero forced flow with heat has no equilibrium in this model.",
    "MDAU/FOBE and aft dead-space heating are excluded, consistent with the cited CFD domain; this is not an aircraft mission energy model.",
]


def _finite(value, name, low, high):
    try:
        valid = (not isinstance(value, bool) and isinstance(value, (int, float))
                 and low <= value <= high and math.isfinite(value))
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number in [{low}, {high}]")
    return float(value)


def parse_nacelle_boundary(value=None):
    """Omitted fields use declared defaults; explicit null/unknown values fail."""
    if value is None:
        return DEFAULT_BOUNDARY.copy()
    if not isinstance(value, Mapping):
        raise ValueError("nacelle boundary must be an object")
    unknown = set(value) - set(DEFAULT_BOUNDARY)
    if unknown:
        raise ValueError("Unknown nacelle boundary fields: " + ", ".join(sorted(map(str, unknown))))
    result = DEFAULT_BOUNDARY | dict(value)
    if not isinstance(result["heat_load"], str) or result["heat_load"] not in HEAT_LOADS:
        raise ValueError("heat_load must be 'peak' or 'mcp'")
    for name, (low, high) in BOUNDARY_LIMITS.items():
        result[name] = _finite(result[name], name, low, high)
    return result


def nacelle_boundary_catalog():
    units = {"airspeed_m_s": "m/s", "ambient_c": "C", "density_kg_m3": "kg/m3",
             "main_propeller_pressure_pa": "Pa", "bypass_propeller_pressure_pa": "Pa", "lv_propeller_pressure_pa": "Pa"}
    fields = [{"name": name, "default": DEFAULT_BOUNDARY[name], "min": limits[0],
               "max": limits[1], "unit": units.get(name, "ratio"), "type": "number"}
              for name, limits in BOUNDARY_LIMITS.items()]
    fields.append({"name": "heat_load", "default": "peak", "type": "enum", "options": list(HEAT_LOADS)})
    psi = 6894.757293168
    dynamic = .5 * DEFAULT_BOUNDARY["density_kg_m3"] * DEFAULT_BOUNDARY["airspeed_m_s"] ** 2
    source_boundary = DEFAULT_BOUNDARY | {
        "ram_recovery": 1.0, "bypass_ram_recovery": 1.0, "lv_ram_recovery": 1.0,
        "main_propeller_pressure_pa": .13 * psi,
        "bypass_propeller_pressure_pa": .08 * psi,
        "lv_propeller_pressure_pa": .005 * psi,
        "motor_exhaust_suction_coefficient": -.01 * psi / dynamic,
        "exhaust_suction_coefficient": .02 * psi / dynamic}
    return {"defaults": DEFAULT_BOUNDARY.copy(), "fields": fields,
            "presets": [{"id": "initial_climb", "boundary": DEFAULT_BOUNDARY.copy()},
                        {"id": "source_pressure_initial_climb", "boundary": source_boundary,
                         "note": "Table 7 total-pressure augmentation above freestream total13.53psi: main1_c13.66 (+.13psi), bypass1_b13.61 (+.08psi), LV ME_L/R mean13.535 (+.005psi, symmetric averaging assumption). Recoveries are1; these additions supplement computed freestream dynamic pressure, avoiding double counting. Upper4_e static13.42 and lower7 static13.39 are referenced to freestream static13.41psi. Source pressure rounding and assumed density mean these are approximate boundary conditions. No measurements or calibration."},
                        {"id": "cruise_climb", "boundary": DEFAULT_BOUNDARY | {"airspeed_m_s": 45.3, "heat_load": "mcp"}},
                        {"id": "dash", "boundary": DEFAULT_BOUNDARY | {"airspeed_m_s": 77.2, "ambient_c": 23.3, "density_kg_m3": .90}},
                        {"id": "no_ram", "boundary": DEFAULT_BOUNDARY | {"airspeed_m_s": 0}},
                        {"id": "reduced_load_screening", "boundary": DEFAULT_BOUNDARY | {"heat_scale": .25},
                         "note": "Optional teaching input: one quarter of the Table 4 HEAT loads, not one quarter aircraft/motor power. Loss versus power is not modeled. Deliberately choose this preset; it is neither the default nor a validated operating point."}],
            "source_heat_loads": HEAT_LOADS, "reference_limits_c": MARGINED_LIMITS,
            "note": "Speeds/temperatures approximate NASA Table 3; density and pressure coefficients are inferred. Presets are not NASA CFD reproduction.",
            "assumptions": ASSUMPTIONS, "source_url": SOURCE_URL}


def _validate_metrics(metrics):
    # Fail loudly rather than silently substituting fixed hydraulic dimensions.
    for branch in BRANCHES:
        if branch not in metrics.get("channels", {}):
            raise ValueError(f"CAD metrics missing channel {branch}")
        ch = metrics["channels"][branch]
        for field in ("area_m2", "wetted_perimeter_m", "length_m", "hydraulic_diameter_m"):
            _finite(ch.get(field), f"{branch}.{field}", 1e-9, 100)
        _finite(ch.get("heated_area_m2"), f"{branch}.heated_area_m2", 0, 100)
        derived = 4 * ch["area_m2"] / ch["wetted_perimeter_m"]
        if not math.isclose(derived, ch["hydraulic_diameter_m"], rel_tol=1e-8):
            raise ValueError(f"{branch} hydraulic diameter differs from CAD area/perimeter")
    for branch in ("motor_internal", "motor_slots"):
        surfaces = metrics["channels"][branch].get("heated_surfaces_m2", {})
        expected = {"motor_winding", "motor_magnet"} if branch == "motor_internal" else {"motor_winding"}
        if set(surfaces) != expected:
            raise ValueError(f"{branch} missing or unknown heated surface IDs")
        for name, area in surfaces.items():
            _finite(area, f"{branch}.{name} heated area", 1e-10, 100)
        if not math.isclose(sum(surfaces.values()), metrics["channels"][branch]["heated_area_m2"], rel_tol=1e-8):
            raise ValueError(f"{branch} heated area does not match surface areas")
    for branch in ("lv_fresh_left", "lv_fresh_right"):
        channel = metrics["channels"][branch]
        if not isinstance(channel.get("segments"), list) or len(channel["segments"]) != 2 or "heat_exchange" not in channel:
            raise ValueError(f"{branch} requires separate scoop and backplate geometry")
        for item in channel["segments"] + [channel["heat_exchange"]]:
            for field in ("area_m2", "wetted_perimeter_m", "length_m", "hydraulic_diameter_m"):
                _finite(item.get(field), f"{branch} section {field}", 1e-9, 100)
            if not math.isclose(4 * item["area_m2"] / item["wetted_perimeter_m"], item["hydraulic_diameter_m"], rel_tol=1e-8):
                raise ValueError(f"{branch} section hydraulic diameter differs from area/perimeter")
    for name in MATERIAL_K:
        if name not in metrics.get("components", {}):
            raise ValueError(f"CAD metrics missing component {name}")
        for field in ("conduction_area_m2", "conduction_length_m"):
            _finite(metrics["components"][name].get(field), f"{name}.{field}", 1e-10, 100)
    magnet = metrics["components"]["motor_magnet"]
    patches = magnet.get("conduction_patch_areas_m2", {})
    if set(patches) != {"inner", "outer"}:
        raise ValueError("motor_magnet requires inner/outer conduction patch areas")
    for name, area in patches.items():
        _finite(area, f"motor_magnet {name} conduction area", 1e-10, 100)
    if not math.isclose(sum(patches.values()), magnet["conduction_area_m2"], rel_tol=1e-8):
        raise ValueError("motor_magnet patch areas must sum to aggregate conduction area")


def _friction_nusselt(reynolds, prandtl):
    if reynolds <= 0:
        return 0.0, 0.0, "no_forced_flow"
    if reynolds < 2300:
        return 64 / reynolds, 3.66, "laminar_equivalent_duct"
    def turbulent(re):
        f = (.790 * math.log(re) - 1.64) ** -2
        nu = (f / 8) * (re - 1000) * prandtl / (1 + 12.7 * math.sqrt(f / 8) * (prandtl ** (2 / 3) - 1))
        return f, nu
    if reynolds < 4000:
        t = (reynolds - 2300) / 1700
        s = t * t * (3 - 2 * t)
        ft, nt = turbulent(4000)
        return ((1 - s) * 64 / reynolds + s * ft,
                (1 - s) * 3.66 + s * nt, "transition_unvalidated")
    f, nu = turbulent(reynolds)
    return f, nu, "turbulent_equivalent_duct"


def _pressure_drop(mass_flow, channel, density, minor_k):
    """Signed, continuous, monotone Darcy pressure loss for a signed mass flow."""
    if mass_flow == 0:
        return 0.0
    velocity = abs(mass_flow) / (density * channel["area_m2"])
    re = density * velocity * channel["hydraulic_diameter_m"] / AIR["viscosity_pa_s"]
    f, _, _ = _friction_nusselt(re, .71)
    if channel.get("segments"):
        # Inlet K acts on aperture velocity; friction sums distinct serial ducts.
        friction_loss = sum(abs(_pressure_drop(mass_flow, segment, density, 0.0)) for segment in channel["segments"])
        loss = friction_loss + minor_k * .5 * density * velocity ** 2
    else:
        loss = (f * channel["length_m"] / channel["hydraulic_diameter_m"] + minor_k) * .5 * density * velocity ** 2
    return math.copysign(loss, mass_flow)


def _flow_for_pressure(dp, channel, density, minor_k):
    if dp == 0:
        return 0.0
    pressure = abs(dp)
    # Minor-loss-only velocity bounds the root from above, including laminar flow.
    low, high = 0.0, channel["area_m2"] * math.sqrt(2 * density * pressure / minor_k)
    for _ in range(43):
        mid = .5 * (low + high)
        if _pressure_drop(mid, channel, density, minor_k) < pressure:
            low = mid
        else:
            high = mid
    return math.copysign(.5 * (low + high), dp)


def _linear_solve(matrix, rhs):
    n = len(rhs)
    a = [list(row) + [rhs[i]] for i, row in enumerate(matrix)]
    for k in range(n):
        pivot = max(range(k, n), key=lambda i: abs(a[i][k]))
        a[k], a[pivot] = a[pivot], a[k]
        if abs(a[k][k]) < 1e-18:
            raise ArithmeticError("Singular nacelle pressure Jacobian")
        scale = a[k][k]
        a[k] = [v / scale for v in a[k]]
        for i in range(n):
            if i == k:
                continue
            scale = a[i][k]
            a[i] = [x - scale * y for x, y in zip(a[i], a[k])]
    return [row[-1] for row in a]


def _solve_pressure(metrics, boundary, drive_factor=1.0, loss_factor=1.0):
    rho = boundary["density_kg_m3"]
    dynamic = .5 * rho * boundary["airspeed_m_s"] ** 2
    pressure = {"main_ram": (dynamic * boundary["ram_recovery"] + boundary["main_propeller_pressure_pa"]) * drive_factor,
                "bypass_ram": (dynamic * boundary["bypass_ram_recovery"] + boundary["bypass_propeller_pressure_pa"]) * drive_factor,
                "lv_ram": (dynamic * boundary["lv_ram_recovery"] + boundary["lv_propeller_pressure_pa"]) * drive_factor,
                "top_exhaust": -dynamic * boundary["motor_exhaust_suction_coefficient"] * drive_factor,
                "lower_exhaust": -dynamic * boundary["exhaust_suction_coefficient"] * drive_factor}
    low, high = min(pressure.values()), max(pressure.values())
    for i, name in enumerate(INTERNAL_NODES):
        pressure[name] = low + (high - low) * (.75 - .22 * i)
    channels = metrics["channels"]
    ks = {name: edge[2] * boundary["loss_multiplier"] * loss_factor for name, edge in BRANCHES.items()}
    index = {name: i for i, name in enumerate(INTERNAL_NODES)}
    def state(p, jacobian=False):
        residual = [0.0] * len(index)
        jac = [[0.0] * len(index) for _ in index]
        flows = {}
        for name, (u, v, _) in BRANCHES.items():
            dp = p[u] - p[v]
            flow = _flow_for_pressure(dp, channels[name], rho, ks[name])
            flows[name] = flow
            if u in index:
                residual[index[u]] += flow
            if v in index:
                residual[index[v]] -= flow
            if not jacobian:
                continue
            # Differentiation in mass-flow space avoids an infinite sqrt slope.
            eps = max(1e-8, abs(flow) * 1e-5)
            derivative = (_pressure_drop(flow + eps, channels[name], rho, ks[name]) -
                          _pressure_drop(flow - eps, channels[name], rho, ks[name])) / (2 * eps)
            conductance = 1 / derivative
            for node, other in ((u, v), (v, u)):
                if node in index:
                    jac[index[node]][index[node]] += conductance
                    if other in index:
                        jac[index[node]][index[other]] -= conductance
        return flows, residual, jac
    converged, iterations = False, 0
    for iterations in range(1, 61):
        flows, residual, jac = state(pressure, True)
        error = max(map(abs, residual))
        if error < 1e-12:
            converged = True
            break
        update = _linear_solve(jac, [-r for r in residual])
        step = 1.0
        for _ in range(24):
            trial = dict(pressure)
            for name, i in index.items():
                trial[name] = max(low, min(high, pressure[name] + step * update[i]))
            _, rr, _ = state(trial)
            if max(map(abs, rr)) < error:
                pressure = trial
                break
            step *= .5
        else:
            break
    # A coordinate-bisection fallback retains monotonicity for extreme valid inputs.
    if not converged:
        for cycle in range(240):
            for node in INTERNAL_NODES:
                lo, hi = low, high
                for _ in range(50):
                    pressure[node] = .5 * (lo + hi)
                    _, rr, _ = state(pressure)
                    if rr[index[node]] > 0:
                        hi = pressure[node]
                    else:
                        lo = pressure[node]
                pressure[node] = .5 * (lo + hi)
            flows, residual, _ = state(pressure)
            if max(map(abs, residual)) < 1e-12:
                converged = True
                break
        iterations += cycle + 1
    flows, residual, _ = state(pressure)
    return pressure, flows, ks, {"converged": converged, "iterations": iterations,
                                 "dynamic_pressure_pa": dynamic,
                                 "mass_residuals_kg_s": dict(zip(INTERNAL_NODES, residual))}


def _branch_transport(channel, flow, density, fin=None, h_factor=1.0, ambient_c=35.9):
    aperture_speed = abs(flow) / (density * channel["area_m2"])
    channel = channel.get("heat_exchange", channel)
    speed = abs(flow) / (density * channel["area_m2"])
    dh = channel["hydraulic_diameter_m"]
    re = density * speed * dh / AIR["viscosity_pa_s"]
    pr = AIR["specific_heat_j_kg_k"] * AIR["viscosity_pa_s"] / AIR["conductivity_w_m_k"]
    friction, nu, regime = _friction_nusselt(re, pr)
    h = nu * AIR["conductivity_w_m_k"] / dh * h_factor
    eta = 1.0
    area = channel["heated_area_m2"]
    if fin:
        height, thickness = fin["fin_height_m"], fin["fin_thickness_m"]
        mh = math.sqrt(2 * h / (167 * thickness)) * height
        eta = math.tanh(mh) / mh if mh else 1.0
        # Geometry supplies fin side area when available; otherwise infer it from
        # the same count, height and streamwise length, capped at heated area.
        fin_area = min(area, fin.get("fin_area_m2", 2 * max(0, fin["fin_count"] - 1) * height * channel["length_m"]))
        area = (area - fin_area) + eta * fin_area
    capacity = abs(flow) * AIR["specific_heat_j_kg_k"]
    ua = h * area
    conductance = -capacity * math.expm1(-ua / capacity) if capacity and ua else 0.0
    return {"velocity_m_s": aperture_speed, "heat_exchange_velocity_m_s": speed, "heat_exchange_hydraulic_diameter_m": dh, "reynolds": re, "prandtl": pr, "darcy_friction_factor": friction,
            "nusselt": nu, "h_w_m2_k": h, "fin_efficiency": eta, "effective_heated_area_m2": area,
            "ua_w_k": ua, "air_capacity_w_k": capacity, "convective_conductance_w_k": conductance,
            "regime": regime, "mach_approx": max(speed, aperture_speed) / math.sqrt(1.4 * 287.05 * (ambient_c + 273.15))}


def _run(metrics, boundary, drive_factor=1.0, loss_factor=1.0, h_factor=1.0, contact_factor=1.0):
    pressures, flows, ks, solver = _solve_pressure(metrics, boundary, drive_factor, loss_factor)
    loads = {k: v * boundary["heat_scale"] for k, v in HEAT_LOADS[boundary["heat_load"]].items()}
    gap_surfaces = metrics["channels"]["motor_internal"]["heated_surfaces_m2"]
    slot_surfaces = metrics["channels"]["motor_slots"]["heated_surfaces_m2"]
    total_winding_area = gap_surfaces["motor_winding"] + slot_surfaces["motor_winding"]
    gap_winding_heat = loads["winding_w"] * gap_surfaces["motor_winding"] / total_winding_area
    slot_winding_heat = loads["winding_w"] - gap_winding_heat
    heat_by_branch = dict.fromkeys(BRANCHES, 0.0)
    heat_by_branch.update({"motor_internal": gap_winding_heat + .5 * loads["magnet_w"],
                           "motor_slots": slot_winding_heat,
                           "motor_bypass": .5 * loads["magnet_w"],
                           "cmc_hv_left": loads["hv_each_w"], "cmc_hv_right": loads["hv_each_w"],
                           "lv_fresh_left": loads["lv_each_w"], "lv_fresh_right": loads["lv_each_w"]})
    cp, ambient = AIR["specific_heat_j_kg_k"], boundary["ambient_c"]
    incoming = {node: [] for node in pressures}
    outgoing = {node: [] for node in pressures}
    branches = {}
    for name, (u, v, _) in BRANCHES.items():
        signed_flow = flows[name]
        upstream, downstream = (u, v) if signed_flow >= 0 else (v, u)
        fin = metrics["components"].get("cmc_" + name[7:] + "_hv") if name.startswith("cmc_hv_") else None
        item = _branch_transport(metrics["channels"][name], signed_flow, boundary["density_kg_m3"], fin, h_factor, boundary["ambient_c"])
        item.update({"id": name, "from_node": u, "to_node": v, "actual_from_node": upstream,
                     "actual_to_node": downstream, "mass_flow_kg_s": signed_flow,
                     "pressure_drop_pa": pressures[u] - pressures[v], "minor_loss_k": ks[name],
                     "heat_w": heat_by_branch[name], "inlet_c": None, "outlet_c": None,
                     "exchange_surface_c": None, "geometry": metrics["channels"][name]})
        branches[name] = item
        outgoing[upstream].append(name)
        incoming[downstream].append(name)
    node_temperatures = {}
    # Any signed pressure-driven edge points from high to low pressure. Sorting
    # produces a directed acyclic advection graph, including reversed branches.
    for node in sorted(pressures, key=lambda n: pressures[n], reverse=True):
        feeds = [branches[name] for name in incoming[node] if abs(flows[name]) > 1e-14]
        if node not in INTERNAL_NODES and outgoing[node]:
            temperature = ambient  # External reservoir supplies ambient air.
        elif feeds:
            if any(b["outlet_c"] is None for b in feeds):
                temperature = None
            else:
                temperature = sum(abs(b["mass_flow_kg_s"]) * b["outlet_c"] for b in feeds) / sum(abs(b["mass_flow_kg_s"]) for b in feeds)
        else:
            temperature = ambient if sum(heat_by_branch.values()) == 0 else None
        node_temperatures[node] = temperature
        for name in outgoing[node]:
            item = branches[name]
            q, capacity, conductance = item["heat_w"], item["air_capacity_w_k"], item["convective_conductance_w_k"]
            item["inlet_c"] = temperature
            if capacity > 1e-11 and temperature is not None:
                item["outlet_c"] = temperature + q / capacity
                item["exchange_surface_c"] = temperature + q / conductance if conductance else (temperature if not q else None)
            elif q == 0:
                item["outlet_c"] = item["exchange_surface_c"] = temperature
    components = {}
    def resistances(name):
        c = metrics["components"][name]
        conduction = c["conduction_length_m"] / (MATERIAL_K[name] * c["conduction_area_m2"])
        contact = CONTACT_K_W[name] * boundary["contact_multiplier"] * contact_factor
        return conduction, contact
    def add_component(name, temperature, q, channel, **extra):
        limit = MARGINED_LIMITS.get(name)
        conduction, contact = resistances(name)
        components[name] = {"id": name, "thermal_node": name, "temperature_c": temperature,
                            "limit_c": limit, "margin_c": limit - temperature if limit is not None and temperature is not None else None,
                            "heat_w": q, "conduction_resistance_k_w": conduction,
                            "contact_resistance_k_w": contact, "channel_id": channel,
                            "temperature_kind": "uncalibrated_lumped_proxy", **extra}
    def component_temp(name, surface, q):
        return surface + q * sum(resistances(name)) if surface is not None else None
    def motor_wall_surface(branch_name, component, q):
        branch = branches[branch_name]
        if branch["inlet_c"] is None or not branch["air_capacity_w_k"] or not branch["ua_w_k"]:
            return branch["inlet_c"] if q == 0 else None
        ntu = branch["ua_w_k"] / branch["air_capacity_w_k"]
        mean_factor = .5 + ntu / 12 - ntu ** 3 / 720 if ntu < 1e-4 else 1 / (-math.expm1(-ntu)) - 1 / ntu
        mean_air = branch["inlet_c"] + branch["heat_w"] / branch["air_capacity_w_k"] * mean_factor
        surface_area = metrics["channels"][branch_name]["heated_surfaces_m2"][component]
        surface = mean_air + q / (branch["h_w_m2_k"] * surface_area)
        branch.setdefault("heated_surface_temperatures_c", {})[component] = surface
        return surface
    gap_surface = motor_wall_surface("motor_internal", "motor_winding", gap_winding_heat)
    slot_surface = motor_wall_surface("motor_slots", "motor_winding", slot_winding_heat)
    gap_winding = component_temp("motor_winding", gap_surface, loads["winding_w"])
    slot_winding = component_temp("motor_winding", slot_surface, loads["winding_w"])
    winding = max(gap_winding, slot_winding) if gap_winding is not None and slot_winding is not None else None
    add_component("motor_winding", winding, loads["winding_w"], "motor_slots",
                  gap_patch_c=gap_winding, slot_patch_c=slot_winding, secondary_channel_id="motor_internal",
                  heat_by_branch_w={"motor_internal": gap_winding_heat, "motor_slots": slot_winding_heat})
    magnet_geometry = metrics["components"]["motor_magnet"]
    magnet_areas = magnet_geometry["conduction_patch_areas_m2"]
    _, magnet_contact = resistances("motor_magnet")
    magnet_patch_r = {patch: magnet_geometry["conduction_length_m"] / (MATERIAL_K["motor_magnet"] * area)
                      for patch, area in magnet_areas.items()}
    inner_wall = motor_wall_surface("motor_internal", "motor_magnet", .5 * loads["magnet_w"])
    outer_wall = branches["motor_bypass"]["exchange_surface_c"]
    magnet_inner = inner_wall + .5 * loads["magnet_w"] * (magnet_patch_r["inner"] + magnet_contact) if inner_wall is not None else None
    magnet_outer = outer_wall + .5 * loads["magnet_w"] * (magnet_patch_r["outer"] + magnet_contact) if outer_wall is not None else None
    magnet = max(magnet_inner, magnet_outer) if magnet_inner is not None and magnet_outer is not None else None
    add_component("motor_magnet", magnet, loads["magnet_w"], "motor_internal",
                  inner_surface_c=magnet_inner, outer_surface_c=magnet_outer, secondary_channel_id="motor_bypass",
                  conduction_patch_areas_m2=magnet_areas, patch_conduction_resistance_k_w=magnet_patch_r,
                  patch_contact_resistance_k_w={"inner": magnet_contact, "outer": magnet_contact},
                  resistance_note="Reported aggregate conduction resistance describes parallel area only; temperatures use individual patch L/(k A) and declared per-patch contact resistance.")
    for side in ("left", "right"):
        hv, lv = "cmc_" + side + "_hv", "cmc_" + side + "_lv"
        hv_channel, lv_channel = "cmc_hv_" + side, "lv_fresh_" + side
        add_component(hv, component_temp(hv, branches[hv_channel]["exchange_surface_c"], loads["hv_each_w"]), loads["hv_each_w"], hv_channel)
        plate = component_temp(lv, branches[lv_channel]["exchange_surface_c"], loads["lv_each_w"])
        scale = boundary["heat_scale"]
        add_component(lv, plate, 10 * scale, lv_channel, total_backplate_heat_w=loads["lv_each_w"],
                      temperature_kind="backplate_proxy_no_published_limit")
        for suffix, watts in (("cpu", 8), ("acdc", 12)):
            name, q = "cmc_" + side + "_" + suffix, watts * scale
            add_component(name, component_temp(name, plate, q), q, lv_channel, parent_backplate=lv)
    # Boundaries are open reservoirs; count their signed mass and enthalpy flux.
    external_in = external_out = external_in_energy = external_out_energy = 0.0
    for name, item in branches.items():
        flow = abs(item["mass_flow_kg_s"])
        if item["actual_from_node"] not in INTERNAL_NODES:
            external_in += flow
            if item["inlet_c"] is not None:
                external_in_energy += flow * cp * (item["inlet_c"] - ambient)
        if item["actual_to_node"] not in INTERNAL_NODES:
            external_out += flow
            if item["outlet_c"] is not None:
                external_out_energy += flow * cp * (item["outlet_c"] - ambient)
    heat = sum(heat_by_branch.values())
    finite_temperatures = [c["temperature_c"] for c in components.values() if c["temperature_c"] is not None]
    margins = [c for c in components.values() if c["margin_c"] is not None]
    limiting = min(margins, key=lambda c: c["margin_c"]) if margins else None
    steady = len(finite_temperatures) == len(components)
    mass_residual = max(map(abs, solver["mass_residuals_kg_s"].values()))
    pressure_residual = max(abs(item["pressure_drop_pa"] - _pressure_drop(item["mass_flow_kg_s"], metrics["channels"][name], boundary["density_kg_m3"], ks[name])) for name, item in branches.items())
    energy_residual = heat + external_in_energy - external_out_energy
    warnings = ["Uncalibrated geometry-linked reduced-order model; temperatures and margins are illustrative proxies, not validated NASA predictions."]
    if not steady:
        warnings.append("No finite forced-flow equilibrium on one or more heated paths. Natural convection and radiation are omitted; null temperatures are intentional.")
    if any(item["mass_flow_kg_s"] < -1e-10 for item in branches.values()):
        warnings.append("One or more branches reverse under these pressure boundaries. Signed flow and heat mixing are solved; the intended cooling topology is not maintained.")
    if any(item["regime"] == "transition_unvalidated" for item in branches.values()):
        warnings.append("At least one path uses unvalidated transition interpolation (2300 <= Re < 4000).")
    flow_valid = all(item["mach_approx"] < .3 and item["reynolds"] <= 1e6 for item in branches.values()) and max(pressures.values()) - min(pressures.values()) < .1 * AIR["reference_pressure_pa"]
    thermal_valid = steady and max(finite_temperatures, default=ambient) <= 200
    if not flow_valid:
        warnings.append("Mach >= 0.3, Re > 1e6 or pressure range >= 10% reference pressure exceeds the declared incompressible/correlation screening envelope.")
    if steady and not thermal_valid:
        warnings.append("A temperature proxy exceeds 200 C; fixed-property thermal approximation is outside its declared screening envelope.")
    if not solver["converged"]:
        warnings.append("Pressure network did not converge; do not use this result.")
    if limiting and limiting["margin_c"] < 0:
        warnings.append("At least one illustrative component proxy exceeds its NASA margined reference limit; this is not an airworthiness assessment.")
    nodes = {n: {"id": n, "pressure_pa": pressures[n], "temperature_c": node_temperatures[n],
                 "external_reservoir": n not in INTERNAL_NODES} for n in pressures}
    hydraulic_power = sum(abs(item["pressure_drop_pa"] * item["mass_flow_kg_s"]) / boundary["density_kg_m3"] for item in branches.values())
    return {"flow": {"branches": branches, "nodes": nodes, "total_inlet_kg_s": external_in,
                     "total_outlet_kg_s": external_out, "pressure_drive_pa": max(pressures.values()) - min(pressures.values()),
                     "hydraulic_dissipation_w": hydraulic_power,
                     "power_note": "Passive pressure loss, not blower electrical power or complete aircraft cooling drag."},
            "thermal": {"components": components, "summary": {
                "max_temperature_c": max(finite_temperatures) if steady else None,
                "min_margin_c": limiting["margin_c"] if steady and limiting else None,
                "limiting_component": limiting["id"] if steady and limiting else None,
                "steady_state_exists": steady, "total_heat_w": heat,
                "result_status": ("no_forced_flow_equilibrium" if not steady else "out_of_domain_diagnostic" if not (flow_valid and thermal_valid) else "uncalibrated_screening_result"),
                "physically_validated": False,
                "within_model_limits": flow_valid and thermal_valid and solver["converged"],
                "all_reference_margins_nonnegative": all(c["margin_c"] >= 0 for c in margins) if steady else None}},
            "diagnostics": {**solver, "max_mass_residual_kg_s": mass_residual,
                            "external_mass_residual_kg_s": external_in - external_out,
                            "max_pressure_residual_pa": pressure_residual,
                            "energy_residual_w": energy_residual,
                            "energy_removed_w": external_out_energy - external_in_energy,
                            "total_heat_w": heat, "steady_energy_balance_evaluable": steady,
                            "conservation_pass": solver["converged"] and mass_residual < 1e-8 and steady and abs(energy_residual) < 1e-5},
            "warnings": warnings}


def _uncertainty(metrics, boundary, nominal):
    # Scenario ranges, not a statistical CI or a guaranteed global envelope.
    scenarios = []
    values = {name: [] for name in MATERIAL_K}
    for drive, loss in itertools.product((.75, 1.25), (.5, 2.0)):
        for thermal_case, h, contact in (("lower_resistance", 1.4, .5), ("higher_resistance", .6, 2.0)):
            result = _run(metrics, boundary, drive, loss, h, contact)
            scenarios.append({"drive_factor": drive, "minor_loss_factor": loss,
                              "h_factor": h, "contact_factor": contact, "thermal_case": thermal_case,
                              "total_inlet_kg_s": result["flow"]["total_inlet_kg_s"],
                              **result["thermal"]["summary"]})
            for name, component in result["thermal"]["components"].items():
                if component["temperature_c"] is not None:
                    values[name].append(component["temperature_c"])
    def span(numbers):
        return {"min": min(numbers), "max": max(numbers)} if numbers else {"min": None, "max": None}
    for name, component in nominal["thermal"]["components"].items():
        if component["temperature_c"] is not None:
            values[name].append(component["temperature_c"])
    return {"kind": "uncalibrated_screening_scenario_range", "scenario_count": len(scenarios),
            "note": "Selected assumption corners plus nominal; not confidence intervals, calibrated error bars, guaranteed extrema, or certification margins. Geometry dimensional uncertainty and heat-load uncertainty are not sampled.",
            "factors": {"pressure_drive": [.75, 1.25], "minor_loss": [.5, 2], "heat_transfer_h": [.6, 1.4], "contact_resistance": [.5, 2]},
            "component_temperature_c": {name: span(numbers) for name, numbers in values.items()},
            "total_inlet_kg_s": span([s["total_inlet_kg_s"] for s in scenarios] + [nominal["flow"]["total_inlet_kg_s"]]),
            "min_margin_c": span([s["min_margin_c"] for s in scenarios if s["min_margin_c"] is not None] + ([nominal["thermal"]["summary"]["min_margin_c"]] if nominal["thermal"]["summary"]["min_margin_c"] is not None else [])),
            "scenarios": scenarios}


def evaluate_nacelle(geometry=None, boundary=None):
    p, b = parse_nacelle(geometry), parse_nacelle_boundary(boundary)
    metrics = nacelle_metrics(p)
    _validate_metrics(metrics)
    result = _run(metrics, b)
    source_hash = MODEL_SOURCE_SHA256
    payload = {"model": MODEL_ID, "geometry": p.to_dict(), "boundary": b, "model_sha256": source_hash}
    input_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    result.update({"geometry": p.to_dict(), "metrics": metrics, "boundary": b,
                   "model_id": MODEL_ID, "model_sha256": source_hash, "module_source_sha256": MODULE_SOURCE_SHA256.copy(), "input_hash": input_hash,
                   "execution": "computed", "uncertainty": _uncertainty(metrics, b, result),
                   "provenance": {"source_url": SOURCE_URL,
                       "source_facts": {"topology": "Printed pp. 7-8, Figs. 5-7 and p. 8 flowpath description", "heat_loads": "Table 4, printed p. 5", "reference_limits": "Table 1, printed p. 3", "flight_conditions": "Table 3, printed p. 4"},
                       "assumptions": ASSUMPTIONS, "air": AIR,
                       "minor_loss_k": {n: e[2] for n, e in BRANCHES.items()},
                       "material_conductivity_w_m_k": MATERIAL_K, "contact_resistance_k_w": CONTACT_K_W,
                       "lv_inferred_heat_split_w": {"cpu": 8, "acdc": 12, "other_boards": 10},
                       "correlation_reference": CORRELATION_URL, "calibrated": False,
                       "source_validation_limit": "NASA paper reports no experimental nacelle airflow validation; this lower-fidelity reconstruction has no such validation either.",
                       "computed": "CAD hydraulic dimensions -> pressure/mass conservation -> heat advection/mixing -> lumped solid resistance proxies. No CFD heatfield."}})
    gap_source, slots_source, bypass_source = .100 * .45359237, .458 * .45359237, .237 * .45359237
    result["source_flow_diagnostic"] = {
        "source": SOURCE_URL, "location": "Table 7, printed p. 15, initial takeoff climb stations 2a_g, 2a_s, 2a_b",
        "note": "Published CFD station flows are a diagnostic reference, not boundary inputs or calibration targets. Our reconstructed geometry and inferred pressure boundaries are not a matched NASA CFD case.",
        "published_kg_s": {"motor_gap": gap_source, "motor_slots": slots_source, "motor_internal_total": gap_source + slots_source, "motor_bypass": bypass_source},
        "computed_kg_s": {"motor_gap": result["flow"]["branches"]["motor_internal"]["mass_flow_kg_s"],
                           "motor_slots": result["flow"]["branches"]["motor_slots"]["mass_flow_kg_s"],
                           "motor_internal_total": result["flow"]["branches"]["motor_internal"]["mass_flow_kg_s"] + result["flow"]["branches"]["motor_slots"]["mass_flow_kg_s"],
                           "motor_bypass": result["flow"]["branches"]["motor_bypass"]["mass_flow_kg_s"]},
        "used_to_fit_coefficients": False, "validation": False}
    source_temps = {"motor_winding": 109.4, "motor_magnet": 45.4,
                    "cmc_left_hv": 104.9, "cmc_right_hv": 104.9,
                    "cmc_left_cpu": 75.1, "cmc_right_cpu": 75.1,
                    "cmc_left_acdc": 75.6, "cmc_right_acdc": 75.6}
    result["source_temperature_diagnostic"] = {
        "source": SOURCE_URL, "location": "Table 6, printed p. 12, initial takeoff climb",
        "note": "Published CFD-driven ICPT component estimates, not measured temperatures. One published component estimate is repeated for left/right context; our lumped patches/contact proxies and boundary assumptions are not node-equivalent NASA predictions. No coefficient fitting.",
        "published_analysis_c": source_temps,
        "computed_proxy_c": {name: result["thermal"]["components"][name]["temperature_c"] for name in source_temps},
        "used_to_fit_coefficients": False, "validation": False}
    return result


def compare_nacelle(geometry=None, boundary=None):
    reference, candidate = evaluate_nacelle(None, boundary), evaluate_nacelle(geometry, boundary)
    delta = {"mass_kg": candidate["metrics"]["mass_kg"] - reference["metrics"]["mass_kg"],
             "total_inlet_kg_s": candidate["flow"]["total_inlet_kg_s"] - reference["flow"]["total_inlet_kg_s"]}
    for name in ("max_temperature_c", "min_margin_c"):
        a, b = candidate["thermal"]["summary"][name], reference["thermal"]["summary"][name]
        delta[name] = a - b if a is not None and b is not None else None
    delta["component_temperature_c"] = {name: candidate["thermal"]["components"][name]["temperature_c"] - c["temperature_c"]
        if candidate["thermal"]["components"][name]["temperature_c"] is not None and c["temperature_c"] is not None else None
        for name, c in reference["thermal"]["components"].items()}
    return {"reference": reference, "candidate": candidate, "delta": delta,
            "note": "Same pressure-boundary assumptions and heat loads; each geometry solves its own branch flows. Improvement is not guaranteed and scenario ranges are not validation."}
