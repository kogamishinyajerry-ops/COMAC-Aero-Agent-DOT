"""Reproduce unfitted three-condition source comparisons and closure budgets.

This is model discrepancy evidence, not experimental validation or a fit report.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aerolab.nacelle_thermal import SOURCE_CASES, SOURCE_URL, evaluate_nacelle, nacelle_boundary_catalog


def generate():
    presets = {p['id']: p['boundary'] for p in nacelle_boundary_catalog()['presets']}
    cases = {}
    for name, source in SOURCE_CASES.items():
        for mode in ('inferred_pressure', 'source_pressure'):
            boundary = ({k: source[k] for k in ('airspeed_m_s', 'ambient_c', 'density_kg_m3', 'heat_load')}
                        if mode == 'inferred_pressure' else presets['source_pressure_' + name])
            result = evaluate_nacelle(boundary=boundary)
            if not result['diagnostics']['conservation_pass']:
                raise RuntimeError(f'{name}/{mode}: numerical conservation failed')
            branches = result['flow']['branches']
            cases[name + '_' + mode] = {
                'boundary': result['boundary'], 'input_hash': result['input_hash'],
                'geometry_fingerprint': result['metrics']['fingerprint'],
                'model_sha256': result['model_sha256'], 'model_id': result['model_id'],
                'summary': result['thermal']['summary'],
                'numerical_verification': result['diagnostics'],
                'source_flow_comparison': result['source_flow_diagnostic'],
                'source_temperature_comparison': result['source_temperature_diagnostic'],
                'motor_patch_budget': result['thermal']['motor_patch_budget'],
                'transport': {key: {field: branches[key][field] for field in (
                    'mass_flow_kg_s', 'reynolds', 'h_w_m2_k', 'ua_w_k', 'air_capacity_w_k',
                    'length_to_hydraulic_diameter', 'regime', 'heat_boundary',
                    'inlet_c', 'outlet_c', 'actual_geometry_correlation_validated')}
                    for key in ('motor_internal', 'motor_slots', 'motor_bypass', 'cmc_hv_left', 'lv_fresh_left')},
                'assumption_scenarios': {'min_margin_c': result['uncertainty']['min_margin_c'],
                    'outside_screening_guard_count': sum(not s['within_model_limits'] for s in result['uncertainty']['scenarios']),
                    'count': result['uncertainty']['scenario_count'], 'not_confidence_interval': True},
            }
    return {'schema': 'aerolab-nacelle-credibility-v1', 'source': SOURCE_URL,
        'purpose': 'Disclose model-form and boundary discrepancies before interpreting geometry sensitivities.',
        'calibration_performed': False, 'experimental_validation': False,
        'source_cases': 'NASA Tables 6-9 are analysis references; no fitted training set or validated holdout is claimed.',
        'interpretation': ['Conservation checks establish equation/numerical consistency only.',
            'Source pressures include propeller influence; source flows and temperatures are never imposed or fitted.',
            'Agreement in total motor flow does not establish its gap/slot split or local convection.',
            'Required UA is an inverse diagnostic at frozen flow and solid resistance, not an available physical enhancement.',
            'Out-of-domain raw temperatures describe model failure, not actual X-57 temperatures.'],
        'cases': cases}


def check(actual, saved, path='root'):
    if isinstance(actual, float) and isinstance(saved, (int, float)):
        if not math.isclose(actual, saved, rel_tol=1e-10, abs_tol=1e-9):
            raise ValueError(f'{path}: {actual} != {saved}')
    elif isinstance(actual, dict) and isinstance(saved, dict) and actual.keys() == saved.keys():
        for key in actual:
            check(actual[key], saved[key], path + '.' + key)
    elif isinstance(actual, list) and isinstance(saved, list) and len(actual) == len(saved):
        for i, (a, b) in enumerate(zip(actual, saved)):
            check(a, b, f'{path}[{i}]')
    elif actual != saved:
        raise ValueError(f'{path}: saved evidence differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'examples' / 'nacelle_credibility.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    report = generate()
    if args.check:
        check(report, json.loads(args.output.read_text(encoding='utf-8')))
        print('Credibility evidence reproduces saved inputs, identities and results')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Wrote {args.output}')
    for name, case in report['cases'].items():
        flow = case['source_flow_comparison']
        temps = case['source_temperature_comparison']
        print(f"{name}: winding={temps['computed_proxy_c']['motor_winding']:.3f}C "
              f"source={temps['published_analysis_c']['motor_winding']:.1f}C "
              f"motor_flow_error={flow['relative_error_percent']['motor_internal_total']:+.2f}% "
              f"slots_fraction={flow['motor_slot_flow_fraction']['computed']:.3f} "
              f"status={case['summary']['result_status']}")


if __name__ == '__main__':
    main()
