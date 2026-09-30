#!/usr/bin/env python3
"""Independent read-only model checks; writes evidence only beside this script.

No experimental targets are loaded. Dense generalized eigenmodes check the
coupled semi-discrete problem with exact axial propagation, independently of
the implementation's marching loop. Analytic low-conductivity plug limits
also check the 15 heated-floor versus two adiabatic-side-channel topology.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.linalg import eigh, solve
from scipy.optimize import brentq
from scipy.sparse import diags
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fin_model_review", ROOT / "conjugate_fin.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def spectral_reference():
    m = c.Model(4, 12)
    K = m.K.toarray()
    nf = m.nfluid
    Kff, Kfs, Kss = K[:nf, :nf], K[:nf, nf:], K[nf:, nf:]
    S = Kff - Kfs @ solve(Kss, Kfs.T, assume_a="pos")
    rows = []
    for speed in (4.0, 10.0, 20.0):
        mass = m.mass_unit[:nf] * speed
        eigenvalues, eigenvectors = eigh(S, np.diag(mass))
        weights = (mass @ eigenvectors) ** 2
        capacity = mass.sum()
        exact = m.factor * (capacity - weights @ np.exp(-eigenvalues * c.L))
        for nz in (100, 200, 400, 800):
            calculated = m.solve(speed, nz=nz)
            be = m.factor * (capacity - weights @ np.exp(-nz * np.log1p(eigenvalues * c.L / nz)))
            rows.append({"speed": speed, "nz": nz, "implementation_G": calculated["G_W_K"],
                         "spectral_BE_G": float(be), "exact_axial_semidiscrete_G": float(exact),
                         "relative_implementation_vs_spectral_BE": float(calculated["G_W_K"] / be - 1),
                         "relative_temporal_error": float(calculated["G_W_K"] / exact - 1),
                         "minimum_eigenvalue_per_m": float(eigenvalues[0]),
                         "spectral_capacity_relative_error": float(weights.sum() / capacity - 1)})
    return rows


def topology_and_symmetry():
    half, full = c.Model(6, 18), c.Model(6, 18, full=True)
    cap = c.RHO * c.CP * c.WI * c.H
    result = {"half_channels": len(half.channels), "half_fins": len(half.fins),
              "full_channels": len(full.channels), "full_fins": len(full.fins),
              "half_channel_capacity_ratios": (np.array(half.channel_mass_unit) / cap).tolist(),
              "whole_array_capacity_per_speed": float(half.factor * half.mass_unit.sum()),
              "expected_capacity_per_speed": float(17 * cap),
              "full_fluid_area": float(half.factor * sum(ch["width"] * c.H for ch in half.channels)),
              "expected_full_fluid_area": float((15 * c.WI + 2 * c.WS) * c.H),
              "heated_floor_ground_conductance": float(half.factor * half.base_floor_g.sum()),
              "expected_heated_floor_ground_conductance": float(15 * 2 * c.KA * c.WI / half.dy),
              "fin_root_ground_conductance": float(half.factor * half.fin_root_g.sum()),
              "expected_fin_root_ground_conductance": float(16 * 2 * 205 * c.T / half.dy),
              "symmetry_comparisons": []}
    for speed in (4.0, 10.0, 20.0):
        rh, rf = half.solve(speed, nz=400), full.solve(speed, nz=400)
        hc, fc = rh["mirrored_channel_contributions_W_K"], rf["mirrored_channel_contributions_W_K"]
        paired = [fc[i] + fc[-1-i] for i in range(8)] + [fc[8]]
        result["symmetry_comparisons"].append({"speed": speed,
            "relative_total_G": rh["G_W_K"] / rf["G_W_K"] - 1,
            "maximum_absolute_channel_G": float(max(abs(np.array(hc) - paired)))})
    return result


def local_residual_and_interfaces():
    results = []
    for ks in (167.0, 205.0, 237.0):
        m = c.Model(12, 36, ks=ks)
        mass = 10 * m.mass_unit
        dz = c.L / 400
        A = m.K + diags(mass / dz)
        lu = splu(A.tocsc())
        theta = np.ones(m.n)
        max_backward = max_increase = max_fin_balance = 0.0
        for step in range(400):
            old = theta
            rhs = mass / dz * old
            theta = lu.solve(rhs)
            residual = A @ theta - rhs
            scale = abs(A) @ abs(theta) + abs(rhs)
            max_backward = max(max_backward, float(np.max(abs(residual) / np.maximum(scale, 1e-300))))
            max_increase = max(max_increase, float(np.max(theta - old)))
            for fin in m.fins:
                # A fin's summed algebraic residual is its net root/interface heat.
                max_fin_balance = max(max_fin_balance, float(abs(residual[fin].sum())))
        diff = m.K - m.K.T
        results.append({"ks": ks, "maximum_componentwise_backward_error": max_backward,
                        "maximum_cellwise_deficit_increase": max_increase,
                        "maximum_absolute_fin_heat_imbalance_W_per_m_K": max_fin_balance,
                        "matrix_symmetry_error": float(max(abs(diff.data), default=0)),
                        "matrix_rowsum_vs_ground_maxabs": float(max(abs(np.asarray(m.K.sum(axis=1)).ravel() - m.bound)))})
    return results


def low_conductivity_limit():
    rows = []
    alpha = c.KA / (c.RHO * c.CP)
    odd = np.arange(1, 4000, 2, dtype=float)
    for speed in (4.0, 10.0, 20.0):
        theta = np.sum(8 / (np.pi**2 * odd**2) * np.exp(-alpha * c.L / speed * (odd * np.pi / (2 * c.H))**2))
        exact = 15 * c.RHO * c.CP * speed * c.WI * c.H * (1 - theta)
        for ny in (72, 144, 288):
            m = c.Model(4, ny, ks=1e-8, profile="plug")
            r = m.solve(speed, nz=1600)
            rows.append({"speed": speed, "ny": ny, "ks": 1e-8,
                         "calculated_G": r["G_W_K"], "exact_zero_ks_continuum_G": float(exact),
                         "relative_error": float(r["G_W_K"] / exact - 1),
                         "combined_side_channel_G": r["mirrored_channel_contributions_W_K"][0]})
    return rows


def observed_spatial_order():
    path = ROOT / "verification.json"
    if not path.exists():
        return {"status": "verification evidence not yet available"}
    evidence = json.loads(path.read_text())
    base_evidence = evidence
    predecessor = None
    if "runs" not in evidence:
        predecessor = ROOT / evidence["reused_mathematical_evidence_file"]
        assert sha(predecessor) == evidence["reused_mathematical_evidence_sha256"]
        base_evidence = json.loads(predecessor.read_text())
    rows = []
    for profile in ("fd", "plug"):
        for speed in (4.0, 10.0, 20.0):
            values = {r["mesh"]["gap_cells"]: r["G_W_K"] for r in base_evidence["runs"]
                      if r["kind"] == "cross_section" and r["profile"] == profile
                      and r["V_interior_m_s"] == speed}
            ratio = (values[24] - values[36]) / (values[36] - values[48])
            order = brentq(lambda p: ((36 / 24)**p - 1) / (1 - (36 / 48)**p) - ratio, 0.1, 5)
            fine_error = (values[36] - values[48]) / ((48 / 36)**order - 1)
            rows.append({"profile": profile, "speed": speed,
                         "observed_order_24_36_48": order,
                         "fine48_Richardson_relative_error_indicator": fine_error / values[48]})
    return {"verification_sha256": sha(path),
            "reused_verification_sha256": sha(predecessor) if predecessor else None,
            "rows": rows,
            "caveat": "Richardson indicators assume asymptotic convergence; they are not proven bounds or measurement uncertainties."}


if __name__ == "__main__":
    output = {"solver_sha256": sha(ROOT / "conjugate_fin.py"),
              "plan_sha256": sha(ROOT / "precomparison_plan.json"),
              "review_script_sha256": sha(Path(__file__)), "experimental_targets_read": False,
              "spectral_reference": spectral_reference(),
              "topology_and_symmetry": topology_and_symmetry(),
              "local_residual_and_interfaces": local_residual_and_interfaces(),
              "low_conductivity_limit": low_conductivity_limit(),
              "observed_spatial_order": observed_spatial_order()}
    path = Path(__file__).with_suffix(".json")
    path.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(path)
