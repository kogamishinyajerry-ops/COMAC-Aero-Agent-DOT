#!/usr/bin/env python3
"""Compare accepted FV evidence with independently refined continuum modes."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
fv=json.loads((R/'verification.json').read_text())
references=[json.loads(line) for line in (R/'independent_galerkin_reference.jsonl').read_text().splitlines()]
assert fv['all_passed'] and references[-1]['odd_modes_per_direction']==40
rows=[]
for e in fv['thermal_mesh_runs']['128']['endpoints']:
    t=e['tau']
    if t<.002:continue
    ref=references[-1]['bulk'][str(t)]
    rows.append({'tau':t,'fv_bulk_theta':e['bulk_theta'],'continuum_reference_theta':ref,'relative_difference':e['bulk_theta']/ref-1})
refinement=[]
for a,b in zip(references[:-1],references[1:]):
    changes=[abs(a['bulk'][t]/b['bulk'][t]-1) for t in b['bulk'] if float(t)>=.002]
    refinement.append({'coarse_odd_modes_per_direction':a['odd_modes_per_direction'],'fine_odd_modes_per_direction':b['odd_modes_per_direction'],'maximum_relative_change_tau_ge_0p002':max(changes)})
result={'method':'Independently numerically converged sine-Galerkin continuum thermal model, analytical velocity, Gauss-Legendre quadrature, exact exponential axial propagation. Not an exact analytical thermal solution.',
        'experimental_data_used':False,'quadrature_order_per_direction':160,
        'reference_code_sha256':sha(R/'independent_galerkin_reference.py'),'reference_result_sha256':sha(R/'independent_galerkin_reference.jsonl'),'fv_verification_sha256':sha(R/'verification.json'),
        'reference_basis_refinement':refinement,
        'fundamental_eigenvalue':references[-1]['fundamental_eigenvalue'],'fully_developed_Nu_Dh':references[-1]['Nu_fully_developed'],
        'maximum_absolute_relative_difference':max(abs(r['relative_difference']) for r in rows),
        'maximum_absolute_theta_difference':max(abs(r['fv_bulk_theta']-r['continuum_reference_theta']) for r in rows),
        'interpretation':'Observed total continuum-reference difference, not a confidence interval or rigorous error bound. Spatial and temporal errors can have opposite signs. Not used to tune the solver or change preregistered gates.',
        'inlet_caveat':'Finite sine basis cannot capture the wall/inlet discontinuity exactly at tau=0; comparisons start at0.002 and retain basis refinement.',
        'rows':rows}
(R/'independent_continuum_comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'maximum_absolute_relative_difference':result['maximum_absolute_relative_difference'],'reference_basis_refinement':refinement,'fully_developed_Nu_Dh':result['fully_developed_Nu_Dh']},indent=2))
