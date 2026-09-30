#!/usr/bin/env python3
"""Refine a mathematically rejected grid without reading targets or changing gates."""
import json,time
from conjugate_fin import *

def clean(r):return {k:v for k,v in r.items() if k not in ('temperature_field_samples','mirrored_channel_contributions_W_K')}
def main():
    start=time.monotonic(); p=HERE/'verification_selected_mesh_rejected.json'; old=json.loads(p.read_text())
    assert old['code_sha256']==digest(HERE/'conjugate_fin.py') and old['plan_sha256']==digest(HERE/'precomparison_plan.json')
    assert [k for k,v in old['gates'].items() if not v]==['velocity_selected_mesh_exact_mean']
    allruns=[]
    for profile in ['fd','plug']:
        for nx,nz in [(48,1600),(64,800)]:
            m=Model(nx,3*nx,profile=profile)
            for speed in [4.,10.,20.]:
                r=m.solve(speed,nz); allruns.append(dict(clean(r),profile=profile));print('refined',profile,speed,nx,nz,r['G_W_K'],flush=True)
    comparisons=[]
    for profile in ['fd','plug']:
        for speed in [4.,10.,20.]:
            oldrow=next(r for r in old['runs'] if r['kind']=='cross_section' and r['profile']==profile and r['V_interior_m_s']==speed and r['mesh']['gap_cells']==48)
            axial=next(r for r in allruns if r['profile']==profile and r['V_interior_m_s']==speed and r['mesh']['gap_cells']==48)
            spatial=next(r for r in allruns if r['profile']==profile and r['V_interior_m_s']==speed and r['mesh']['gap_cells']==64)
            comparisons.append({'profile':profile,'speed':speed,'relative_48_to_64_spatial':abs(oldrow['G_W_K']/spatial['G_W_K']-1),'relative_800_to_1600_axial':abs(oldrow['G_W_K']/axial['G_W_K']-1)})
    _,v=poisson(48,144,WI,H); gates=dict(old['gates']); gates.update({'velocity_selected_mesh_exact_mean':abs(v['mean_relative_error'])<.002,'cross_section_convergence':max(r['relative_48_to_64_spatial'] for r in comparisons)<.005,'axial_convergence':max(r['relative_800_to_1600_axial'] for r in comparisons)<.002,'refined_energy_balance':max(r['energy_relative_balance_max'] for r in allruns)<1e-8,'refined_maximum_principle':min(r['min_normalized_temperature'] for r in allruns)>-1e-10 and max(r['max_normalized_temperature'] for r in allruns)<1+1e-10});gates={k:bool(v) for k,v in gates.items()}
    out={'status':'verified_precomparison' if all(gates.values()) else 'verification_failed_do_not_compare','gates':gates,'reused_mathematical_evidence_file':p.name,'reused_mathematical_evidence_sha256':digest(p),'refinement_plan_sha256':digest(HERE/'refinement_plan.json'),'new_runs':allruns,'refinement_comparisons':comparisons,'selected_velocity_check':v,'code_sha256':digest(HERE/'conjugate_fin.py'),'plan_sha256':digest(HERE/'precomparison_plan.json'),'refinement_code_sha256':digest(__file__),'experimental_data_read':False,'elapsed_s':time.monotonic()-start}
    (HERE/'verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(gates,indent=2),flush=True)
    if not all(gates.values()):raise SystemExit('Refinement failed; no freeze')
    freeze={'status':'numerics_frozen_before_experimental_comparison','selected':{'gap_cells':48,'height_cells':144,'axial_steps':1600,'method':'backward_euler','half_array_symmetry':True},'selection_basis':'Initial36x108 mesh rejected by unchanged0.2% exact Poisson mean gate;48x144 passes and is checked against64x192 at800 steps and against800-vs1600 axial steps, at4/10/20m/s in both model forms; all gates pass','plan_sha256':digest(HERE/'precomparison_plan.json'),'code_sha256':digest(HERE/'conjugate_fin.py'),'verification_sha256':digest(HERE/'verification.json'),'experimental_data_read':False}
    (HERE/'frozen_numerics.json').write_text(json.dumps(freeze,indent=2)+'\n');print('Freeze saved',digest(HERE/'frozen_numerics.json'),flush=True)
if __name__=='__main__':main()
