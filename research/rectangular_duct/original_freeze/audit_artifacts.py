#!/usr/bin/env python3
"""Read-only evidence checks plus a compact content-hash manifest."""
import hashlib,json,math
from pathlib import Path
R=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda name:json.loads((R/name).read_text())
v=load('verification.json');f=load('frozen_response.json');c=load('experimental_comparison.json');s=load('experimental_source.json')
assert v['all_passed'] and all(v['gates'].values())
assert f['all_mathematical_gates_passed']
assert f['verification_sha256']==sha(R/'verification.json')
for record in (v,f,c):
    assert record['provenance']['plan_sha256']==sha(R/'numerical_plan.json')
    assert record['provenance']['refinement_plan_sha256']==sha(R/'refinement_plan.json')
    assert record['provenance']['code_sha256']==sha(R/'rectangular_graetz.py')
assert not v['experiment_used_for_selection'] and not f['experiment_used_for_selection']
independent=load('independent_continuum_comparison.json')
assert independent['fv_verification_sha256']==sha(R/'verification.json')
assert independent['reference_code_sha256']==sha(R/'independent_galerkin_reference.py')
assert independent['reference_result_sha256']==sha(R/'independent_galerkin_reference.jsonl')
assert c['physical_validation_pass'] is None
assert v['provenance']['code_sha256']==f['provenance']['code_sha256']==sha(R/'rectangular_graetz.py')
assert c['comparison_code_sha256']==sha(R/'compare_experiment.py')
assert c['frozen_response_sha256']==sha(R/'frozen_response.json')
assert c['source_transcription_sha256']==sha(R/'experimental_source.json')
assert s['source']['pdf_sha256']==sha((R/s['source']['pdf_relative_path']).resolve())
assert len(c['rows'])==32 and [x['count'] for x in c['groups']]==[12,11,9]
assert sum(x['Re'] is None for x in c['rows'])==8
for row in c['rows']:
    assert row['Tin_F']<row['Tout_F']<row['Tw_F']
    assert 0<row['observed_bulk_theta']<1 and 0<row['predicted_bulk_theta']<1
for left,right in zip(f['curve'][:-1],f['curve'][1:]):
    assert left['tau']<right['tau'] and left['bulk_theta']>=right['bulk_theta']
assert f['curve'][0]['bulk_theta']==1
for p in R.glob('*.json'):
    assert p.stat().st_size<100000,p
    # Python's parser accepts nonfinite tokens by default; forbid them explicitly.
    json.loads(p.read_text(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
files=['render_plots.py','independent_galerkin_reference.py','independent_galerkin_reference.jsonl','compare_independent_reference.py','independent_continuum_comparison.json','rectangular_graetz.py','compare_experiment.py','audit_artifacts.py','reproduce.sh','numerical_plan.json','refinement_plan.json','experimental_source.json','verification.json','frozen_response.json','interpolation_verification.json','experimental_comparison.json','cross_section_fields.npz','cross_section_fields.png','frozen_response.png','historical_comparison.png','initial_solver_rejected.py','initial_verification_rejected.json','README.md']
manifest={'all_evidence_audits_passed':True,'source_pdf_sha256':s['source']['pdf_sha256'],
          'files':[{'file':name,'bytes':(R/name).stat().st_size,'sha256':sha(R/name)} for name in files]}
(R/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'all_evidence_audits_passed':True,'files_hashed':len(files),'rows':len(c['rows']),'blank_Re_cells':8},indent=2))
