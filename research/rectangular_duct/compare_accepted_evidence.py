#!/usr/bin/env python3
"""Record exact supported-grid replay identity, without claiming a new blind test."""
import json
from rectangular_graetz import ROOT, CODE_DIR, INPUT_DIR, ORIGINAL_DIR, sha, save
load=lambda base,name:json.loads((base/name).read_text())
oldv,newv=load(ORIGINAL_DIR,'verification.json'),load(ROOT,'verification.json')
oldf,newf=load(ORIGINAL_DIR,'frozen_response.json'),load(ROOT,'frozen_response.json')
oldc,newc=load(ORIGINAL_DIR,'experimental_comparison.json'),load(ROOT,'experimental_comparison.json')
without=lambda obj,keys:{k:v for k,v in obj.items() if k not in keys}
checks={
 'verification_numerical_payload_exactly_equal':without(oldv,{'provenance','elapsed_seconds'})==without(newv,{'provenance','elapsed_seconds'}),
 'frozen_response_numerical_payload_exactly_equal':without(oldf,{'provenance','verification_sha256'})==without(newf,{'provenance','verification_sha256'}),
 'all_32_comparison_rows_exactly_equal':oldc['rows']==newc['rows'],
 'grouped_residual_statistics_exactly_equal':oldc['groups']==newc['groups'],
 'interpolation_check_results_exactly_equal':oldc['interpolation_verification']==newc['interpolation_verification'],
 'source_transcription_bytes_identical':sha(INPUT_DIR/'experimental_source.json')==sha(ORIGINAL_DIR/'experimental_source.json'),
 'initial_plan_bytes_identical':sha(INPUT_DIR/'numerical_plan.json')==sha(ORIGINAL_DIR/'numerical_plan.json'),
 'refinement_plan_bytes_identical':sha(INPUT_DIR/'refinement_plan.json')==sha(ORIGINAL_DIR/'refinement_plan.json'),
 'all_original_math_gates_still_pass':newv['all_passed'] and all(newv['gates'].values()),
 'no_physical_validation_pass_claimed':newc['physical_validation_pass'] is None,
 'new_execution_phase_honestly_labeled':newv['provenance']['execution_phase']=='postcomparison_guard_only_packaging_replay',
 'source_pdf_audit_status_explicit':newc['source_pdf_audit']['status'] in ('not_requested','passed'),
}
if not all(checks.values()):raise AssertionError({k:v for k,v in checks.items() if not v})
result={
 'purpose':'Post-comparison packaging replay and numeric equivalence evidence, not a new unseen experimental test',
 'original_precomparison_solver_sha256':sha(ORIGINAL_DIR/'rectangular_graetz.py'),
 'original_precomparison_verification_sha256':sha(ORIGINAL_DIR/'verification.json'),
 'original_precomparison_frozen_response_sha256':sha(ORIGINAL_DIR/'frozen_response.json'),
 'original_experimental_comparison_sha256':sha(ORIGINAL_DIR/'experimental_comparison.json'),
 'packaged_solver_sha256':sha(CODE_DIR/'rectangular_graetz.py'),
 'packaged_verification_sha256':sha(ROOT/'verification.json'),
 'packaged_frozen_response_sha256':sha(ROOT/'frozen_response.json'),
 'packaged_experimental_comparison_sha256':sha(ROOT/'experimental_comparison.json'),
 'guard_change':'Reject unsupported grid dimensions below2 before assembly; accepted grids use at least16 cells per short side',
 'non_numerical_changes':['relocatable code/input/output paths','explicit replay provenance','optional source-PDF audit','display-only downsampled/rounded field export'],
 'equations_grids_and_tolerances_changed':False,'checks':checks,'all_passed':True}
save(ROOT/'packaging_replay.json',result)
print('All supported-grid verification, frozen-curve, interpolation and experimental residual numerics are exactly identical')
