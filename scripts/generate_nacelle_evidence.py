"""Reproducible source-load and CAD-design sensitivity evidence (stdlib only)."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aerolab.nacelle_thermal import evaluate_nacelle, nacelle_boundary_catalog

CASES = {
    'source_peak_reference': ({}, {}),
    'larger_lv_intakes': ({'upper_inlet_height_mm': 42}, {}),
    'more_hv_fins': ({'hv_fin_count': 34}, {}),
    'larger_motor_bypass': ({'motor_bypass_gap_mm': 40}, {}),
    'source_mcp': ({}, {'heat_load': 'mcp', 'airspeed_m_s': 45.3}),
    'no_forced_flow': ({}, {'airspeed_m_s': 0}),
    'reduced_heat_screening': ({}, {'heat_scale': .25}),
}


def generate():
    cases = {}
    specifications = dict(CASES)
    source = next(p['boundary'] for p in nacelle_boundary_catalog()['presets'] if p['id'] == 'source_pressure_initial_climb')
    specifications['source_pressure_sensitivity'] = ({}, source)
    for name, (geometry, boundary) in specifications.items():
        run = evaluate_nacelle(geometry, boundary)
        # Retain all flow/heat balances and uncertainty scenarios, not only a
        # favorable summary. Geometry meshes are a separate reproducible export.
        cases[name] = {key: run[key] for key in ('geometry', 'boundary', 'model_id', 'model_sha256', 'input_hash', 'flow', 'thermal', 'diagnostics', 'uncertainty', 'warnings', 'source_flow_diagnostic', 'source_temperature_diagnostic')}
        cases[name]['geometry_fingerprint'] = run['metrics']['fingerprint']
        cases[name]['mass_kg'] = run['metrics']['mass_kg']
        cases[name]['component_mass_kg'] = {k: v['mass_kg'] for k, v in run['metrics']['components'].items()}
        if not run['diagnostics']['converged']:
            raise RuntimeError(f'{name}: pressure solve failed')
        if run['diagnostics']['max_mass_residual_kg_s'] >= 1e-8:
            raise RuntimeError(f'{name}: mass balance failed')
        if run['thermal']['summary']['steady_state_exists'] and not run['diagnostics']['conservation_pass']:
            raise RuntimeError(f'{name}: energy balance failed')
    return {'schema': 'aerolab-modii-reconstruction-evidence-v1',
            'scope': 'Public-source topology and loads, inferred dimensions and uncalibrated reduced-order network. Software conservation evidence is not physical validation.',
            'source': 'https://ntrs.nasa.gov/citations/20230006888',
            'cases': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'examples' / 'nacelle_evidence.json')
    parser.add_argument('--check', action='store_true', help='Check saved evidence with explicit floating-point tolerance')
    args = parser.parse_args()
    result = generate()
    if args.check:
        expected = json.loads(args.output.read_text(encoding='utf-8'))
        def check(actual, saved, path='root'):
            if isinstance(actual, float) and isinstance(saved, (int, float)):
                if not math.isclose(actual, saved, rel_tol=1e-10, abs_tol=1e-9):
                    raise SystemExit(f'Saved evidence differs at {path}: {actual} vs {saved}')
            elif isinstance(actual, dict) and isinstance(saved, dict):
                if actual.keys() != saved.keys():
                    raise SystemExit(f'Saved evidence keys differ at {path}')
                for key in actual:
                    check(actual[key], saved[key], f'{path}.{key}')
            elif isinstance(actual, list) and isinstance(saved, list):
                if len(actual) != len(saved):
                    raise SystemExit(f'Saved evidence length differs at {path}')
                for index, (a, b) in enumerate(zip(actual, saved)):
                    check(a, b, f'{path}[{index}]')
            elif actual != saved:
                raise SystemExit(f'Saved evidence differs at {path}')
        check(result, expected)
        print('All nacelle cases reproduce saved evidence (rel 1e-10 / abs 1e-9 tolerance)')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
        print(f'Wrote {args.output}')
    for name, run in result['cases'].items():
        s = run['thermal']['summary']
        print(f"{name}: flow={run['flow']['total_inlet_kg_s']:.6f}kg/s mass={run['mass_kg']:.3f}kg limit={s['limiting_component']} margin={s['min_margin_c']} screen={s['within_model_limits']}")

if __name__ == '__main__':
    main()
