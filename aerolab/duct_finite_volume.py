"""Verified laminar parallel-plate subproblem; independent of the X-57 ROM.

Cell-centred finite volumes solve momentum across the gap and march the
steady Graetz energy equation downstream. Both walls receive independently
specified signed heat fluxes. A local, exact through-thickness solid
reconstruction is provided, NOT a multidimensional conjugate or rotating-motor
CFD solution.
Python standard library only; see docs/DUCT_SUBMODEL.md for equations/scope.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
from pathlib import Path


MODEL_ID = "parallel-plate-graetz-finite-volume-v1"
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
NU_FULLY_DEVELOPED = 140.0 / 17.0
ABSOLUTE_ZERO_C = -273.15
DEFAULT_CASE = {
    "gap_m": .004, "span_m": .08, "length_m": .2,
    "mean_velocity_m_s": 1.0, "inlet_c": 25.0,
    "density_kg_m3": 1.2, "viscosity_pa_s": 1.8e-5,
    "conductivity_w_m_k": .026, "specific_heat_j_kg_k": 1005.0,
    "left_heat_flux_w_m2": 200.0, "right_heat_flux_w_m2": 200.0,
    "wall_thickness_m": .002,
    "wall_conductivity_w_m_k": 167.0,
    "transverse_cells": 64, "axial_cells": 400,
    "axial_stretch": 2.0, "inlet_profile": "uniform",
    "axial_samples": 17, "transverse_samples": 17,
}
_LIMITS = {
    "gap_m": (1e-4, .1), "span_m": (1e-3, 10), "length_m": (1e-3, 20),
    "mean_velocity_m_s": (-30, 30), "inlet_c": (-100, 500),
    "density_kg_m3": (.1, 2000), "viscosity_pa_s": (1e-6, .1),
    "conductivity_w_m_k": (.001, 100), "specific_heat_j_kg_k": (100, 10000),
    "left_heat_flux_w_m2": (-10000, 10000), "right_heat_flux_w_m2": (-10000, 10000), "wall_thickness_m": (0, .1),
    "wall_conductivity_w_m_k": (.01, 1000), "axial_stretch": (1, 3),
}
_INTEGERS = {"transverse_cells": (4, 256), "axial_cells": (4, 8192),
             "axial_samples": (2, 65), "transverse_samples": (3, 65)}
SCOPE = [
    "Verification of an ideal laminar subproblem, not physical validation of an aircraft.",
    "Infinite parallel plates with a specified reporting span; no spanwise sidewall effects.",
    "Hydrodynamically developed, constant-property, steady incompressible flow.",
    "Independent uniform signed heat fluxes on the two walls; no imposed thermal symmetry.",
    "No axial heat conduction, buoyancy, viscous heating, radiation, rotation or turbulence.",
    "Solid temperatures use local 1D conduction; no axial/spreading/contact resistance.",
    "No connection, fitted coefficient or calibration transfer to the nacelle ROM.",
]


def parse_case(case=None):
    """Strict bounded input contract. Zero flow is handled explicitly in solve_duct."""
    if case is None:
        case = {}
    if not isinstance(case, Mapping):
        raise ValueError("case must be a mapping")
    unknown = set(case) - set(DEFAULT_CASE)
    if unknown:
        raise ValueError("unknown case fields: " + ", ".join(sorted(map(str, unknown))))
    result = dict(DEFAULT_CASE)
    result.update(case)
    for key, (low, high) in _LIMITS.items():
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(f"{key} must be a finite number")
        try:
            value = float(value)
        except OverflowError as exc:
            raise ValueError(f"{key} must be a bounded finite number") from exc
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key} must be in [{low}, {high}]")
        result[key] = value
    for key, (low, high) in _INTEGERS.items():
        value = result[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} must be an integer in [{low}, {high}]")
    if result["inlet_profile"] not in ("uniform", "fully_developed"):
        raise ValueError("inlet_profile must be uniform or fully_developed")
    if result["transverse_cells"] * result["axial_cells"] > 1000000:
        raise ValueError("transverse_cells * axial_cells must not exceed 1000000")
    return result


def _tridiagonal(lower, diagonal, upper, rhs):
    """Thomas elimination for strictly positive definite discretizations."""
    diagonal, rhs = list(diagonal), list(rhs)
    for i in range(1, len(rhs)):
        factor = lower[i] / diagonal[i - 1]
        diagonal[i] -= factor * upper[i - 1]
        rhs[i] -= factor * rhs[i - 1]
    result = [0.0] * len(rhs)
    result[-1] = rhs[-1] / diagonal[-1]
    for i in range(len(rhs) - 2, -1, -1):
        result[i] = (rhs[i] - upper[i] * result[i + 1]) / diagonal[i]
    return result


def _residual(lower, diagonal, upper, rhs, values):
    worst = 0.0
    for i, value in enumerate(values):
        terms = [diagonal[i] * value, -rhs[i]]
        if i:
            terms.append(lower[i] * values[i - 1])
        if i + 1 < len(values):
            terms.append(upper[i] * values[i + 1])
        worst = max(worst, abs(math.fsum(terms)))
    return worst


def _velocity(n):
    h = 2.0 / n
    diagonal = [2.0] * n
    diagonal[0], diagonal[-1] = 3.0, 3.0
    lower, upper = [-1.0] * n, [-1.0] * n
    lower[0], upper[-1] = 0.0, 0.0
    rhs = [h * h] * n
    raw = _tridiagonal(lower, diagonal, upper, rhs)
    mean = math.fsum(raw) / n
    velocity = [value / mean for value in raw]
    forcing = 1.0 / mean
    residual = _residual(lower, diagonal, upper, rhs, raw) / (h * h)
    return velocity, forcing, residual


def _fully_developed(velocity, left=1.0, right=1.0):
    """Discrete FV solution with arbitrary fluxes and weighted-mean theta=0."""
    n = len(velocity)
    h = 2.0 / n
    temperature, gradient = [0.0], -left
    average_flux = .5 * (left + right)
    for i in range(1, n):
        gradient += average_flux * velocity[i - 1] * h
        temperature.append(temperature[-1] + gradient * h)
    bulk = math.fsum(v * t for v, t in zip(velocity, temperature)) / math.fsum(velocity)
    return [value - bulk for value in temperature]


def fully_developed_reference(eta, left=1.0, right=1.0):
    """Continuum solution, eta=y/(gap/2) in [-1,1], fluxes divided by q_ref.

    For either wall i, (k/Dh)(Tw_i-Tb) = (13/70)q_i-(9/140)q_other.
    A weakly heated wall can therefore be below the mixed bulk temperature.
    """
    for key, value in (("eta", eta), ("left", left), ("right", right)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{key} must be finite")
    if not -1 <= eta <= 1:
        raise ValueError("eta must be in [-1, 1]")
    symmetric = .75 * eta**2 - .125 * eta**4 - 39 / 280
    return {"velocity_over_mean": 1.5 * (1 - eta * eta),
            "temperature_minus_bulk_over_qref_b_k":
                .5 * (left + right) * symmetric + .5 * (right - left) * eta}


def solve_duct(case=None):
    """Conservative fluid-cell samples, local solid conduction and provenance.

    Signed velocity reverses physical inlet/outlet; s always goes downstream.
    Negative flux cools. Heated zero-flow cases have no determined advective
    steady state: return null temperatures, never a fake numerical cap.
    Nonzero cases require Re_Dh <= 2000, Pe_Dh >= 50 and Pe_length >= 50.
    Any computed fluid, wall or local solid temperature at/below absolute zero
    is rejected, scanning all marched states rather than just output samples.
    """
    p = parse_case(case)
    n, nx = p["transverse_cells"], p["axial_cells"]
    b, length, span = p["gap_m"] / 2, p["length_m"], p["span_m"]
    speed = abs(p["mean_velocity_m_s"])
    flux = {"left": p["left_heat_flux_w_m2"], "right": p["right_heat_flux_w_m2"]}
    qref = max(abs(value) for value in flux.values())
    rho, mu, k, cp = (p[key] for key in ("density_kg_m3", "viscosity_pa_s",
                                      "conductivity_w_m_k", "specific_heat_j_kg_k"))
    dh = 4 * b
    reynolds, peclet = rho * speed * dh / mu, rho * cp * speed * dh / k
    axial_peclet = rho * cp * speed * length / k
    if speed and (reynolds > 2000 or peclet < 50 or axial_peclet < 50):
        raise ValueError("nonzero flow requires Re_Dh <= 2000, Pe_Dh >= 50 and Pe_length >= 50")
    direction = 1 if p["mean_velocity_m_s"] >= 0 else -1
    mass_flow = rho * p["mean_velocity_m_s"] * 2 * b * span
    heat = math.fsum(flux.values()) * length * span
    source_input = json.dumps(p, sort_keys=True, separators=(",", ":"), allow_nan=False)
    metadata = {
        "model_id": MODEL_ID, "source_sha256": SOURCE_SHA256,
        "input_sha256": hashlib.sha256(source_input.encode()).hexdigest(),
        "case": p, "arithmetic": "IEEE-754 binary64; standard-library-only",
        "algorithm": "cell-centred FV; direct tridiagonal solves; backward-Euler axial marching",
        "grid": {"transverse_full_gap_cells": n, "axial_cells": nx,
                 "total_marched_cells": n * nx, "axial_stretch": p["axial_stretch"],
                 "transverse_order": 2, "axial_order": 1},
        "scope": list(SCOPE), "experimental_validation": False,
        "spatial_field_type": "computed full-gap fluid cells; sampled, not a 3D CFD mesh",
    }
    result = {
        "provenance": metadata, "status": "solved",
        "hydraulics": {"mass_flow_kg_s": mass_flow, "reynolds_dh": reynolds,
                       "peclet_dh": peclet, "peclet_length": axial_peclet, "prandtl": mu * cp / k,
                       "hydraulic_diameter_m": dh, "flow_direction": direction if speed else 0},
        "thermal": {"wall_heat_w": heat, "inlet_c": p["inlet_c"],
                    "wall_flux_w_m2": flux, "reference_flux_w_m2": qref},
    }
    if not speed:
        temperature = p["inlet_c"] if qref == 0 else None
        result["status"] = ("isothermal_zero_flow" if qref == 0 else
                            "undetermined_zero_flow_temperature" if heat == 0 else
                            "no_steady_state_zero_flow")
        result["hydraulics"].update(signed_pressure_drop_pa=0.0, darcy_friction_factor=None,
                                    darcy_f_re=None, velocity_samples=[])
        result["thermal"].update(outlet_bulk_c=temperature,
                                  outlet_wall_c={side: temperature for side in flux},
                                  outlet_solid_outer_c={side: temperature for side in flux},
                                  outlet_nusselt={side: None for side in flux},
                                  axial_samples=[], outlet_profile=[])
        result["diagnostics"] = {"converged": qref == 0, "energy_residual_w": -heat,
                                 "energy_removed_w": 0.0,
                                 "reason": "No advective removal at zero flow. Opposing balanced fluxes leave absolute temperature undetermined without an extra thermal datum."}
        return result
    velocity, forcing, momentum_residual = _velocity(n)
    h = 2.0 / n
    ratios = {side: value / qref if qref else 0.0 for side, value in flux.items()}
    average_flux = .5 * math.fsum(ratios.values())
    fd = _fully_developed(velocity, **ratios)
    fd_wall = {"left": fd[0] + ratios["left"] * h / 2,
               "right": fd[-1] + ratios["right"] * h / 2}
    zeta_end = k * length / (rho * cp * speed * b * b)
    theta = [0.0] * n if p["inlet_profile"] == "uniform" else list(fd)
    initial_bulk = math.fsum(v * t for v, t in zip(velocity, theta)) / n
    scale = qref * b / k
    wall_rise = {side: value * p["wall_thickness_m"] / p["wall_conductivity_w_m_k"]
                 for side, value in flux.items()}
    minimum_temperature = p["inlet_c"]
    minimum_temperature_location = "inlet bulk datum"

    def check_absolute_temperatures(step, include_walls=True):
        nonlocal minimum_temperature, minimum_temperature_location
        candidates = [(p["inlet_c"] + scale * value, f"fluid cell {i}")
                      for i, value in enumerate(theta)]
        if include_walls:
            # Local solid conduction is linear in depth, so both endpoints
            # bound every point in each solid, including unreturned samples.
            for side, index in (("left", 0), ("right", -1)):
                wall = p["inlet_c"] + scale * (theta[index] + ratios[side] * h / 2)
                candidates.append((wall, f"{side} fluid-wall interface"))
                candidates.append((wall + wall_rise[side], f"{side} solid outer face"))
        value, location = min(candidates)
        if value <= ABSOLUTE_ZERO_C:
            raise ValueError(
                f"nonphysical absolute temperature at axial face {step}, {location}: "
                f"{value:.12g} C is at/below absolute zero ({ABSOLUTE_ZERO_C} C); "
                "the prescribed constant-property case is inadmissible, not clipped")
        if value < minimum_temperature:
            minimum_temperature = value
            minimum_temperature_location = f"axial face {step}, {location}"

    # At a uniform inlet the heated-wall corner has no reconstructed solid
    # temperature. The fully developed inlet has well-defined wall values.
    check_absolute_temperatures(0, include_walls=p["inlet_profile"] == "fully_developed")
    sample_indices = set(round(j * nx / (p["axial_samples"] - 1)) for j in range(p["axial_samples"]))
    sample_indices.add(nx)
    transverse_indices = sorted(set(round(j * (n - 1) / (p["transverse_samples"] - 1))
                                    for j in range(p["transverse_samples"])))

    def nusselt(side, delta):
        # A negative signed h/Nu is possible for asymmetric heating; it is not
        # clipped. Separate-wall Newton cooling is not an independent closure.
        return 4 * ratios[side] / delta if ratios[side] and abs(delta) > 1e-14 else None

    def sample(step, zeta):
        bulk = math.fsum(v * t for v, t in zip(velocity, theta)) / n
        inlet_corner = step == 0 and p["inlet_profile"] == "uniform"
        wall = {"left": theta[0] + ratios["left"] * h / 2,
                "right": theta[-1] + ratios["right"] * h / 2}
        if inlet_corner:
            wall = {side: 0.0 for side in flux}
        s = length * (step / nx)**p["axial_stretch"]
        delta = {side: value - bulk for side, value in wall.items()}
        return {"axial_face_index": step, "s_from_inlet_m": s,
                "x_physical_m": s if direction > 0 else length - s, "zeta": zeta,
                "bulk_c": p["inlet_c"] + scale * bulk,
                "wall_c": {side: p["inlet_c"] + scale * value for side, value in wall.items()},
                "solid_outer_c": {side: None if inlet_corner else
                                   p["inlet_c"] + scale * wall[side] + wall_rise[side] for side in flux},
                "wall_minus_bulk_over_qref_b_k": delta,
                "nusselt_dh": {side: nusselt(side, value) for side, value in delta.items()},
                "fluid_c": [p["inlet_c"] + scale * theta[i] for i in transverse_indices]}

    samples = [sample(0, 0.0)]
    max_energy_error, max_linear_residual, previous_zeta = 0.0, 0.0, 0.0
    for step in range(1, nx + 1):
        zeta = zeta_end * (step / nx)**p["axial_stretch"]
        dz = zeta - previous_zeta
        capacity = [v * h / dz for v in velocity]
        diagonal = [value + 2 / h for value in capacity]
        diagonal[0] -= 1 / h
        diagonal[-1] -= 1 / h
        lower, upper = [-1 / h] * n, [-1 / h] * n
        lower[0], upper[-1] = 0.0, 0.0
        rhs = [c * t for c, t in zip(capacity, theta)]
        rhs[0] += ratios["left"]
        rhs[-1] += ratios["right"]
        theta = _tridiagonal(lower, diagonal, upper, rhs)
        check_absolute_temperatures(step)
        residual = _residual(lower, diagonal, upper, rhs, theta)
        max_linear_residual = max(max_linear_residual, residual)
        bulk = math.fsum(v * t for v, t in zip(velocity, theta)) / n
        max_energy_error = max(max_energy_error, abs(bulk - initial_bulk - average_flux * zeta))
        if step in sample_indices:
            samples.append(sample(step, zeta))
        previous_zeta = zeta
    outlet = samples[-1]
    pressure_gradient = forcing * mu * speed / (b * b)
    darcy_f_re = 32 * forcing
    energy_removed = abs(mass_flow) * cp * scale * (bulk - initial_bulk)
    energy_residual = energy_removed - heat
    result["hydraulics"].update({
        "signed_pressure_drop_pa": direction * pressure_gradient * length,
        "darcy_friction_factor": darcy_f_re / reynolds, "darcy_f_re": darcy_f_re,
        "exact_darcy_f_re": 96.0,
        "wall_shear_pa": {"left": mu * speed * velocity[0] / (b * h / 2),
                          "right": mu * speed * velocity[-1] / (b * h / 2)},
        "hydraulic_dissipation_w": pressure_gradient * length * abs(mass_flow) / rho,
        "velocity_samples": [{"eta": -1 + (i + .5) * h,
                              "y_from_midplane_m": b * (-1 + (i + .5) * h),
                              "velocity_m_s": direction * speed * velocity[i]} for i in transverse_indices],
    })
    result["thermal"].update({
        "outlet_bulk_c": outlet["bulk_c"], "outlet_wall_c": outlet["wall_c"],
        "outlet_solid_outer_c": outlet["solid_outer_c"], "outlet_nusselt": outlet["nusselt_dh"],
        "dimensionless_length_zeta": zeta_end,
        "fully_developed_wall_offset_on_grid": fd_wall,
        "fully_developed_nusselt_on_grid": {side: nusselt(side, value) for side, value in fd_wall.items()},
        "exact_equal_flux_nusselt": NU_FULLY_DEVELOPED,
        "axial_samples": samples,
        "sample_eta": [-1 + (i + .5) * h for i in transverse_indices],
        "outlet_profile": [{"eta": -1 + (i + .5) * h,
                            "temperature_c": p["inlet_c"] + scale * theta[i],
                            "temperature_minus_bulk_over_qref_b_k": theta[i] - bulk}
                           for i in transverse_indices],
        "outlet_solid_profile": {side: [
            {"depth_from_fluid_m": p["wall_thickness_m"] * fraction,
             "temperature_c": outlet["wall_c"][side] + wall_rise[side] * fraction}
            for fraction in (0, .25, .5, .75, 1)] for side in flux},
    })
    result["diagnostics"] = {
        "converged": (abs(energy_residual) < 1e-8 * max(1, abs(heat))
                      and max_linear_residual < 1e-7 and momentum_residual < 1e-7),
        "momentum_max_residual_over_forcing": momentum_residual,
        "thermal_max_cell_residual_over_reference_flux": max_linear_residual,
        "max_bulk_energy_error_dimensionless": max_energy_error,
        "energy_removed_w": energy_removed, "energy_residual_w": energy_residual,
        "momentum_linear_solves": 1, "thermal_linear_solves": nx,
        "absolute_temperature_admissible": True,
        "minimum_computed_temperature_c": minimum_temperature,
        "minimum_temperature_location": minimum_temperature_location,
        "absolute_temperature_checked_axial_states": nx + 1,
        "warning": "Numerical convergence does not establish experimental or aircraft validation.",
    }
    if not all(math.isfinite(t) for t in theta):
        raise ArithmeticError("non-finite temperature in bounded solve")
    return result
