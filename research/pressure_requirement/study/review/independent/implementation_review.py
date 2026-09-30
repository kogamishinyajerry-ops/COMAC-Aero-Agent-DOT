"""Independent non-marching checks of the new subclass against accepted inputs."""
import gc
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import connected_components

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('independent_hydraulic_helpers',HERE/'hydraulic_review.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
STUDY = HERE.parents[1]
spec = importlib.util.spec_from_file_location('reviewed_pressure_requirement',STUDY/'pressure_requirement.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def main():
    rows = []
    for thickness in (.00086, .0006):
        for nx, ny in ((48,144), (64,192)):
            reference = h.accepted.PressureFin(t=thickness,nx=nx,ny=ny)
            for coefficient in (0,1,2):
                model = candidate.EndLossFin(t=thickness,nx=nx,ny=ny,end_loss_K=coefficient)
                coo=model.K.tocoo()
                operator_checks = {
                    'matrix_exact_identity':(model.K!=reference.K).nnz==0,
                    'floor_exact_identity':np.array_equal(model.floor,reference.floor),
                    'root_exact_identity':np.array_equal(model.root,reference.root),
                    'boundary_exact_identity':np.array_equal(model.bound,reference.bound),
                    'symmetric_matrix':(model.K!=model.K.T).nnz==0,
                    'positive_diagonal':bool(np.min(model.K.diagonal())>0),
                    'nonpositive_offdiagonal':bool(np.max(coo.data[coo.row!=coo.col])<=0),
                    'nonnegative_boundary_weights':bool(np.min(model.bound)>=0 and np.max(model.bound)>0),
                    'row_sum_matches_ground':bool(np.max(abs(model.K@np.ones(model.n)-model.bound))<1e-9),
                    'single_grounded_connected_array':connected_components(model.K,directed=False,return_labels=False)==1,
                    'full_array':len(model.channels)==17 and len(model.fins)==16,
                    'side_floors_adiabatic':all(np.all(model.floor[model.channels[i]['ids']]==0) for i in (0,16)),
                    'interior_floors_grounded':all(np.all(model.floor[c['ids'][0,:]]>0) for c in model.channels[1:-1]),
                    'sealed_fluid_diffusion_retained':all(model.K[a,b]<0 for a,b in
                        [(model.channels[1]['ids'][0,0],model.channels[1]['ids'][0,1]),
                         (model.channels[1]['ids'][0,0],model.channels[1]['ids'][1,0]),
                         (model.channels[1]['ids'][0,0],model.fins[0][0]),
                         (model.channels[1]['ids'][0,-1],model.fins[1][0])]),
                }
                domain = model.domain()
                hydraulic_rows = []
                for pressure in (15.,25.,domain['upper_Pa']):
                    open_rows = model.hydraulic(pressure)
                    closed = model.hydraulic(pressure,(1,))
                    doubled = model.hydraulic(2*pressure)
                    original = reference.hydraulic(pressure)
                    scalar_errors, force_errors, pressure_errors, dissip_errors = [], [], [], []
                    for index,(flow,channel) in enumerate(zip(open_rows,model.channels)):
                        mean, width = channel['wmean'], channel['width']
                        a = h.accepted.MU*h.accepted.L/mean
                        u = h.scalar_speed(pressure,a,coefficient)
                        scalar_errors.append(abs(flow['mean_speed_m_s']/u-1))
                        pressure_errors.append(abs(a*u+.5*h.accepted.RHO*coefficient*u*u-pressure)/pressure)
                        raw = channel['shape']*mean
                        dx,dy=channel['dx'],model.dy
                        wall_sum=2*dy/dx*(raw[:,0].sum()+raw[:,-1].sum())+2*dx/dy*(raw[0,:].sum()+raw[-1,:].sum())
                        force=h.accepted.MU*h.accepted.L*u/mean*wall_sum
                        pressure_force=a*u*width*h.accepted.H
                        force_errors.append(abs(force/pressure_force-1))
                        reported=flow['friction_dissipation_W']+flow['end_loss_dissipation_W']
                        dissip_errors.append(abs(reported/(pressure*flow['volume_flow_m3_s'])-1))
                    original_keys=['mean_speed_m_s','volume_flow_m3_s','mass_flow_kg_s','Re_Dh','flow_fraction']
                    checks={
                        'scalar_root':max(scalar_errors)<1e-10,
                        'pressure_law':max(pressure_errors)<1e-12,
                        'straight_friction_wall_force':max(force_errors)<1e-9,
                        'dissipation_counted_once':max(dissip_errors)<1e-12,
                        'exact_K0_original_arithmetic':coefficient!=0 or all(r[k]==a[k] for r,a in zip(open_rows,original) for k in original_keys),
                        'positive_K_reduces_flow':coefficient==0 or all(r['volume_flow_m3_s']<a['volume_flow_m3_s'] for r,a in zip(open_rows,original)),
                        'open_flow_unchanged_under_closure':all(a['volume_flow_m3_s']==b['volume_flow_m3_s'] for i,(a,b) in enumerate(zip(open_rows,closed)) if i!=1),
                        'sealed_flow_zero':closed[1]['volume_flow_m3_s']==closed[1]['mean_speed_m_s']==0,
                        'mass_fraction_closure':abs(sum(r['flow_fraction'] for r in closed)-1)<1e-12,
                        'equal_interior_flow':len(set(r['volume_flow_m3_s'] for r in closed[2:-1]))==1,
                        'double_pressure_behavior':all((abs(d['mean_speed_m_s']/r['mean_speed_m_s']-2)<1e-12 if coefficient==0 else math.sqrt(2)<d['mean_speed_m_s']/r['mean_speed_m_s']<2) for r,d in zip(open_rows,doubled)),
                        'peak_guard_conservative':all(r['peak_Mach']>=r['sampled_peak_Mach'] for r in open_rows),
                    }
                    hydraulic_rows.append({'pressure_Pa':pressure,'checks':checks,
                        'max_scalar_root_relative_error':max(scalar_errors),'max_force_error':max(force_errors)})
                scope=model.domain_state(domain['upper_Pa'])
                rows.append({'thickness_mm':1000*thickness,'K':coefficient,'mesh':[nx,ny],
                    'operator_checks':operator_checks,'hydraulic_checks':hydraulic_rows,
                    'domain_upper_Pa':domain['upper_Pa'],'both_conditions_in_scope_at_upper':all(x['within_domain'] for x in scope.values())})
                del model
                gc.collect()
            del reference
            gc.collect()
    checks={'all_operators_and_boundaries_identical':all(all(r['operator_checks'].values()) for r in rows),
            'all_hydraulic_invariants':all(all(c['checks'].values()) for r in rows for c in r['hydraulic_checks']),
            'both_conditions_in_scope_at_each_upper':all(r['both_conditions_in_scope_at_upper'] for r in rows)}
    result={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'rows':rows,
        'candidate_code_sha256':hashlib.sha256((STUDY/'pressure_requirement.py').read_bytes()).hexdigest(),
        'review_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'new_thermal_marches':0,'physical_validation':False}
    encoded=json.dumps(result,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n'
    assert len(encoded.encode())<100000
    Path(__file__).with_suffix('.json').write_text(encoded)
    print(json.dumps({'status':result['status'],'checks':checks,'scenarios':len(rows)},indent=2))


if __name__=='__main__':
    main()
