from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from .model import SCENARIOS, DESIGNS, POLICIES, simulate, compare, sweep
from .server import serve


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Synthetic aircraft power/thermal demonstrator")
    parser.add_argument("command", choices=("serve", "run", "compare", "sweep", "export-demo", "benchmark"))
    parser.add_argument("--scenario", choices=list(SCENARIOS), default="cooling_fault")
    parser.add_argument("--policy", choices=list(POLICIES), default="baseline")
    parser.add_argument("--design", choices=list(DESIGNS), default="reference")
    parser.add_argument("--ambient", type=float)
    parser.add_argument("--dt", type=float, default=2)
    parser.add_argument("--demand-scale", type=float, default=1)
    parser.add_argument("--event-offset", type=float, default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cad-preset", choices=("reference", "light", "dense"), help="Opt in to CAD-linked separated controller/motor mission")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.command == "serve":
        serve(port=args.port)
        return
    kwargs = dict(scenario_id=args.scenario, design_id=args.design, ambient_c=args.ambient,
                  dt_s=args.dt, demand_scale=args.demand_scale, event_time_offset_s=args.event_offset)
    if args.cad_preset:
        from .geometry import GEOMETRY_PRESETS, parse_geometry
        from dataclasses import asdict
        kwargs["cad_geometry"] = asdict(parse_geometry(GEOMETRY_PRESETS[args.cad_preset]))
    if args.command == "benchmark":
        result = []
        for scenario in SCENARIOS:
            for policy in POLICIES:
                run = simulate(scenario, policy)
                result.append({"scenario": scenario, "policy": policy, "run_id": run["meta"]["run_id"], **run["summary"]})
    elif args.command == "sweep":
        result = sweep(**kwargs)
    elif args.command in ("compare", "export-demo"):
        result = compare(**kwargs)
    else:
        result = simulate(policy=args.policy, **kwargs)
    output = args.output or (Path("examples/reference_compare.json") if args.command == "export-demo" else None)
    if output:
        write_json(output, result)
        print(f"Wrote {output}")
    elif args.command == "run":
        print(json.dumps(result["summary"], indent=2))
    elif args.command == "compare":
        print(json.dumps({key: run["summary"] for key, run in result.items()}, indent=2))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
