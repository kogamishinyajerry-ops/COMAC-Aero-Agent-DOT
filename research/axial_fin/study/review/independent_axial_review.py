#!/usr/bin/env python3
"""Small direct reference for axial-fin review; never writes accepted evidence.

The complete three-dimensional block graph is independently assembled here.
Only the accepted transverse graph is imported. No experimental target is read.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
import scipy
from scipy.sparse import diags, eye, kron
from scipy.sparse.linalg import splu

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASELINE = REPO / "research/plate_fin/conjugate_fin.py"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("frozen_fin_for_axial_review", BASELINE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def neumann_graph(n):
    if n == 1:
        return diags([np.zeros(1)], [0], format="csc")
    diag = np.full(n, 2.0)
    diag[[0, -1]] = 1.0
    return diags([-np.ones(n-1), diag, -np.ones(n-1)], [-1, 0, 1], format="csc")


def direct_reference(model, speed, nz, axial_multiplier=1.0, length=base.L):
    """Return a direct solution of slab-integrated conservation equations."""
    dz = length / nz
    mass = model.mass_unit * speed
    M = diags(mass, format="csc")
    lower = diags([-np.ones(nz-1)], [-1], shape=(nz, nz), format="csc") if nz > 1 else eye(1, format="csc") * 0
    az = np.zeros(model.n)
    az[model.nfluid:] = axial_multiplier * model.ks * base.T * model.dy / dz
    A = (kron(eye(nz, format="csc"), model.K * dz + M, format="csc")
         + kron(lower, M, format="csc")
         + kron(neumann_graph(nz), diags(az, format="csc"), format="csc"))
    rhs = np.zeros((nz, model.n))
    rhs[0] = mass
    start = time.perf_counter()
    lu = splu(A)
    flat = lu.solve(rhs.ravel())
    elapsed = time.perf_counter() - start
    theta = flat.reshape(nz, model.n)
    residual = A @ flat - rhs.ravel()
    scale = abs(A) @ abs(flat) + abs(rhs.ravel())
    G = model.factor * float(mass @ (1 - theta[-1]))
    Q = model.factor * dz * float(theta.sum(axis=0) @ model.bound)
    channel_G = [model.factor * float(np.sum(mass[c["ids"]] * (1-theta[-1, c["ids"]]))) for c in model.channels]
    report = {"nx": model.nx, "ny": model.ny, "nz": nz, "speed": speed,
              "profile": model.profile, "full": model.full,
              "axial_multiplier": axial_multiplier, "unknowns": A.shape[0],
              "matrix_nonzeros": A.nnz, "lu_nonzeros": lu.L.nnz + lu.U.nnz,
              "G_W_K": G, "base_heat_W_K": Q,
              "relative_energy_imbalance": abs(Q-G)/max(abs(G), 1e-300),
              "maximum_componentwise_backward_error": float(np.max(abs(residual)/np.maximum(scale, 1e-300))),
              "theta_min": float(theta.min()), "theta_max": float(theta.max()),
              "direct_factor_solve_seconds": elapsed,
              "channel_G": channel_G}
    return theta, report


def self_check():
    cases = []
    symmetry = []
    for profile in ("fd", "plug"):
        half = base.Model(4, 8, profile=profile)
        full = base.Model(4, 8, profile=profile, full=True)
        for multiplier in (0.0, 1.0):
            th, rh = direct_reference(half, 10.0, 12, multiplier)
            tf, rf = direct_reference(full, 10.0, 12, multiplier)
            if multiplier == 0:
                old = half.solve(10.0, nz=12)
                rh["zero_axial_baseline_relative_G"] = rh["G_W_K"]/old["G_W_K"] - 1
            cases.extend([rh, rf])
            pair = [rf["channel_G"][i]+rf["channel_G"][-1-i] for i in range(8)] + [rf["channel_G"][8]]
            halfsolid = th[:, half.nfluid:].reshape(12, 8, 8)
            fullsolid = tf[:, full.nfluid:].reshape(12, 16, 8)
            symmetry.append({"profile": profile, "axial_multiplier": multiplier,
                             "relative_total_G": rh["G_W_K"]/rf["G_W_K"] - 1,
                             "maximum_channel_G_absolute_difference": float(np.max(abs(np.array(pair)-rh["channel_G"]))),
                             "maximum_left_fin_theta_difference": float(np.max(abs(halfsolid-fullsolid[:, :8]))),
                             "maximum_full_fin_reflection_difference": float(np.max(abs(fullsolid-fullsolid[:, ::-1])))})
    return {"direct_checks": cases, "full_mirror_checks": symmetry}


def manufactured_fin():
    rows = []
    ky, kz, thickness, beta = 205.0, 73.0, base.T, 100.0
    for ny, nz in ((12, 24), (24, 48), (48, 96)):
        dy, dz = base.H/ny, base.L/nz
        # Half-cell root distance, insulated tip, insulated two axial end faces.
        Dy = neumann_graph(ny).tolil()
        Dy[0, 0] += 2.0
        Dy = Dy.tocsc()
        A = (kron(eye(nz), Dy * (ky*thickness*dz/dy), format="csc")
             + kron(neumann_graph(nz) * (kz*thickness*dy/dz), eye(ny), format="csc")
             + eye(ny*nz, format="csc")*(beta*dy*dz))
        y = (np.arange(ny)+0.5)*dy
        z = (np.arange(nz)+0.5)*dz
        exact = np.cos(np.pi*z[:, None]/base.L)*np.sin(np.pi*y[None, :]/(2*base.H))
        coefficient = ky*thickness*(np.pi/(2*base.H))**2 + kz*thickness*(np.pi/base.L)**2 + beta
        rhs = coefficient * exact.ravel() * dy*dz
        actual = splu(A).solve(rhs).reshape(nz, ny)
        rows.append({"ny": ny, "nz": nz,
                     "max_absolute_error": float(np.max(abs(actual-exact))),
                     "relative_L2_error": float(np.linalg.norm(actual-exact)/np.linalg.norm(exact))})
    for old, new in zip(rows, rows[1:]):
        new["observed_order_from_previous"] = float(np.log2(old["relative_L2_error"]/new["relative_L2_error"]))
    return {"purpose": "Independent nonconstant axial curvature with manufactured forcing; beta is a synthetic linear verification coefficient, not an experimental heat-transfer fit.",
            "exact_theta": "sin(pi*y/(2*H))*cos(pi*z/L)",
            "root": "Dirichlet zero", "tip_and_axial_ends": "zero derivative",
            "ky": ky, "kz": kz, "beta": beta, "rows": rows}


def main():
    frozen = {}
    for root in (REPO / "research/plate_fin", REPO / "examples/plate_fin_experiment"):
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                frozen[str(path.relative_to(REPO))] = sha(path)
    output = {"status": "independent reference self-check; implementation comparison pending",
              "script_sha256": sha(__file__), "baseline_sha256": sha(BASELINE),
              "numpy_version": np.__version__, "scipy_version": scipy.__version__,
              "source_targets_read_by_script": False,
              "frozen_package_file_hashes": frozen,
              **self_check(), "manufactured_fin": manufactured_fin()}
    path = HERE / "independent_reference_self_checks.json"
    text = json.dumps(output, indent=2, allow_nan=False)+"\n"
    assert len(text.encode()) < 100_000
    path.write_text(text)
    print(json.dumps({"output": str(path), "bytes": path.stat().st_size,
                      "max_conservation_error": max(row["relative_energy_imbalance"] for row in output["direct_checks"]),
                      "max_symmetry_error": max(abs(row["relative_total_G"]) for row in output["full_mirror_checks"]),
                      "manufactured_last_order": output["manufactured_fin"]["rows"][-1]["observed_order_from_previous"]}))


if __name__ == "__main__":
    main()
