"""Reproduce the bounded historical motor component benchmark; never fit the ROM."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aerolab.historical_motor import historical_motor_benchmark
from scripts.generate_nacelle_credibility import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "examples" / "historical_motor.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = historical_motor_benchmark()
    if args.check:
        check(report, json.loads(args.output.read_text(encoding="utf-8")))
        print("Historical component evidence reproduces saved inputs, equations and identities")
    else:
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if len(payload.encode()) >= 100_000:
            raise RuntimeError("Historical benchmark exceeds bounded-file limit")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output}")
    print("2019 component only; no calibration, actual channel count or aircraft-temperature prediction")
    for row in report["velocity_sweep"]:
        t = row["transport"]
        print(f"U={t['velocity_m_s']:.0f}m/s Re={t['reynolds']:.1f} "
              f"h={t['h_w_m2_k']:.2f}W/m2K friction_dp={t['friction_pressure_drop_pa']:.2f}Pa "
              f"{t['correlation_status']}")
    materials = report["materials"]
    print(f"Mixture cp={materials['mass_consistent_specific_heat_j_kg_k']:.6f}J/kgK; "
          f"printed implied rho*cp is {materials['printed_capacity_excess_percent_of_constituent_value']:.4f}% higher")


if __name__ == "__main__":
    main()
