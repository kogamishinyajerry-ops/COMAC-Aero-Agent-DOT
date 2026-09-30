#!/usr/bin/env python3
"""Predeclared numerical checks; no requirements ranking here."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
from concurrent.futures import ProcessPoolExecutor, as_completed
from pressure_fin import *
PROBES=[('baseline_nominal',16,.00086,25.,()),('baseline_combined',16,.00086,15.,(1,)),('wide_nominal',12,.0006,25.,()),('dense_combined',20,.0012,15.,(1,))]
def run(task):
    name,N,t,p,b,nx,ny,nz=task;m=PressureFin(N,t,nx,ny);r=m.solve(p,b,nz);r['probe']=name;r['gates']=thermal_gates(r);save('verification_runs/'+name+f'_{nx}_{nz}.json',r);return r

def main():
    ts=time.monotonic();tasks=[(name,N,t,p,b,nx,ny,nz) for name,N,t,p,b in PROBES for nx,ny,nz in [(48,144,800),(64,192,800),(48,144,1600)]];rows=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        fs=[pool.submit(run,x) for x in tasks]
        for f in as_completed(fs):
            r=f.result();rows.append(r);print(r['probe'],r['mesh'],r['G_W_K'],all(r['gates'].values()),flush=True)
    comparisons=[]
    for name,*_ in PROBES:
        rr=[r for r in rows if r['probe']==name];s=next(r for r in rr if r['mesh']['nx']==48 and r['mesh']['nz']==800);fine=next(r for r in rr if r['mesh']['nx']==64);ax=next(r for r in rr if r['mesh']['nz']==1600)
        comparisons.append({'probe':name,'spatial_G_relative':abs(s['G_W_K']/fine['G_W_K']-1),'axial_G_relative':abs(s['G_W_K']/ax['G_W_K']-1)})
    limits=[]
    for N,t in [(12,.0006),(16,.00086),(20,.0012)]:
        m=PressureFin(N,t,48,144,profile='plug',isothermal=True);r=m.solve(25.,nz=1600);exact=analytic_isothermal_plug(m);limits.append({'N':N,'t_mm':t*1000,'numerical_W_K':r['G_W_K'],'analytic_W_K':exact,'relative_error':r['G_W_K']/exact-1})
        print('analytic plug',N,limits[-1],flush=True)
    m=PressureFin();fin=m.fins[2];tau=spsolve(m.K[fin,:][:,fin],m.root[fin]);heff=1/(m.gap/m.nx/(2*m.ka)+m.t/(2*m.ks));exact=math.sqrt(2*heff*m.ks*m.t)*math.tanh(H*math.sqrt(2*heff/(m.ks*m.t)));q=2*m.ks*m.t/m.dy*(1-tau[0]);fincheck={'analytic_W_m_K':exact,'assembled_W_m_K':q,'relative_error':q/exact-1}
    low=PressureFin(nx=12,ny=36).solve(.001,nz=100);ad=PressureFin(nx=12,ny=36,grounded=False).solve(25,nz=100)
    left=PressureFin(nx=12,ny=36).solve(15,(1,),200,details=True);right=PressureFin(nx=12,ny=36).solve(15,(15,),200)
    h=m.hydraulic(25);h2=m.hydraulic(50);hb=m.hydraulic(25,(1,));network={'doubled_pressure_flow_relative':max(abs(b['volume_flow_m3_s']/a['volume_flow_m3_s']/2-1) for a,b in zip(h,h2)),'unchanged_unblocked_flow_relative':max(abs(b['volume_flow_m3_s']/a['volume_flow_m3_s']-1) for a,b in zip(h,hb) if not b['blocked']),'blocked_mass_flow_kg_s':hb[1]['mass_flow_kg_s'],'blocked_enthalpy_W_K':left['channels'][1]['heat_transport_W_K'],'closed_branch_total_flow_difference_m3_s':sum(r['volume_flow_m3_s'] for r in h)-sum(r['volume_flow_m3_s'] for r in hb),'original_closed_branch_flow_m3_s':h[1]['volume_flow_m3_s'],'equal_interior_flow_max_relative':max(abs(r['volume_flow_m3_s']/h[1]['volume_flow_m3_s']-1) for r in h[1:-1]),'left_right_reflection_G_relative':abs(left['G_W_K']/right['G_W_K']-1)}
    gates={k:all(r['gates'][k] for r in rows) for k in rows[0]['gates']};gates.update({'spatial_convergence':all(r['spatial_G_relative']<.005 for r in comparisons),'axial_convergence':all(r['axial_G_relative']<.002 for r in comparisons),'analytic_isothermal_plug':all(abs(r['relative_error'])<.005 for r in limits),'analytic_uniform_bath_fin':abs(fincheck['relative_error'])<.002,'low_flow_capacity':abs(low['effectiveness']-1)<1e-8,'adiabatic_limit':abs(ad['G_W_K'])<1e-9,'pressure_doubling':network['doubled_pressure_flow_relative']<1e-12,'blocked_network':network['unchanged_unblocked_flow_relative']<1e-12 and network['blocked_mass_flow_kg_s']==0 and network['blocked_enthalpy_W_K']==0 and abs(network['closed_branch_total_flow_difference_m3_s']/network['original_closed_branch_flow_m3_s']-1)<1e-12,'equal_interior_network':network['equal_interior_flow_max_relative']<1e-12,'reflection_symmetry':network['left_right_reflection_G_relative']<1e-12})
    gates={k:bool(v) for k,v in gates.items()}
    out={'status':'passed' if all(gates.values()) else 'failed','gates':gates,'grid_comparisons':comparisons,'analytic_plug_rows':limits,'analytic_uniform_bath_fin':fincheck,'low_flow_effectiveness':low['effectiveness'],'adiabatic_G_W_K':ad['G_W_K'],'network_limits':network,'plan_sha256':digest(HERE/'presweep_plan.json'),'code_sha256':digest(HERE/'pressure_fin.py'),'original_model_sha256':digest(SOURCE),'verification_code_sha256':digest(__file__),'elapsed_s':time.monotonic()-ts,'selected_mesh':{'nx':48,'ny':144,'nz':800},'scope':'Numerical verification of declared synthetic model; no aircraft or experimental validation'}
    save('verification.json',out);print(json.dumps(out,indent=2),flush=True)
    if not all(gates.values()):raise SystemExit(1)
if __name__=='__main__':main()
