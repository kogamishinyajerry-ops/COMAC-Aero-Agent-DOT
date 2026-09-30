#!/usr/bin/env python3
"""Post-screen check only; does not retune the frozen mesh or requirements."""
from pressure_fin import *
from concurrent.futures import ProcessPoolExecutor

def run(mesh):
    nx,ny,nz=mesh;m=PressureFin(16,.0006,nx,ny);r=m.solve(15.,(1,),nz);r['gates']=thermal_gates(r);return r
if __name__=='__main__':
    primary=json.loads((HERE/'runs/n16_t600_combined_fault.json').read_text())
    with ProcessPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,[(64,192,800),(48,144,1600)]))
    diffs=[{'mesh':r['mesh'],'G_W_K':r['G_W_K'],'Tb_at_60W_C':25+60/r['G_W_K'],'relative_G_difference_from_frozen':abs(primary['G_W_K']/r['G_W_K']-1),'gates':r['gates']} for r in rows]
    passed=all(all(r['gates'].values()) for r in rows) and diffs[0]['relative_G_difference_from_frozen']<.005 and diffs[1]['relative_G_difference_from_frozen']<.002
    save('postscreen_point_check.json',{'status':'passed' if passed else 'failed','scope':'Additional post-screen confirmation of the sole within-Re-scope Pareto point; no original requirements, parameters, frozen mesh, result or ranking changed','design_id':'n16_t600','case':'combined_fault','primary_G_W_K':primary['G_W_K'],'primary_Tb_at_60W_C':25+60/primary['G_W_K'],'rows':diffs,'code_sha256':digest(HERE/'pressure_fin.py'),'check_code_sha256':digest(__file__)})
