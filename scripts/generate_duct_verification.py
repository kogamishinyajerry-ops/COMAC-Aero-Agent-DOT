"""Generate/check FV evidence against independently evaluated analytical solutions.

The high-precision power-series eigenproblem below does NOT call the FV solver
or reuse its spatial discretization. It verifies developing equal/unequal-flux
Graetz solutions, not measured hardware or a turbulent rotating-motor model.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aerolab.duct_finite_volume import DEFAULT_CASE, NU_FULLY_DEVELOPED, solve_duct

REFERENCE_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
REFERENCE_PRECISION = 90
REFERENCE_TERMS = 180


def _coefficients(eigenvalue, odd, terms=REFERENCE_TERMS):
    """Power series of psi'' + 1.5*lambda*(1-eta^2)*psi = 0.

    Even psi(0)=1, psi'(0)=0; odd psi(0)=0, psi'(0)=1.
    Coefficient index j denotes eta**(2*j+odd).
    """
    coefficients, previous = [Decimal(1)], Decimal(0)
    for j in range(terms - 1):
        power = 2 * j + int(odd)
        value = (-Decimal("1.5") * eigenvalue * (coefficients[-1] - previous)
                 / Decimal((power + 2) * (power + 1)))
        previous = coefficients[-1]
        coefficients.append(value)
    return coefficients


def _wall_derivative(eigenvalue, odd):
    return sum(Decimal(2 * j + int(odd)) * coefficient
               for j, coefficient in enumerate(_coefficients(eigenvalue, odd)))


@lru_cache(maxsize=4)
def graetz_modes(odd=False, count=12):
    """Independent bounded high-precision eigenvalues and wall-mode amplitudes.

    Neumann eigencondition psi'(1)=0; the constant eigenmode is excluded.
    Exact polynomial-product integration gives int_0^1 u*psi^2 d eta.
    Mode amplitude = psi(1)^2 / (lambda * weighted_norm).
    """
    if type(odd) is not bool or type(count) is not int or not 1 <= count <= 12:
        raise ValueError("odd must be bool and count an integer in [1, 12]")
    with localcontext() as context:
        context.prec = REFERENCE_PRECISION
        modes = []
        left = Decimal("0.01")
        f_left = _wall_derivative(left, odd)
        for index in range(1, 2001):
            right = Decimal(index)
            f_right = _wall_derivative(right, odd)
            if f_left * f_right < 0:
                low, high, f_low = left, right, f_left
                for _ in range(180):
                    middle = (low + high) / 2
                    f_middle = _wall_derivative(middle, odd)
                    if f_middle * f_low > 0:
                        low, f_low = middle, f_middle
                    else:
                        high = middle
                eigenvalue = (low + high) / 2
                coefficients = _coefficients(eigenvalue, odd)
                wall = sum(coefficients)
                square = [Decimal(0)] * (2 * len(coefficients) - 1)
                for i, a in enumerate(coefficients):
                    for j, b in enumerate(coefficients):
                        square[i + j] += a * b
                norm = sum(Decimal("1.5") * value * (
                    1 / Decimal(2 * j + 2 * int(odd) + 1)
                    - 1 / Decimal(2 * j + 2 * int(odd) + 3))
                    for j, value in enumerate(square))
                amplitude = wall * wall / (eigenvalue * norm)
                modes.append((float(eigenvalue), float(amplitude)))
                if len(modes) == count:
                    return tuple(modes)
            left, f_left = right, f_right
    raise ArithmeticError("Graetz eigenvalue search did not converge within its bound")


def graetz_reference(zeta, left=1.0, right=1.0, count=12):
    """Continuum wall-minus-bulk temperatures in units q_ref*b/k.

    For zeta>=.02, compare 8 and 12 modes in the generated evidence; the
    truncation difference is disclosed, not assumed to prove a rigorous bound.
    This reference is intentionally separate from the production FV module.
    """
    if (not isinstance(zeta, (int, float)) or isinstance(zeta, bool)
            or not math.isfinite(zeta) or zeta < .02):
        raise ValueError("reference requires finite zeta >= .02")
    for value in (left, right):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("reference flux ratios must be finite")
    even = 17 / 35 - math.fsum(a * math.exp(-lam * zeta) for lam, a in graetz_modes(False, count))
    odd = 1 - math.fsum(a * math.exp(-lam * zeta) for lam, a in graetz_modes(True, count))
    return {"left": .5 * (left + right) * even - .5 * (right - left) * odd,
            "right": .5 * (left + right) * even + .5 * (right - left) * odd}


def _length(zeta):
    p = DEFAULT_CASE
    return zeta * p["density_kg_m3"] * p["specific_heat_j_kg_k"] * abs(p["mean_velocity_m_s"]) * (p["gap_m"] / 2)**2 / p["conductivity_w_m_k"]


def _order(errors):
    return [math.log(errors[i] / errors[i + 1], 2) for i in range(len(errors) - 1)]


def generate():
    developed = []
    for n in (16, 32, 64, 128):
        result = solve_duct({"transverse_cells": n, "axial_cells": 4, "inlet_profile": "fully_developed"})
        friction = result["hydraulics"]["darcy_f_re"]
        nu = result["thermal"]["outlet_nusselt"]["right"]
        developed.append({"transverse_cells": n, "darcy_f_re": friction, "nusselt_dh": nu,
                          "friction_absolute_error": abs(friction - 96),
                          "nusselt_absolute_error": abs(nu - NU_FULLY_DEVELOPED),
                          "energy_residual_w": result["diagnostics"]["energy_residual_w"]})
    asymmetric = []
    for left, right in ((1, 1), (0, 1), (.1, 1), (1, .1), (-1, 1), (-1, -1)):
        result = solve_duct({"transverse_cells": 128, "axial_cells": 4,
                             "left_heat_flux_w_m2": 200 * left, "right_heat_flux_w_m2": 200 * right,
                             "inlet_profile": "fully_developed"})
        actual = result["thermal"]["axial_samples"][-1]["wall_minus_bulk_over_qref_b_k"]
        exact = {"left": (26 * left - 9 * right) / 35, "right": (26 * right - 9 * left) / 35}
        asymmetric.append({"flux_ratios": {"left": left, "right": right},
                           "fv_wall_offsets": actual, "analytical_wall_offsets": exact,
                           "max_absolute_error": max(abs(actual[side] - exact[side]) for side in exact),
                           "energy_residual_w": result["diagnostics"]["energy_residual_w"]})
    developing = []
    for left, right in ((1.0, 1.0), (.1, 1.0)):
        for zeta in (.02, .05, .1, .2, 1.0):
            result = solve_duct({"transverse_cells": 128, "axial_cells": 800, "length_m": _length(zeta),
                                 "left_heat_flux_w_m2": 200 * left, "right_heat_flux_w_m2": 200 * right})
            actual = result["thermal"]["axial_samples"][-1]["wall_minus_bulk_over_qref_b_k"]
            reference = graetz_reference(zeta, left, right)
            short = graetz_reference(zeta, left, right, count=8)
            developing.append({"zeta": zeta, "flux_ratios": {"left": left, "right": right},
                               "fv_wall_offsets": actual, "spectral_wall_offsets": reference,
                               "max_absolute_error": max(abs(actual[side] - reference[side]) for side in reference),
                               "max_8_vs_12_mode_difference": max(abs(short[side] - reference[side]) for side in reference),
                               "energy_residual_w": result["diagnostics"]["energy_residual_w"]})
    coupled_grid = []
    exact = graetz_reference(.05)["right"]
    for n, nx in ((16, 100), (32, 200), (64, 400), (128, 800)):
        result = solve_duct({"transverse_cells": n, "axial_cells": nx, "length_m": _length(.05)})
        actual = result["thermal"]["axial_samples"][-1]["wall_minus_bulk_over_qref_b_k"]["right"]
        coupled_grid.append({"transverse_cells": n, "axial_cells": nx, "wall_offset": actual,
                             "absolute_error": abs(actual - exact)})
    axial_grid = []
    for nx in (100, 200, 400, 800):
        result = solve_duct({"transverse_cells": 256, "axial_cells": nx, "length_m": _length(.05)})
        actual = result["thermal"]["axial_samples"][-1]["wall_minus_bulk_over_qref_b_k"]["right"]
        axial_grid.append({"transverse_cells": 256, "axial_cells": nx, "wall_offset": actual,
                           "absolute_error": abs(actual - exact)})
    differences = [abs(axial_grid[i]["wall_offset"] - axial_grid[i + 1]["wall_offset"])
                   for i in range(len(axial_grid) - 1)]
    visual_cases = {"equal_flux_developing": solve_duct({"axial_samples": 9}),
                    "unequal_flux_developing": solve_duct({"left_heat_flux_w_m2": 20, "axial_samples": 9})}
    gates = {
        "friction_relative_error_below_0_02_percent": developed[-1]["friction_absolute_error"] / 96 < .0002,
        "equal_flux_nusselt_relative_error_below_0_01_percent": developed[-1]["nusselt_absolute_error"] / NU_FULLY_DEVELOPED < .0001,
        "second_order_transverse": all(1.9 < order < 2.1 for order in _order([r["nusselt_absolute_error"] for r in developed])),
        "first_order_axial": all(.95 < order < 1.05 for order in _order(differences)),
        "asymmetric_offsets_absolute_error_below_0_0001": max(r["max_absolute_error"] for r in asymmetric) < .0001,
        "developing_offsets_absolute_error_below_0_0005": max(r["max_absolute_error"] for r in developing) < .0005,
        "spectral_8_vs_12_difference_below_1e_8": max(r["max_8_vs_12_mode_difference"] for r in developing) < 1e-8,
        "coupled_refinement_error_decreases": all(coupled_grid[i + 1]["absolute_error"] < coupled_grid[i]["absolute_error"] for i in range(3)),
        "visual_case_energy_residual_below_1e_9_w": all(abs(r["diagnostics"]["energy_residual_w"]) < 1e-9 for r in visual_cases.values()),
    }
    if not all(gates.values()):
        raise ArithmeticError("verification gates failed: " + str([name for name, passed in gates.items() if not passed]))
    return {"schema": "duct-verification-v1", "purpose": "Analytical/numerical verification only; no aircraft calibration or experiment.",
            "sources_checked_date": "2026-09-30",
            "sources": [
                {"title": "Cess and Shaffer (1959), prescribed-wall-flux parallel-plate Graetz problem",
                 "url": "https://link.springer.com/article/10.1007/BF00411758",
                 "checked": "Publisher abstract and bibliographic metadata; no paywalled tables reproduced."},
                {"title": "NASA TN D-1972, heat transfer in concentric annuli (1963)",
                 "url": "https://ntrs.nasa.gov/citations/19630010444",
                 "checked": "Plane-gap limit and unequal-wall heat-flux superposition; not a rotating-motor validation."},
                {"title": "Inman, laminar slip flow with uniform wall heat transfer, NASA (1966 archive)",
                 "url": "https://ntrs.nasa.gov/api/citations/19660009101/downloads/19660009101.pdf",
                 "checked": "Primary report describes eigenfunction solution, equal/one-wall heating and continuum limit."}],
            "reference": {"source_sha256": REFERENCE_SOURCE_SHA256,
                          "method": "Independent Decimal power-series Sturm-Liouville eigenproblem and exact polynomial-product quadrature",
                          "precision_decimal_digits": REFERENCE_PRECISION, "power_series_terms": REFERENCE_TERMS,
                          "root_bisections": 180, "modes_used": 12,
                          "even_modes_lambda_amplitude": graetz_modes(False),
                          "odd_modes_lambda_amplitude": graetz_modes(True),
                          "analytical_equal_flux_nusselt": NU_FULLY_DEVELOPED,
                          "analytical_one_heated_wall_nusselt": 70 / 13,
                          "analytical_darcy_f_re": 96.0},
            "gates": gates, "fully_developed_grid_convergence": developed,
            "transverse_nusselt_observed_orders": _order([r["nusselt_absolute_error"] for r in developed]),
            "asymmetric_wall_verification": asymmetric, "developing_spectral_comparison": developing,
            "coupled_grid_convergence": coupled_grid, "axial_grid_convergence": axial_grid,
            "axial_observed_orders_from_successive_differences": _order(differences),
            "visual_cases": visual_cases}


def check(actual, saved, path="root"):
    if isinstance(actual, float) and isinstance(saved, (int, float)):
        if not math.isclose(actual, saved, rel_tol=1e-10, abs_tol=1e-9):
            raise ValueError(f"{path}: {actual} != {saved}")
    elif isinstance(actual, dict) and isinstance(saved, dict) and actual.keys() == saved.keys():
        for key in actual:
            check(actual[key], saved[key], path + "." + key)
    elif isinstance(actual, (list, tuple)) and isinstance(saved, (list, tuple)) and len(actual) == len(saved):
        for index, (a, b) in enumerate(zip(actual, saved)):
            check(a, b, f"{path}[{index}]")
    elif actual != saved:
        raise ValueError(f"{path}: saved evidence differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "examples" / "duct_verification.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = generate()
    if args.check:
        check(report, json.loads(args.output.read_text(encoding="utf-8")))
        print("Duct evidence reproduces source identities, inputs, spatial solutions and analytical checks")
    else:
        encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if len(encoded.encode()) >= 100000:
            raise ValueError("verification artifact must remain below 100 kB")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(f"Wrote {args.output} ({len(encoded.encode())} bytes)")
    last = report["fully_developed_grid_convergence"][-1]
    print(f"All {len(report['gates'])} gates pass; fRe={last['darcy_f_re']:.8f}, Nu={last['nusselt_dh']:.8f}")
    print("No physical aircraft validation or ROM calibration is claimed")


if __name__ == "__main__":
    main()
