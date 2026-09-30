#!/usr/bin/env python3
"""Offline package/content/provenance audit and repository-destination manifest."""
import json
from pathlib import Path
from package_paths import ROOT, CODE_DIR, INPUT_DIR, ORIGINAL_DIR, sha, save
load=lambda p:json.loads(p.read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
anchor=load(CODE_DIR/'packaging_provenance.json')
for name,digest in anchor['original_freeze_anchors'].items():assert sha(ORIGINAL_DIR/name)==digest
v=load(ROOT/'verification.json');f=load(ROOT/'frozen_response.json');c=load(ROOT/'experimental_comparison.json');s=load(INPUT_DIR/'experimental_source.json')
assert v['all_passed'] and all(v['gates'].values()) and f['all_mathematical_gates_passed']
assert f['verification_sha256']==sha(ROOT/'verification.json')
for r in (v,f,c):
    assert r['provenance']['code_sha256']==sha(CODE_DIR/'rectangular_graetz.py')
    assert r['provenance']['plan_sha256']==sha(INPUT_DIR/'numerical_plan.json')
    assert r['provenance']['refinement_plan_sha256']==sha(INPUT_DIR/'refinement_plan.json')
    assert r['provenance']['original_solver_sha256']==anchor['original_freeze_anchors']['rectangular_graetz.py']
    assert r['provenance']['execution_phase']=='postcomparison_guard_only_packaging_replay'
assert c['comparison_code_sha256']==sha(CODE_DIR/'compare_experiment.py')
assert c['frozen_response_sha256']==sha(ROOT/'frozen_response.json')
assert c['source_transcription_sha256']==sha(INPUT_DIR/'experimental_source.json')
assert c['original_source_pdf_sha256']==s['source']['pdf_sha256']==anchor['original_source_pdf_sha256']
assert c['source_pdf_audit']['status'] in ('not_requested','passed')
assert c['physical_validation_pass'] is None
assert len(c['rows'])==32 and [g['count'] for g in c['groups']]==[12,11,9]
assert sum(r['Re'] is None for r in c['rows'])==8
for row in c['rows']:
    assert row['Tin_F']<row['Tout_F']<row['Tw_F']
    assert 0<row['observed_bulk_theta']<1 and 0<row['predicted_bulk_theta']<1
for a,b in zip(f['curve'][:-1],f['curve'][1:]):assert a['tau']<b['tau'] and a['bulk_theta']>=b['bulk_theta']
replay=load(ROOT/'packaging_replay.json');assert replay['all_passed'] and all(replay['checks'].values())
assert replay['packaged_verification_sha256']==sha(ROOT/'verification.json')
assert replay['packaged_frozen_response_sha256']==sha(ROOT/'frozen_response.json')
assert replay['packaged_experimental_comparison_sha256']==sha(ROOT/'experimental_comparison.json')
tests=load(ROOT/'packaging_tests.json');assert tests['march_method_ast_identical'] and tests['supported_grid_short_marches_bitwise_identical']
independent=load(ROOT/'independent_continuum_comparison.json')
assert independent['reference_code_sha256']==sha(CODE_DIR/'independent_galerkin_reference.py')
assert independent['reference_result_sha256']==sha(ROOT/'independent_galerkin_reference.jsonl')
assert independent['fv_verification_sha256']==sha(ROOT/'verification.json')
display=load(ROOT/'display_fields.json')
assert display['source_solver_sha256']==sha(CODE_DIR/'rectangular_graetz.py')
assert display['source_ny']==128 and display['source_nx']==256 and display['decimal_places']==6
assert len(display['sampled_row_indices'])==17 and len(display['sampled_column_indices'])==33
assert all(len(a)==17 and all(len(row)==33 for row in a) for a in display['fields'].values())
assert not list(CODE_DIR.rglob('*.pdf')) and not list(ROOT.glob('*.pdf'))
assert not list(CODE_DIR.rglob('*.npz')) and not list(ROOT.glob('*.npz'))
replay_index={'label':'Recorded experimental-comparison replay',
 'live_computation':False,'physical_validation_pass':None,'aircraft_transfer_authorized':False,
 'chronology':'Post-comparison packaged replay; original precomparison freeze is preserved separately',
 'source_title':'P. Wibulswas, UCL1966, Appendix7.6 pp124–125',
 'source_url':'https://discovery.ucl.ac.uk/1381757/1/388313.pdf',
 'source_pdf_sha256':anchor['original_source_pdf_sha256'],'source_pdf_required':False,
 'target':'Mixed outlet attenuation (Tw−Tout)/(Tw−Tin)',
 'conditioning':'Reported source Gz is a reduced flow/property input; this is not a raw device-temperature prediction',
 'case_count':32,'missing_Re_count':8,
 'residual_display':'Multiply raw theta residual by100 for attenuation percentage points; positive means less predicted heat pickup',
 'caveats':['Incomplete experimental uncertainty','Transition/buoyancy/property applicability concerns','No fitted coefficients or residual-based filtering'],
 'artifacts':{'comparison':'experimental_comparison.json','response':'frozen_response.json','display_fields':'display_fields.json','mathematical_verification':'verification.json','replay_identity':'packaging_replay.json'},
 'packaged_solver_sha256':sha(CODE_DIR/'rectangular_graetz.py'),
 'original_precomparison_frozen_response_sha256':anchor['original_freeze_anchors']['frozen_response.json'],
 'comparison_sha256':sha(ROOT/'experimental_comparison.json')}
save(ROOT/'replay_index.json',replay_index)
code_files=[p for p in CODE_DIR.rglob('*') if p.is_file() and not any(x.startswith('.') or x=='__pycache__' for x in p.relative_to(CODE_DIR).parts) and p.suffix in ('.py','.json','.jsonl','.md','.sh','.txt')]
evidence_names=['replay_index.json','verification.json','frozen_response.json','experimental_comparison.json','interpolation_verification.json','packaging_tests.json','packaging_replay.json','independent_galerkin_reference.jsonl','independent_continuum_comparison.json','display_fields.json','cross_section_fields.png','frozen_response.png','historical_comparison.png','README.md']
if (ROOT/'relocation_audit.json').exists():
    relocation=load(ROOT/'relocation_audit.json')
    assert relocation['all_passed'] and relocation['tested_audit_code_sha256']==sha(CODE_DIR/'audit_package.py')
    evidence_names.append('relocation_audit.json')
entries=[]
for p,prefix,rel in [(p,'research/rectangular_duct',str(p.relative_to(CODE_DIR))) for p in code_files]+[(ROOT/name,'examples/rectangular_experiment',name) for name in evidence_names]:
    assert p.is_file(),p
    size=p.stat().st_size
    if p.suffix=='.json':assert size<100000;load(p)
    if p.suffix=='.png':assert size<250000
    entries.append({'proposed_repository_path':f'{prefix}/{rel}','bytes':size,'sha256':sha(p)})
manifest={
 'all_audits_passed':True,'package_kind':'Offline research-only rectangular-duct experimental-comparison replay',
 'chronology':'Original precomparison freeze preserved; this is a post-comparison packaging/reproducibility run',
 'physical_validation_pass':None,'aircraft_transfer_authorized':False,
 'application_dependencies_added':False,'research_requirements_file':'research/rectangular_duct/requirements-research.txt',
 'original_freeze_anchors':anchor['original_freeze_anchors'],
 'packaged_solver_sha256':sha(CODE_DIR/'rectangular_graetz.py'),
 'reproduce_from_repository_root':'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 bash research/rectangular_duct/reproduce.sh',
 'optional_source_pdf_audit':'python research/rectangular_duct/compare_experiment.py --audit-source-pdf /path/to/388313.pdf',
 'source_pdf_required':False,'source_pdf_redistributed':False,
 'publication_exclusions':['PDFs','full-resolution NPZ','logs','caches','__pycache__'],
 'display_field_notice':'17×33 point samples rounded to6 decimals; independent of full-grid acceptance evidence',
 'files':sorted(entries,key=lambda e:e['proposed_repository_path']),
 'files_count':len(entries),'total_listed_bytes':sum(e['bytes'] for e in entries)}
save(ROOT/'package_manifest.json',manifest)
print(json.dumps({'all_audits_passed':True,'files_count':len(entries),'total_listed_bytes':manifest['total_listed_bytes'],'manifest':str(ROOT/'package_manifest.json')},indent=2))
