#!/usr/bin/env python3
"""Independent calculations for NACELLE_THERMAL_PHYSICS_AUDIT_2026-09-30.md.

Run from any directory:
    python docs/research/verify_thermal_subcase_references.py --check

Prints a JSON report; writes no files and imports no production aerolab modules.
Dependencies used when first checked: numpy 2.3.5, scipy 1.17.0, mpmath 1.3.0.

Scope: no-slip, stationary, fully developed incompressible laminar ducts;
constant properties; no entrance/minor losses, buoyancy, rotation or dissipation.
The Gnielinski item is formula regression only, not a laminar calculation.
Historical channel dimensions are full gap/width, NOT half dimensions.
Source links and all limitations are recorded in the companion research note.
"""
from __future__ import annotations

import argparse
import json
import math

import mpmath as mp
import numpy as np
import scipy
from scipy.sparse import diags, eye, kron
from scipy.sparse.linalg import spsolve


def rectangular_reference():
    """Exact Fourier-series flow and an independent cell-centered FV solve."""
    gap, width, length = 0.002, 0.017, 0.105  # m, full dimensions
    rho, mu, cp, conductivity = 1.02, 1.90e-5, 1007.0, 0.027  # SI
    dh = 2 * gap * width / (gap + width)
    series = sum(math.tanh(n * math.pi * width / (2 * gap)) / n**5
                 for n in range(1, 2000, 2))
    correction = 1 - 192 * gap / (math.pi**5 * width) * series
    # U divided by (G/mu), where G=-dp/dx; this has dimensions m^2.
    exact_normalized_mean = gap**2 * correction / 12
    exact_po = 2 * dh**2 / exact_normalized_mean  # Darcy f * Re_Dh

    def negative_second_derivative(n, spacing):
        # Interior face conductance=1/dx^2. Boundary face is half a
        # cell from its center, so boundary diagonal is 2+1 rather than 1+1.
        diagonal = np.full(n, 2.0)
        diagonal[[0, -1]] = 3.0
        return diags((-np.ones(n - 1), diagonal, -np.ones(n - 1)),
                     (-1, 0, 1), format="csr") / spacing**2

    grids = []
    for nx in (8, 16, 32, 64):
        ny = round(nx * width / gap)
        operator = (kron(eye(ny), negative_second_derivative(nx, gap / nx))
                    + kron(negative_second_derivative(ny, width / ny), eye(nx)))
        operator = operator.tocsr()
        # -Laplacian u = 1 with no-slip u=0 at all four physical walls.
        field = spsolve(operator, np.ones(nx * ny))
        mean = float(field.mean())
        grids.append({"gap_cells": nx, "width_cells": ny,
                      "normalized_mean_velocity_m2": mean,
                      "darcy_f_re": 2 * dh**2 / mean,
                      "mean_velocity_relative_error": mean / exact_normalized_mean - 1,
                      "linear_residual_max": float(np.max(np.abs(operator @ field - 1)))})

    reynolds = 500.0
    speed = reynolds * mu / (rho * dh)
    dp = exact_po / reynolds * length / dh * rho * speed**2 / 2
    pr = mu * cp / conductivity
    turbulent_re = 10000.0
    friction = (0.790 * math.log(turbulent_re) - 1.64)**-2
    nu = ((friction / 8) * (turbulent_re - 1000) * pr
          / (1 + 12.7 * math.sqrt(friction / 8) * (pr**(2 / 3) - 1)))
    return {
        "full_gap_m": gap, "full_width_m": width, "length_m": length,
        "density_kg_m3": rho, "dynamic_viscosity_pa_s": mu,
        "hydraulic_diameter_m": dh, "highest_odd_series_term": 1999,
        "normalized_exact_mean_velocity_m2": exact_normalized_mean,
        "exact_darcy_f_re": exact_po, "finite_volume_grids": grids,
        "laminar_case": {"reynolds": reynolds, "mean_velocity_m_s": speed,
                         "mass_flow_kg_s": rho * speed * gap * width,
                         "pressure_drop_pa": dp},
        "gnielinski_formula_regression_only": {
            "reynolds": turbulent_re, "prandtl": pr,
            "specific_heat_j_kg_k": cp, "conductivity_w_m_k": conductivity,
            "darcy_friction_factor": friction, "nusselt": nu,
            "h_w_m2_k": nu * conductivity / dh,
            "required_mean_velocity_m_s": turbulent_re * mu / (rho * dh),
            "is_source_test_condition": False},
    }


