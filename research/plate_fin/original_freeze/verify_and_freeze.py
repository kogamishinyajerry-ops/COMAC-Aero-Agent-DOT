#!/usr/bin/env python3
"""Verify without reading experimental targets, then freeze numerical choices."""
import json, pathlib, time, math
import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve
from conjugate_fin import Model,poisson,Assembler,H,T,L,WI,WS,KA,RHO,CP,digest,HERE

def compact(r): return {k:v for k,v in r.items() if k not in ['temperature_field_samples','mirrored_channel_contributions_W_K']}
def relative(a,b): return abs(a/b-1)
def fin_bath(ny,ks,h):
    dy=H/ny; ids=np.arange(ny); a=Assembler(ny); a.connect(ids[:-1],ids[1:],ks*T/dy); a.ground(ids[0],2*ks*T/dy)
    # Here excess tau=(Ts-Tin)/(Tb-Tin); root tau=1, bath tau=0.
    K=a.matrix()+diags(np.full(ny,2*h*dy)); rhs=a.bound.copy(); tau=spsolve(K,rhs)
    q=2*ks*T/dy*(1-tau[0]); exact=np.sqrt(2*h*ks*T)*np.tanh(H*np.sqrt(2*h/(ks*T)))
    profile=np.cosh(np.sqrt(2*h/(ks*T))*(H-(ids+.5)*dy))/np.cosh(np.sqrt(2*h/(ks*T))*H)
    return {'ny':ny,'ks':ks,'h':h,'Q_per_length':float(q),'exact_Q_per_length':float(exact),'relative_Q_error':relative(q,exact),'profile_max_abs':float(max(abs(tau-profile)))}

