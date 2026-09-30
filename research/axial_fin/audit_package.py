#!/usr/bin/env python3
"""Bounded offline appendix audit. Standard library only; no model execution."""
from __future__ import annotations
import argparse, hashlib, json, math, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = 'research/axial_fin/'
STUDY = PREFIX + 'study/'
MANIFEST = PREFIX + 'package_manifest.json'
CORE = 'research/plate_fin/conjugate_fin.py'
ORIGINAL_MANIFEST_SHA256 = '4d283fbb2dc3171e97dca0094053929c481da375c8f2970b8e1b69d9bd7a3413'
CORE_SHA256 = 'bdf9998a7f20cdd5d75fef2f5f0e49c9344ebc1e6f31a5ac955bff366d6c9d4c'

def require(test, message):
    if not test:
        raise ValueError(message)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def bounded_read(path, limit, expected_size=None):
    size = path.stat().st_size
    require(size < limit and (expected_size is None or size == expected_size), 'Size preflight failed: ' + str(path))
    with path.open('rb') as stream:
        raw = stream.read(limit)
    require(len(raw) < limit and len(raw) == size, 'Changed or oversized bounded read')
    return raw

def strict_json(raw):
    require(len(raw) < 100000, 'Oversized JSON')
    def reject(value):
        raise ValueError('Nonfinite JSON: ' + value)
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'Duplicate JSON key')
            out[key] = value
        return out
    obj = json.loads(raw, parse_constant=reject, object_pairs_hook=pairs)
    def finite(value):
        if isinstance(value, float):
            require(math.isfinite(value), 'Nonfinite JSON number')
        elif isinstance(value, dict):
            for v in value.values(): finite(v)
        elif isinstance(value, list):
            for v in value: finite(v)
    finite(obj)
    return obj

def same(a, b):
    require(type(a) in (int, float) and type(b) in (int, float), 'Numeric arithmetic required')
    require(math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-12), 'Saved arithmetic differs')

