"""Reproduce bounded NASA station-identifiability evidence without fitting the ROM."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aerolab.nacelle_source_audit import source_audit
from scripts.generate_nacelle_credibility import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "examples" / "nacelle_source_audit.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = source_audit()
    if args.check:
        check(report, json.loads(args.output.read_text(encoding="utf-8")))
        print("Source-station audit reproduces saved inference, cross-condition checks and provenance")
    else:
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if len(payload.encode()) > 100_000:
            raise RuntimeError("Audit evidence exceeds bounded-file publication limit")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output}")
    for key in ("main_inlet", "motor_internal", "motor_slots", "motor_bypass_inlet"):
        item = report["flow_area_constraints"][key]
        print(f"{key}: inferred={item['inferred_flux_equivalent_area_m2']:.7f}m2 "
              f"current={item['current_rom_area_m2']:.7f}m2 "
              f"three-case span={item['three_case_span_percent_of_inferred']:.3f}%")
    for key in ("main_to_gap", "main_to_slots", "slot_core"):
        cases = report["conditional_resistance_checks"][key]["cases"]
        print(f"{key}: fixed initial-climb conductance, cruise error="
              f"{cases['cruise_climb']['relative_error_percent']:+.2f}%, "
              f"dash error={cases['dash']['relative_error_percent']:+.2f}%")


if __name__ == "__main__":
    main()
