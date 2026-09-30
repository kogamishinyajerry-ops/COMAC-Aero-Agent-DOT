#!/usr/bin/env python3
"""Small labeled moderate-grid field samples; accepted scalar study unchanged."""
import gc,json,math
import numpy as np
from axial_fin import AxialModel,base,HERE,sha
ref=json.loads((HERE/'refinement.json').read_text());rows=[]
for speed in [4.,10.]:
 m=AxialModel(24,72,240,speed,1.);r=m.solve(True);s0,G0=m.accepted_baseline();saved=next(x for x in ref['rows'] if x['mesh']['gap_cells']==24 and x['mesh']['axial_slabs']==240 and x['V_interior_m_s']==speed)
 assert math.isclose(r['G_W_K'],saved['G_W_K'],rel_tol=1e-11,abs_tol=1e-12)
 sample=r['samples'];yi=np.unique(np.linspace(0,m.ny-1,9,dtype=int));zi=np.unique(np.linspace(0,m.nz-1,7,dtype=int))
 for fin in sample['fins']:
  ids=np.arange(fin['fin_index_from_side']*m.ny,(fin['fin_index_from_side']+1)*m.ny)[yi];baseline=1-s0[np.ix_(zi,ids)]
  fin['baseline_without_axial_normalized_T']=baseline.tolist();fin['axial_minus_baseline_normalized_T']=(np.array(fin['normalized_T'])-baseline).tolist()
 q=m.model.factor*m.ks*base.T*m.model.dy/m.dz*np.sum(np.diff(m.solid,axis=0),axis=1);ix=np.unique(np.linspace(0,m.nz-2,9,dtype=int))
 sample['axial_conduction_sections']={'z_faces_m':[0.]+((ix+1)*m.dz).tolist()+[base.L],'net_heat_positive_downstream_W_per_K':[0.]+q[ix].tolist()+[0.],'normalization':'Axial solid heat rate divided by(Tbase-Tin), summed over all16 fins; negative means upstream heat transport'}
 out={'status':'illustrative_moderate_grid_samples_not_full_resolution','mesh':r['mesh'],'speed_m_s':speed,'lambda_z':1.,'same_mesh_scalar_replay_absolute_G_difference':abs(r['G_W_K']-saved['G_W_K']),'scalar_acceptance_notice':'Final effect estimates use48x144x480; these smaller24x72x240 samples illustrate redistribution only','samples':sample,'current_solver_sha256':sha(HERE/'axial_fin.py'),'numerical_run_solver_sha256':sha(HERE/'axial_fin_numerical_run.py'),'physical_validation_pass':None,'source_targets_read':False}
 path=HERE/f'fields_V{int(speed):02d}.json';path.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');assert path.stat().st_size<100000;rows.append({'file':path.name,'sha256':sha(path),'replay_absolute_G_difference':out['same_mesh_scalar_replay_absolute_G_difference']});del m;gc.collect()
(HERE/'field_sample_index.json').write_text(json.dumps({'rows':rows,'sample_code_sha256':sha(__file__)},indent=2)+'\n');print(rows)