def annulus_response(radius_ratio):
    """Integrate momentum/thermal equations, with ro=1 for nondimensional M.

    Returned matrix M satisfies [Tw_i-Tb,Tw_o-Tb] = (Dh/k) M [q_i,q_o].
    q_i and q_o are inward wall heat fluxes in W/m^2. Tb is the velocity-
    weighted bulk temperature. A separate arbitrary constant is removed by
    enforcing integral u*r*(T-Tb) dr=0, not by prescribing a wall temperature.
    """
    ri, ro = mp.mpf(radius_ratio), mp.mpf(1)
    logarithm = mp.log(ro / ri)
    b = (ro**2 - ri**2) / logarithm
    dh = 2 * (ro - ri)

    def u(r):
        # Velocity up to a common positive G/(4 mu) factor.
        return ro**2 - r**2 - b * mp.log(ro / r)

    ci = ri**2 * logarithm / 2 + ri**2 / 4

    def integral_ru(r):
        return (ro**2 * (r**2 - ri**2) / 2 - (r**4 - ri**4) / 4
                - b * (r**2 * mp.log(ro / r) / 2 + r**2 / 4 - ci))

    def integral_integral_ru_over_r(r):
        # Analytic antiderivative of integral_ru(r)/r, zero at ri.
        return (ro**2 * (r**2 - ri**2) / 4
                - ro**2 * ri**2 * mp.log(r / ri) / 2
                - (r**4 - ri**4) / 16 + ri**4 * mp.log(r / ri) / 4
                - b * ((r**2 * mp.log(ro / r) - ri**2 * logarithm) / 4
                       + (r**2 - ri**2) / 4 - ci * mp.log(r / ri)))

    flux_integral = integral_ru(ro)
    columns = []
    checks = []
    for qi, qo in ((1, 0), (0, 1)):
        def phi(r):
            return (-ri * qi * mp.log(r / ri)
                    + (ri * qi + ro * qo) / flux_integral
                    * integral_integral_ru_over_r(r))

        bulk_offset = mp.quad(lambda r: r * u(r) * phi(r), [ri, ro]) / flux_integral
        columns.append([(phi(ri) - bulk_offset) / dh,
                        (phi(ro) - bulk_offset) / dh])
        checks.append({
            "inner_heat_flux_error": float(abs(-mp.diff(phi, ri) - qi)),
            "outer_heat_flux_error": float(abs(mp.diff(phi, ro) - qo)),
            "bulk_mean_offset_residual": float(abs(mp.quad(
                lambda r: r * u(r) * (phi(r) - bulk_offset), [ri, ro]) / flux_integral)),
        })
    matrix = [[columns[j][i] for j in range(2)] for i in range(2)]
    po = 64 * (1 - ri)**2 / (1 + ri**2 - (1 - ri**2) / mp.log(1 / ri))
    return {
        "radius_ratio": float(ri), "darcy_f_re": float(po),
        "response_matrix": [[float(x) for x in row] for row in matrix],
        "unilateral_heating_nusselt": [float(1 / matrix[i][i]) for i in range(2)],
        "equal_flux_nusselt": [float(1 / sum(row)) for row in matrix],
        "identity_checks": checks,
    }


def mixture_reference():
    phi = 0.45
    rho_cu, cp_cu, k_cu = 8960.0, 385.0, 400.0
    rho_epoxy, cp_epoxy, k_epoxy = 1225.0, 1000.0, 1.0
    rho = phi * rho_cu + (1 - phi) * rho_epoxy
    volumetric = phi * rho_cu * cp_cu + (1 - phi) * rho_epoxy * cp_epoxy
    printed_cp = 723.25
    return {
        "copper_volume_fraction": phi, "density_kg_m3": rho,
        "correct_volumetric_heat_capacity_j_m3_k": volumetric,
        "correct_specific_heat_j_kg_k": volumetric / rho,
        "printed_specific_heat_j_kg_k": printed_cp,
        "printed_implied_volumetric_heat_capacity_j_m3_k": rho * printed_cp,
        "printed_over_correct_relative_difference": rho * printed_cp / volumetric - 1,
        "ideal_series_conductivity_w_m_k": 1 / (phi / k_cu + (1 - phi) / k_epoxy),
        "ideal_parallel_conductivity_w_m_k": phi * k_cu + (1 - phi) * k_epoxy,
        "actual_historical_solver_inputs_known": False,
    }


