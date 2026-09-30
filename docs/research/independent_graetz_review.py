"""Independent global-Galerkin review of the developing parallel-plate reference.

Research-only dependencies: NumPy and SciPy (reviewed with NumPy 2.3.5 and
SciPy 1.17.0). Install in a separate research environment with:
    python -m pip install numpy scipy
Run from any directory:
    python docs/research/independent_graetz_review.py
    python docs/research/independent_graetz_review.py --output output/physics-campaign/independent-graetz-review.json

No dependency is added to the standard-library-only application. This script
does not call the production finite-volume solver. Its cosine basis, Gaussian
integration, generalized eigenproblem, and quadratic boundary lift differ from
the production reference's power-series shooting/root-finding method. The
production reference is imported only to compare the independently computed
wall responses. Agreement is numerical cross-verification, not experimental
validation, a rigorous error bound, or verification at arbitrary inputs.

Exact dimensionless problem and input matrix:
    eta in [-1,1], zeta in {0.02,0.05,0.1,0.2,1}; initially theta=0
    v(theta_zeta)=theta_eta_eta, v=1.5(1-eta**2)
    theta_eta(-1)=-q_left, theta_eta(1)=q_right
    (q_left,q_right) in {(1,1),(0.1,1),(-1,1),(0,1)}
Here q values are flux/reference-flux ratios; theta=k(T-Tin)/(q_ref*b),
zeta=k*s/(rho*cp*abs(U)*b**2), and b is the half-gap. No dimensional fluid
properties, NASA observations, or fitted temperatures enter this check.

Use theta=L+sum(a_j*cos(j*pi*(eta+1)/2)), with
L=(q_left+q_right)*eta**2/4+(q_right-q_left)*eta/2. L enforces both wall
fluxes; the cosine remainder has homogeneous Neumann boundaries. Weak form:
    M a' + K a = F,
    M_ij=int(v*phi_i*phi_j), K_ij=int(phi_i'*phi_j'), F_i=int(phi_i*L'').
The initial remainder is the weighted projection of -L. Solve K V=M V Lambda
with V.T M V=I, then integrate each forced modal ODE analytically. Subtract
the exactly conserved bulk rise (q_left+q_right)*zeta/2 at each wall.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from numpy.polynomial.legendre import leggauss
import scipy
from scipy.linalg import eigh

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.generate_duct_verification import graetz_reference

ZETAS = (.02, .05, .1, .2, 1.)
FLUX_PAIRS = ((1., 1.), (.1, 1.), (-1., 1.), (0., 1.))
REFINEMENTS = ((120, 512), (240, 1024))


def independent_responses(modes, quadrature_points):
    """Solve the original PDE by a global basis; return both wall offsets."""
    eta, weights = leggauss(quadrature_points)
    j = np.arange(modes)
    phi = np.cos(np.outer((eta + 1) * np.pi / 2, j))
    weighted_velocity = weights * 1.5 * (1 - eta * eta)
    mass = phi.T @ (weighted_velocity[:, None] * phi)
    stiffness = np.diag((j * np.pi / 2)**2)
    eigenvalues, eigenvectors = eigh(stiffness, mass)
    positive = eigenvalues > 1e-9
    if not np.all(eigenvalues >= -1e-9) or np.count_nonzero(~positive) != 1:
        raise ArithmeticError("Expected exactly one constant zero eigenmode")
    rows = []
    for left, right in FLUX_PAIRS:
        lift = (left + right) * eta**2 / 4 + (right - left) * eta / 2
        forcing = phi.T @ (weights * (left + right) / 2)
        modal_forcing = eigenvectors.T @ forcing
        modal_initial = -eigenvectors.T @ (phi.T @ (weighted_velocity * lift))
        for zeta in ZETAS:
            factors = np.full(modes, zeta)
            factors[positive] = (-np.expm1(-eigenvalues[positive] * zeta)
                                 / eigenvalues[positive])
            modal = modal_initial * np.exp(-eigenvalues * zeta) + modal_forcing * factors
            coefficients = eigenvectors @ modal
            bulk = (left + right) * zeta / 2
            wall = {
                "left": float((left + right) / 4 - (right - left) / 2
                              + coefficients.sum() - bulk),
                "right": float((left + right) / 4 + (right - left) / 2
                               + (coefficients * (-1.)**j).sum() - bulk),
            }
            rows.append({"zeta": zeta, "flux_ratios": {"left": left, "right": right},
                         "independent_wall_minus_bulk_over_qref_b_k": wall})
    return rows, eigenvalues[:9].tolist()


def review_report():
    refinements = []
    for modes, quadrature_points in REFINEMENTS:
        rows, eigenvalues = independent_responses(modes, quadrature_points)
        for row in rows:
            reference = graetz_reference(row["zeta"], **row["flux_ratios"])
            actual = row["independent_wall_minus_bulk_over_qref_b_k"]
            row["production_series_wall_minus_bulk_over_qref_b_k"] = reference
            row["maximum_absolute_difference"] = max(abs(actual[s] - reference[s]) for s in actual)
        refinements.append({"cosine_modes_including_constant": modes,
                            "gauss_legendre_points": quadrature_points,
                            "first_nine_eigenvalues_including_zero": eigenvalues,
                            "maximum_absolute_difference": max(r["maximum_absolute_difference"] for r in rows),
                            "comparisons": rows})
    coarse, fine = (r["maximum_absolute_difference"] for r in refinements)
    gates = {"fine_difference_below_2e_7": fine < 2e-7,
             "refinement_reduces_maximum_difference_by_more_than_5": coarse > 5 * fine}
    if not all(gates.values()) or not math.isfinite(fine):
        raise ArithmeticError("Independent research cross-check failed: " + str(gates))
    return {
        "schema": "independent-graetz-review-v1",
        "scope": "Numerical cross-verification of a mathematical subproblem only; no experimental validation or all-input error bound",
        "method": "Global cosine Galerkin with quadratic Neumann-boundary lift, Gaussian mass integration, generalized symmetric eigenproblem and exact modal time integration",
        "review_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "compared_reference_sha256": hashlib.sha256((ROOT / "scripts/generate_duct_verification.py").read_bytes()).hexdigest(),
        "dependencies": {"numpy": np.__version__, "scipy": scipy.__version__},
        "arithmetic": "IEEE-754 binary64; results may vary slightly by BLAS/platform",
        "exact_inputs": {"eta_domain": [-1, 1], "zetas": ZETAS,
                         "left_right_flux_ratios": FLUX_PAIRS, "initial_theta": 0.,
                         "velocity_over_mean": "1.5*(1-eta**2)"},
        "gates": gates, "refinements": refinements,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional bounded JSON report; no repository changes by default")
    args = parser.parse_args()
    report = review_report()
    for item in report["refinements"]:
        print(f"{item['cosine_modes_including_constant']} modes / {item['gauss_legendre_points']} quadrature points: "
              f"maximum normalized wall difference {item['maximum_absolute_difference']:.10g}")
    print("Both independent cross-verification gates passed; no physical-validation claim")
    if args.output:
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if len(payload.encode()) >= 100000:
            raise ValueError("Review report must remain below 100 kB")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output} ({len(payload.encode())} bytes)")


if __name__ == "__main__":
    main()