def main():
    start=time.monotonic(); checks={}; runs=[]
    checks['geometry_closure_error_m']=abs(16*T+15*WI+2*WS-.0452)
    velocity=[]
    for nx in [12,24,36,48]:
        _,v=poisson(nx,3*nx,WI,H); velocity.append(dict(v,nx=nx,ny=3*nx))
    checks['velocity_convergence']=velocity
    checks['analytic_fin_bath']=[fin_bath(ny,ks,h) for ny in [36,72,144] for ks in [167.,237.] for h in [50.,200.,1000.]]
    for profile in ['fd','plug']:
        for speed in [4.,10.,20.]:
            for nx in [12,24,36,48]:
                r=Model(nx,3*nx,profile=profile).solve(speed,nz=800)
                rr=dict(compact(r),profile=profile,kind='cross_section');runs.append(rr)
                print('spatial',profile,speed,nx,r['G_W_K'],r['energy_relative_balance_max'],flush=True)
    # Separate uniform axial convergence at the eventual candidate cross-section.
    for profile in ['fd','plug']:
        m=Model(36,108,profile=profile)
        for speed in [4.,10.,20.]:
            for nz in [200,400,800,1600]:
                r=m.solve(speed,nz=nz); runs.append(dict(compact(r),profile=profile,kind='axial'))
                print('axial',profile,speed,nz,r['G_W_K'],flush=True)
    # Conservative symmetry reduction compared with full four-fin array.
    half=Model(12,36,nfins=4).solve(10.,nz=400); full=Model(12,36,nfins=4,full=True).solve(10.,nz=400)
    checks['half_full_symmetry_relative_G']=relative(half['G_W_K'],full['G_W_K'])
    ad=Model(12,36,grounded=False).solve(10.,nz=200)
    checks['all_adiabatic']={'G_W_K':ad['G_W_K'],'temperature_min':ad['min_normalized_temperature'],'temperature_max':ad['max_normalized_temperature']}
    material=[]
    for ks in [.001,167.,205.,237.,1e8]:
        r=Model(12,36,ks=ks).solve(10.,nz=400); material.append({'ks':ks,'G_W_K':r['G_W_K']})
    iso=Model(12,36,isothermal=True).solve(10.,nz=400)
    checks['material_monotonicity']=material; checks['isothermal_fins_G']=iso['G_W_K']; checks['isothermal_limit_relative']=relative(material[-1]['G_W_K'],iso['G_W_K'])
    # A manufactured linear temperature scaling is checked at the discrete operator level.
    m=Model(12,36); f=np.linspace(.1,.8,m.n); a=m.K@f; checks['linear_operator_scaling_relative']=float(np.linalg.norm(m.K@(23*f)-23*a,np.inf)/np.linalg.norm(23*a,np.inf))
    spatial=[]; axial=[]
    for profile in ['fd','plug']:
        for speed in [4.,10.,20.]:
            g={r['mesh']['gap_cells']:r['G_W_K'] for r in runs if r['kind']=='cross_section' and r['profile']==profile and r['V_interior_m_s']==speed}
            spatial.append({'profile':profile,'speed':speed,'relative_24_to_36':relative(g[24],g[36]),'relative_36_to_48':relative(g[36],g[48])})
            g={r['mesh']['axial_steps']:r['G_W_K'] for r in runs if r['kind']=='axial' and r['profile']==profile and r['V_interior_m_s']==speed}
            axial.append({'profile':profile,'speed':speed,'relative_400_to_800':relative(g[400],g[800]),'relative_800_to_1600':relative(g[800],g[1600])})
    gates={
        'geometry':checks['geometry_closure_error_m']<1e-14,
        'velocity_positive':all(v['min_raw_m2']>0 for v in velocity),
        'velocity_residual':max(v['relative_residual'] for v in velocity)<1e-9,
        'velocity_force_balance':max(v['force_balance_relative'] for v in velocity)<1e-9,
        'velocity_selected_mesh_exact_mean':abs(velocity[2]['mean_relative_error'])<.002,
        'fin_analytic_limit':max(r['relative_Q_error'] for r in checks['analytic_fin_bath'] if r['ny']==144)<.002,
        'half_full_symmetry':checks['half_full_symmetry_relative_G']<1e-10,
        'adiabatic_limit':max(abs(ad['min_normalized_temperature']),abs(ad['max_normalized_temperature']))<1e-10,
        'isothermal_limit':checks['isothermal_limit_relative']<1e-5,
        'material_monotonicity':all(a['G_W_K']<b['G_W_K'] for a,b in zip(material,material[1:])),
        'linear_scaling':checks['linear_operator_scaling_relative']<1e-10,
        'energy_balance':max(r['energy_relative_balance_max'] for r in runs)<1e-8,
        'temperature_maximum_principle':min(r['min_normalized_temperature'] for r in runs)>-1e-10 and max(r['max_normalized_temperature'] for r in runs)<1+1e-10,
        'cross_section_convergence':max(s['relative_36_to_48'] for s in spatial)<.005,
        'axial_convergence':max(s['relative_800_to_1600'] for s in axial)<.002}
    gates={k:bool(v) for k,v in gates.items()}
    out={'status':'verified_precomparison' if all(gates.values()) else 'verification_failed_do_not_compare','gates':gates,'checks':checks,'spatial_convergence':spatial,'axial_convergence':axial,'runs':runs,'plan_sha256':digest(HERE/'precomparison_plan.json'),'code_sha256':digest(HERE/'conjugate_fin.py'),'verification_code_sha256':digest(__file__),'elapsed_s':time.monotonic()-start,'experimental_data_read':False}
    (HERE/'verification.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(gates,indent=2),flush=True)
    if not all(gates.values()): raise SystemExit('Verification failed; no comparison freeze written')
    freeze={'status':'numerics_frozen_before_experimental_comparison','selected':{'gap_cells':36,'height_cells':108,'axial_steps':1600,'method':'backward_euler','half_array_symmetry':True},'selection_basis':'36 vs48 across gap, with ny=3*nx;1600 vs800 uniform axial steps, at declared4/10/20m/s speeds in both prescribed velocity model forms; all gates passed','plan_sha256':digest(HERE/'precomparison_plan.json'),'code_sha256':digest(HERE/'conjugate_fin.py'),'verification_sha256':digest(HERE/'verification.json'),'experimental_data_read':False}
    (HERE/'frozen_numerics.json').write_text(json.dumps(freeze,indent=2)+'\n')
    print('Freeze saved',digest(HERE/'frozen_numerics.json'),flush=True)
if __name__=='__main__':main()