def audit(root=ROOT, expected_manifest_sha256=None, return_verified_records=False):
    root = pathlib.Path(root).resolve()
    manifest_path = (root / MANIFEST).resolve()
    require(manifest_path.is_relative_to(root), 'Manifest escapes package')
    raw = bounded_read(manifest_path, 100000)
    manifest_sha = digest(raw)
    if expected_manifest_sha256 is not None:
        require(manifest_sha == expected_manifest_sha256, 'Pinned manifest identity differs')
    manifest = strict_json(raw)
    require(manifest['schema'] == 'axial_fin_appendix_v1', 'Unknown appendix schema')
    require(manifest['physical_validation_pass'] is None and manifest['experimental_residuals_recomputed'] is False and manifest['aircraft_transfer_authorized'] is False, 'Physical scope changed')
    records = {}
    for item in manifest['files']:
        name = item['path']; p = pathlib.PurePosixPath(name)
        require(p.as_posix() == name and not p.is_absolute() and '..' not in p.parts and '\\' not in name, 'Noncanonical artifact path')
        require(name.startswith(PREFIX) or name == CORE, 'Unexpected artifact destination')
        require(name not in records and name != MANIFEST, 'Duplicate/self-listed artifact')
        require(not any(x in {'__pycache__', '.cache', '.mplconfig'} for x in p.parts), 'Cache excluded')
        require(p.suffix.lower() not in {'.log', '.pdf', '.npz', '.npy', '.pyc'}, 'Excluded artifact')
        actual = (root / name).resolve()
        require(actual.is_relative_to(root) and actual.is_file(), 'Missing or escaping artifact')
        require(type(item['bytes']) is int and item['bytes'] >= 0, 'Invalid declared size')
        data = bounded_read(actual, 100000 if p.suffix == '.json' else 250000, item['bytes'])
        require(digest(data) == item['sha256'], 'Artifact hash mismatch: ' + name)
        if p.suffix == '.json': strict_json(data)
        records[name] = data
    require(len(records) == manifest['files_count'] and sum(map(len, records.values())) == manifest['total_bytes'], 'Inventory totals differ')
    require(digest(records[STUDY + 'manifest.json']) == ORIGINAL_MANIFEST_SHA256, 'Original study inventory changed')
    original = strict_json(records[STUDY + 'manifest.json'])
    require(len(original['files']) == 34, 'Original 34-record inventory changed')
    for name, item in original['files'].items():
        data = records[STUDY + name]
        require(len(data) == item['bytes'] and digest(data) == item['sha256'], 'Original evidence changed: ' + name)
    require(digest(records[CORE]) == CORE_SHA256, 'Accepted transverse core changed')
    def saved(name): return strict_json(records[STUDY + name])
    summary = saved('study_summary.json'); math_record = saved('mathematical_verification.json'); refinement = saved('refinement.json'); review = saved('review/final_review_gate.json')
    require(len(math_record['gates']) == 15 and all(v is True for v in math_record['gates'].values()), 'Mathematical gate not accepted')
    require(all(v is True for v in refinement['gates'].values()) and len(refinement['rows']) == 14, 'Refinement record incomplete')
    require(all(v is True for v in review['checks'].values()), 'Independent review gate failed')
    for name, value in review['source_hashes'].items():
        require(digest(records[STUDY + name]) == value, 'Independent review identity differs')
    for name, key in [('axial_fin_numerical_run.py', 'numerical_run_solver_sha256'), ('axial_fin.py', 'current_label_corrected_solver_sha256'), ('PLAN.md', 'plan_sha256'), ('label_patch_verification.json', 'label_only_patch_proof_sha256'), ('mathematical_verification.json', 'mathematical_verification_sha256'), ('refinement.json', 'refinement_sha256')]:
        require(digest(records[STUDY + name]) == summary['provenance'][key], 'Summary provenance differs')
    require(summary['post_comparison_model_form_investigation'] is True and summary['physical_validation_pass'] is None and summary['experimental_residuals_recomputed'] is False, 'Study scope differs')
    require(summary['mesh'] == {'gap_cells':48, 'height_cells':144, 'axial_slabs':480, 'half_domain_represents_full16_fin17_channel_array':True}, 'Accepted mesh differs')
    require([r['speed_m_s'] for r in summary['results']] == [4.0, 10.0], 'Declared probes differ')
    require(review['results'] == summary['results'], 'Independent readout differs')
    for row in summary['results']:
        source = next(x for x in refinement['rows'] if x['V_interior_m_s'] == row['speed_m_s'] and x['mesh']['gap_cells'] == 48 and x['mesh']['axial_slabs'] == 480)
        same(row['baseline_same_mesh_G_W_K'], source['baseline_same_mesh_G_W_K']); same(row['axial_conduction_G_W_K'], source['G_W_K'])
        delta = source['G_W_K']/source['baseline_same_mesh_G_W_K'] - 1
        same(row['relative_conductance_change'], delta); same(row['conductance_change_percent'], 100*delta)
        same(row['relative_resistance_change'], 1/(1+delta)-1); same(row['resistance_change_percent'], 100*row['relative_resistance_change'])
    result = {'status':'passed', 'all_passed':True, 'original_scientific_records_preserved':34, 'original_manifest_sha256':ORIGINAL_MANIFEST_SHA256, 'listed_files':len(records), 'listed_bytes':sum(map(len,records.values())), 'maximum_JSON_bytes':max(len(v) for k,v in records.items() if k.endswith('.json')), 'stdlib_only':True, 'model_execution':False, 'source_PDF_required':False, 'physical_validation_pass':None, 'experimental_residuals_recomputed':False, 'aircraft_transfer_authorized':False}
    return (result, records, manifest_sha) if return_verified_records else result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, default=ROOT)
    parser.add_argument('--expected-manifest-sha256')
    args = parser.parse_args()
    print(json.dumps(audit(args.root, args.expected_manifest_sha256), indent=2))

if __name__ == '__main__': main()
