"""Reproduce source-based geometry → thermal → fixed-hardware mission evidence."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aerolab.geometry import GEOMETRY_PRESETS, parse_geometry
from aerolab.cad_thermal import evaluate
from aerolab.model import simulate

root=Path(__file__).resolve().parents[1]
results=[]
for name,g in GEOMETRY_PRESETS.items():
    geometry=asdict(parse_geometry(g))
    benchmark=evaluate(geometry)
    benchmark.pop('preview_svg')
    runs={}
    for scenario in ('nominal','cooling_fault','bus_cooling'):
        run=simulate(scenario,cad_geometry=geometry)
        runs[scenario]={k:run[k] for k in ('meta','design','summary','validation')}
    results.append({'preset':name,'benchmark':benchmark,'missions':runs})
output=root/'examples/cad_thermal_evidence.json'
output.write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
print(f'Wrote {output}: 3 geometries, 3 thermal benchmarks, 9 fixed-hardware missions')
for row in results:
    g,t=row['benchmark']['metrics'],row['benchmark']['thermal']
    print(f"{row['preset']}: {g['mass_kg']:.6f} kg, {t['base_temperature_c']:.3f} C base, {t['pressure_drop_pa']:.3f} Pa, {t['blower_electrical_w']:.3f} W blower")
