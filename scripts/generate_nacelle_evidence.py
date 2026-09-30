"""Reproducible source-load and CAD-design sensitivity evidence (stdlib only)."""
from __future__ import annotations
import argparse
import hashlib
import re
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


# One complete logical case per bounded text file. The index is deliberately
# separate from the former monolithic path, so publication cannot retry it.
CASE_FILE_MAX_BYTES = 200000
MANIFEST_MAX_BYTES = 64000
STORAGE_SCHEMA = 'aerolab-nacelle-evidence-index-v1'


def _canonical_digest(value):
    blob = json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')


def _bounded_read(path, limit):
    if path.is_symlink():
        raise ValueError(f'Evidence symlinks are not accepted: {path.name}')
    with path.open('rb') as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f'Evidence exceeds bounded size: {path.name}')
    return data


def write_evidence(result, manifest_path):
    """Validate all case sizes before writing; atomically publish index last."""
    manifest_path = Path(manifest_path)
    parts = []
    for name, case in result['cases'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
            raise ValueError('Evidence case name must be a plain stable identifier')
        data = _encode(case)
        if not 0 < len(data) <= CASE_FILE_MAX_BYTES:
            raise ValueError(f'{name}: case exceeds {CASE_FILE_MAX_BYTES} bytes')
        parts.append((name, name + '.json', data))
    index = {'schema': STORAGE_SCHEMA, 'storage': 'one_complete_case_per_json',
             'metadata': {k: v for k, v in result.items() if k != 'cases'},
             'case_file_max_bytes': CASE_FILE_MAX_BYTES,
             'reconstructed_data_sha256': _canonical_digest(result),
             'case_files': [{'name': name, 'file': filename, 'bytes': len(data),
                             'sha256': hashlib.sha256(data).hexdigest()}
                            for name, filename, data in parts]}
    encoded_index = _encode(index)
    if len(encoded_index) > MANIFEST_MAX_BYTES:
        raise ValueError('Evidence index exceeds bounded size')
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    for _, filename, data in parts:
        destination = manifest_path.parent / filename
        temporary = destination.with_suffix('.json.tmp')
        temporary.write_bytes(data)
        temporary.replace(destination)
    temporary = manifest_path.with_suffix(manifest_path.suffix + '.tmp')
    temporary.write_bytes(encoded_index)
    temporary.replace(manifest_path)
    return index


def read_evidence(manifest_path):
    """Reconstruct exactly the prior full evidence object with integrity checks."""
    manifest_path = Path(manifest_path)
    index = json.loads(_bounded_read(manifest_path, MANIFEST_MAX_BYTES))
    if index.get('schema') != STORAGE_SCHEMA or index.get('storage') != 'one_complete_case_per_json':
        raise ValueError('Unknown evidence storage schema')
    if index.get('case_file_max_bytes') != CASE_FILE_MAX_BYTES:
        raise ValueError('Evidence index has an unsupported file-size bound')
    metadata = index.get('metadata')
    if not isinstance(metadata, dict) or 'cases' in metadata:
        raise ValueError('Evidence metadata must not contain cases')
    descriptors = index.get('case_files')
    if not isinstance(descriptors, list) or not descriptors:
        raise ValueError('Evidence index has no cases')
    cases = {}
    for part in descriptors:
        if not isinstance(part, dict):
            raise ValueError('Invalid evidence case descriptor')
        name, filename, size = part.get('name'), part.get('file'), part.get('bytes')
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name):
            raise ValueError('Invalid evidence case name')
        if name in cases or filename != name + '.json':
            raise ValueError('Duplicate case or unsafe evidence filename')
        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= CASE_FILE_MAX_BYTES:
            raise ValueError('Invalid evidence case size')
        data = _bounded_read(manifest_path.parent / filename, size)
        if len(data) != size or hashlib.sha256(data).hexdigest() != part.get('sha256'):
            raise ValueError(f'{name}: evidence checksum or length differs')
        cases[name] = json.loads(data)
    result = dict(metadata)
    result['cases'] = cases
    if _canonical_digest(result) != index.get('reconstructed_data_sha256'):
        raise ValueError('Reconstructed evidence identity differs')
    return result


def check(actual, saved, path='root'):
    if isinstance(actual, float) and isinstance(saved, (int, float)):
        if not math.isclose(actual, saved, rel_tol=1e-10, abs_tol=1e-9):
            raise ValueError(f'Saved evidence differs at {path}: {actual} vs {saved}')
    elif isinstance(actual, dict) and isinstance(saved, dict):
        if actual.keys() != saved.keys():
            raise ValueError(f'Saved evidence keys differ at {path}')
        for key in actual:
            check(actual[key], saved[key], f'{path}.{key}')
    elif isinstance(actual, list) and isinstance(saved, list):
        if len(actual) != len(saved):
            raise ValueError(f'Saved evidence length differs at {path}')
        for index, (a, b) in enumerate(zip(actual, saved)):
            check(a, b, f'{path}[{index}]')
    elif actual != saved:
        raise ValueError(f'Saved evidence differs at {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'examples' / 'nacelle_evidence' / 'manifest.json',
                        help='Bounded evidence index path; complete case files are written beside it')
    parser.add_argument('--check', action='store_true', help='Verify part integrity, then reproduce every value with explicit tolerance')
    args = parser.parse_args()
    result = generate()
    if args.check:
        check(result, read_evidence(args.output))
        print('All bounded nacelle cases reproduce saved evidence (rel 1e-10 / abs 1e-9 tolerance)')
    else:
        index = write_evidence(result, args.output)
        print(f'Wrote {args.output} and {len(index["case_files"])} complete case files; each <= {CASE_FILE_MAX_BYTES} bytes')
    for name, run in result['cases'].items():
        s = run['thermal']['summary']
        print(f"{name}: flow={run['flow']['total_inlet_kg_s']:.6f}kg/s mass={run['mass_kg']:.3f}kg limit={s['limiting_component']} margin={s['min_margin_c']} screen={s['within_model_limits']}")

if __name__ == '__main__':
    main()
