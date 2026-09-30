#!/usr/bin/env python3
"""Coarse algebraic review only, not sweep acceptance or physical validation.

No experiment arrays or requirement outcomes are read. Eliminate both fins
and sealed-branch fluid as massless states and independently propagate the
remaining generalized eigenmodes along the duct.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.linalg import eigh, solve

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pressure_model_review", ROOT / "pressure_fin.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    model = t.PressureFin(nx=4, ny=12)
    nominal = model.hydraulic(25.0)
    closed = model.hydraulic(25.0, (1,))
    doubled = model.hydraulic(50.0)
    closure = sum(x["volume_flow_m3_s"] for x in nominal) - sum(x["volume_flow_m3_s"] for x in closed)
    hydraulic_checks = {
        "unblocked_absolute_flows_unchanged": all(a["volume_flow_m3_s"] == b["volume_flow_m3_s"]
            for i, (a, b) in enumerate(zip(nominal, closed)) if i != 1),
        "closed_branch_flow_zero": closed[1]["volume_flow_m3_s"] == 0.0,
        "total_flow_reduction_equals_closed_flow_relative_error": closure / nominal[1]["volume_flow_m3_s"] - 1,
        "pressure_doubling_maximum_relative_error": max(abs(a["volume_flow_m3_s"] / b["volume_flow_m3_s"] - 2)
            for a, b in zip(doubled, nominal)),
    }
    rows = []
    for blocked in ((), (1,)):
        hydraulic = model.hydraulic(25.0, blocked)
        mass = np.zeros(model.n)
        for channel, flow in zip(model.channels, hydraulic):
            mass[channel["ids"]] = (model.heatcap * flow["mean_speed_m_s"] * channel["shape"]
                                    * channel["dx"] * model.dy)
        active, algebraic = np.flatnonzero(mass > 0), np.flatnonzero(mass == 0)
        K = model.K.toarray()
        Kaa, Kaz, Kzz = K[np.ix_(active, active)], K[np.ix_(active, algebraic)], K[np.ix_(algebraic, algebraic)]
        schur = Kaa - Kaz @ solve(Kzz, Kaz.T, assume_a="pos")
        eigenvalues, eigenvectors = eigh(schur, np.diag(mass[active]))
        weights = (mass[active] @ eigenvectors)**2
        nz = 200
        independent_G = mass.sum() - weights @ np.exp(-nz * np.log1p(eigenvalues * t.L / nz))
        result = model.solve(25.0, blocked, nz=nz, details=True)
        profiles = [np.asarray(x["normalized_T"]) for x in result["outlet_fin_profiles"]]
        rows.append({"blocked_channels": list(blocked), "coarse_grid": {"nx": 4, "ny": 12, "nz": nz},
            "algebraic_unknown_count": len(algebraic), "active_unknown_count": len(active),
            "minimum_eigenvalue_per_m": float(eigenvalues[0]),
            "implementation_G_W_K": result["G_W_K"], "independent_spectral_BE_G_W_K": float(independent_G),
            "relative_propagation_difference": result["G_W_K"] / independent_G - 1,
            "global_energy_relative_imbalance": result["energy_relative_balance_max"],
            "closed_branch_enthalpy_transport_W_K": result["channels"][1]["heat_transport_W_K"] if blocked else None,
            "maximum_mirrored_fin_temperature_asymmetry": float(max(np.max(abs(a - b)) for a, b in zip(profiles, profiles[::-1]))),
            "fin_only_mass_kg": result["fin_only_mass_kg"]})
    checks = {
        "hydraulic_invariants": hydraulic_checks["unblocked_absolute_flows_unchanged"] and hydraulic_checks["closed_branch_flow_zero"]
            and abs(hydraulic_checks["total_flow_reduction_equals_closed_flow_relative_error"]) < 1e-12
            and hydraulic_checks["pressure_doubling_maximum_relative_error"] < 1e-12,
        "independent_coupled_propagation": all(abs(r["relative_propagation_difference"]) < 1e-11 for r in rows),
        "zero_closed_branch_enthalpy": rows[1]["closed_branch_enthalpy_transport_W_K"] == 0.0,
        "genuine_asymmetric_fin_coupling": rows[0]["maximum_mirrored_fin_temperature_asymmetry"] < 1e-12
            and rows[1]["maximum_mirrored_fin_temperature_asymmetry"] > 1e-5,
    }
    evidence = {"scope": "Early coarse operator review only; not acceptance of the geometry sweep or synthetic requirements",
        "model_sha256": sha(ROOT / "pressure_fin.py"), "inherited_solver_sha256": sha(t.SOURCE),
        "presweep_plan_sha256": sha(ROOT / "presweep_plan.json"), "review_script_sha256": sha(Path(__file__)),
        "experimental_arrays_read": False, "hydraulic_checks": hydraulic_checks, "rows": rows,
        "checks": checks, "all_early_checks_passed": bool(all(checks.values()))}
    path = Path(__file__).with_suffix(".json")
    path.write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
    print(path)
    if not evidence["all_early_checks_passed"]:
        raise SystemExit("Early operator review failed")


if __name__ == "__main__":
    main()
