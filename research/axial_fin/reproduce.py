#!/usr/bin/env python3
"""Audit, snapshot and replay in a new ignored output directory; never promote evidence."""
from __future__ import annotations
import argparse, hashlib, importlib.metadata, json, os, pathlib, subprocess, sys, time, uuid
sys.dont_write_bytecode = True
from audit_package import audit, bounded_read, strict_json, ROOT, PREFIX, STUDY, CORE, MANIFEST

def output_directory(root, requested=None):
    root = pathlib.Path(root).resolve()
    allowed = root/'output'
    if allowed.is_symlink() or allowed.resolve() != allowed:
        raise ValueError('ROOT/output must not be a symlink or redirect outside its literal location')
    destination = pathlib.Path(requested).resolve() if requested else allowed/'axial-fin-replays'/('run_'+uuid.uuid4().hex)
    if destination == allowed or not destination.is_relative_to(allowed):
        raise ValueError('Replay output must be a new directory strictly inside ROOT/output/')
    if destination.exists(): raise FileExistsError('Refusing existing output directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Re-resolve after mkdir to reject symlinks introduced in parent creation.
    if not destination.resolve().is_relative_to(allowed): raise ValueError('Output path escaped allowed root')
    destination.mkdir(exist_ok=False)
    return destination

def run(root=ROOT, output=None, suite='final', expected_manifest_sha256=None):
    if suite not in {'quick', 'final', 'refinement'}:
        raise ValueError('Unsupported replay suite')
    if sys.platform != 'linux':
        raise RuntimeError('Numerical replay requires Linux: original resource accounting assumes ru_maxrss in KiB; stdlib audit works independently')
    root = pathlib.Path(root).resolve()
    accepted, records, manifest_sha = audit(root, expected_manifest_sha256, True)
    target = output_directory(root, output); workspace = target/'workspace'; workspace.mkdir()
    # Every copied byte comes from this audit snapshot. Never reopen source records.
    for name, raw in records.items():
        dest = workspace/name; dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream: stream.write(raw)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    study = workspace/STUDY; started = time.monotonic()
    # The historical verification script writes only to its disposable snapshot.
    subprocess.run([sys.executable, str(study/'verify_math.py')], cwd=workspace, env=env, stdout=subprocess.DEVNULL, check=True, timeout=300)
    mathematical = strict_json(bounded_read(study/'mathematical_verification.json', 100000))
    if not all(v is True for v in mathematical['gates'].values()): raise ValueError('Replayed mathematical gate failed')
    source = strict_json(records[STUDY+'refinement.json'])['rows']
    cases = [r for r in source if suite == 'refinement' or (suite == 'final' and r['mesh']['gap_cells'] == 48 and r['mesh']['axial_slabs'] == 480) or (suite == 'quick' and r['mesh']['gap_cells'] == 12 and r['mesh']['axial_slabs'] == 120)]
    rows = []; maximum = 0.
    scalar_keys = ['G_W_K', 'Rth_K_W', 'baseline_same_mesh_G_W_K', 'paired_relative_conductance_change', 'integrated_base_heat_W_K', 'minimum_normalized_temperature', 'maximum_normalized_temperature', 'maximum_absolute_net_axial_heat_across_internal_section_W_K']
    for i, expected in enumerate(cases):
        m = expected['mesh']; destination = target/('case_%02d.json'%i)
        if suite == 'refinement' and m['gap_cells'] == 48:
            prev = [r for r in rows if r['mesh']['gap_cells'] == 36]
            if any(r['elapsed_seconds'] >= 60 or r['process_peak_RSS_MiB'] >= 900 for r in prev):
                raise RuntimeError('Original staged refinement resource guard prevents 48-cell replay')
        subprocess.run([sys.executable, str(workspace/PREFIX/'replay_case.py'), '--nx', str(m['gap_cells']), '--ny', str(m['height_cells']), '--nz', str(m['axial_slabs']), '--speed', str(expected['V_interior_m_s']), '--output', str(destination)], cwd=workspace, env=env, stdout=subprocess.DEVNULL, check=True, timeout=360)
        actual = strict_json(bounded_read(destination, 100000))
        differences = {k:abs(actual[k]-expected[k]) for k in scalar_keys}; maximum = max(maximum, *differences.values())
        if max(differences.values()) > 1e-9: raise ValueError('Numerical payload differs beyond declared 1e-9 absolute tolerance')
        if actual['energy_relative_balance'] >= 1e-8 or actual['componentwise_backward_error_max'] >= 1e-8: raise ValueError('Replayed conservation check failed')
        if actual['provenance'] != expected['provenance']: raise ValueError('Exact numerical source/plan identity differs')
        rows.append({'speed_m_s':actual['V_interior_m_s'], 'mesh':m, 'scalar_absolute_differences':differences, 'maximum_absolute_difference':max(differences.values()), 'conductance_change_percent':100*actual['paired_relative_conductance_change'], 'energy_relative_balance':actual['energy_relative_balance'], 'true_schur_relative_residual':actual['true_schur_relative_residual'], 'elapsed_seconds':actual['elapsed_seconds'], 'process_peak_RSS_MiB':actual['process_peak_RSS_MiB'], 'result_file':destination.name, 'result_sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
        print('Replayed', m['gap_cells'], m['height_cells'], m['axial_slabs'], actual['V_interior_m_s'], 'm/s', flush=True)
        if time.monotonic()-started > 1800: raise RuntimeError('Total replay computation budget reached')
    # Check the pinned source again before reporting preservation; never use this
    # second snapshot for staging or numerical input.
    _, after, after_sha = audit(root, manifest_sha, True)
    if after_sha != manifest_sha or after != records:
        raise ValueError('Accepted source package changed during replay')
    # These hashes describe newly generated metadata, not a replacement acceptance.
    report = {'status':'packaging_replay_passed', 'suite':suite, 'post_comparison_packaging_replay':True, 'source_manifest_sha256':manifest_sha, 'source_package_unchanged_after_replay':True, 'original_scientific_records_preserved':34, 'numerical_run_solver_sha256':hashlib.sha256(records[STUDY+'axial_fin_numerical_run.py']).hexdigest(), 'label_corrected_math_solver_sha256':mathematical['axial_code_sha256'], 'mathematical_gates':mathematical['gates'], 'mathematical_replay_sha256':hashlib.sha256((study/'mathematical_verification.json').read_bytes()).hexdigest(), 'compared_scalar_keys':scalar_keys, 'absolute_equivalence_tolerance':1e-9, 'maximum_absolute_payload_difference':maximum, 'cases':rows, 'elapsed_seconds':time.monotonic()-started, 'linux_resource_assumptions':'ru_maxrss is KiB; process peak RSS includes interpreter and libraries; per-case subprocess avoids previous-case high-water accumulation; source caps unchanged', 'unchanged_equations_revalidated_claim':False, 'physical_validation_pass':None, 'experimental_residuals_recomputed':False, 'aircraft_transfer_authorized':False, 'promotion_performed':False}
    report['environment'] = {'python':sys.version, 'platform':sys.platform, 'numpy':importlib.metadata.version('numpy'), 'scipy':importlib.metadata.version('scipy')}
    raw = (json.dumps(report, indent=2, allow_nan=False)+'\n').encode()
    if len(raw) >= 100000: raise ValueError('Replay report exceeds cap')
    with (target/'replay_report.json').open('xb') as stream: stream.write(raw)
    return target

def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--root', type=pathlib.Path, default=ROOT); p.add_argument('--output', type=pathlib.Path); p.add_argument('--suite', choices=['quick','final','refinement'], default='final'); p.add_argument('--expected-manifest-sha256'); a = p.parse_args()
    print(run(a.root, a.output, a.suite, a.expected_manifest_sha256))

if __name__ == '__main__': main()