def generate():
    mp.mp.dps = 45
    annulus = annulus_response(mp.mpf(".1538") / mp.mpf(".1598"))
    ri, ro, rho, mu, k, length, re = .1538, .1598, 1.02, 1.90e-5, .027, .15, 100
    dh = 2 * (ro - ri)
    speed = re * mu / (rho * dh)
    annulus["dimensional_case"] = {
        "inner_radius_m": ri, "outer_radius_m": ro, "length_m": length,
        "density_kg_m3": rho, "dynamic_viscosity_pa_s": mu,
        "conductivity_w_m_k": k, "reynolds": re, "mean_velocity_m_s": speed,
        "mass_flow_kg_s": rho * speed * math.pi * (ro**2 - ri**2),
        "pressure_drop_pa": annulus["darcy_f_re"] / re * length / dh * rho * speed**2 / 2,
        "heat_flux_inner_w_m2": 100, "heat_flux_outer_w_m2": 20,
        "wall_minus_bulk_temperature_k": [dh / k * (row[0] * 100 + row[1] * 20)
                                          for row in annulus["response_matrix"]],
    }
    return {
        "scope": "equation_and_numerical_verification_not_aircraft_physical_validation",
        "dependencies": {"numpy": np.__version__, "scipy": scipy.__version__,
                         "mpmath": mp.__version__, "mpmath_decimal_precision": mp.mp.dps},
        "rectangular_channel": rectangular_reference(),
        "annulus_current_reconstructed_radii": annulus,
        "annulus_nasa_table_radius_ratio_half": annulus_response("0.5"),
        "annulus_thin_gap_limit_sample": annulus_response("0.9999"),
        "material_mixture": mixture_reference(),
    }


def check(report):
    def close(a, b, tol=1e-9):
        if not math.isclose(a, b, rel_tol=tol, abs_tol=tol):
            raise AssertionError(f"{a} differs from reference {b}")
    rect = report["rectangular_channel"]
    close(rect["exact_darcy_f_re"], 83.00797157275215)
    close(rect["laminar_case"]["pressure_drop_pa"], 16.822487100727752)
    grids = rect["finite_volume_grids"]
    errors = [r["mean_velocity_relative_error"] for r in grids]
    for previous, current in zip(errors, errors[1:]):
        if not 3.9 < previous / current < 4.1:
            raise AssertionError("FV convergence is not approximately second order")
    if errors[-1] >= .00052 or max(r["linear_residual_max"] for r in grids) >= 1e-9:
        raise AssertionError("FV solution accuracy or linear residual failed")
    annulus = report["annulus_current_reconstructed_radii"]
    close(annulus["darcy_f_re"], 95.99765683402755)
    offsets = annulus["dimensional_case"]["wall_minus_bulk_temperature_k"]
    close(offsets[0], 7.626272145996139)
    close(offsets[1], -1.1429099398930531)
    source_nu = report["annulus_nasa_table_radius_ratio_half"]["unilateral_heating_nusselt"]
    # NASA Table II.D.2 is rounded, so allow its printed precision.
    for got, printed in zip(source_nu, (6.18102, 5.03655)):
        close(got, printed, 2e-5)
    for nu in report["annulus_thin_gap_limit_sample"]["equal_flux_nusselt"]:
        close(nu, 140 / 17, 5e-5)  # finite eta=.9999, not an exact plate
    for key in ("annulus_current_reconstructed_radii", "annulus_nasa_table_radius_ratio_half",
                "annulus_thin_gap_limit_sample"):
        for item in report[key]["identity_checks"]:
            if max(item.values()) > 1e-30:
                raise AssertionError("Annular heat flux or bulk-temperature identity failed")
    close(report["material_mixture"]["correct_specific_heat_j_kg_k"], 473.0531796206768)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="also assert published research reference checks")
    args = parser.parse_args()
    result = generate()
    if args.check:
        check(result)
        result["reference_checks_passed"] = True
    print(json.dumps(result, indent=2, allow_nan=False))
