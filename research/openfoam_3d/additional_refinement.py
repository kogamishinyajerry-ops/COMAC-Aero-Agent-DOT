#!/usr/bin/env python3
"""One separately preregistered additional grid; original failure stays intact."""
import argparse,json
from pathlib import Path
import study as s
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
plan=json.loads((s.HERE/'additional_refinement_plan.json').read_text());case=a.output/'grid_3'
if case.exists():raise ValueError('Fresh additional-refinement directory required')
case.mkdir(parents=True)
s.setup(case,plan['grid']);s.solve_flow(case);s.solve_heat(case);s.solve_heat(case,exact=True)
r=s.analyse(case);print(json.dumps(r,indent=2))
