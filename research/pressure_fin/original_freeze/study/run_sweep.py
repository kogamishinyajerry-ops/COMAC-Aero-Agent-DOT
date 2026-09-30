#!/usr/bin/env python3
"""Finite declared sweep; every candidate retained, no optimization or fitting."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
from concurrent.futures import ProcessPoolExecutor, as_completed
from pressure_fin import *

def design_task(N,t):
    m=PressureFin(N,t);rows=[];design_id=f'n{N}_t{round(t*1e6)}'
    for cid,p,b in case_list():
        r=m.solve(p,b,800,details=(N==16 and t==.00086 and cid in ('nominal','combined_fault')));r['case_id']=cid;r['design_id']=design_id;r['gates']=thermal_gates(r)
        save(f'runs/{design_id}_{cid}.json',r)
        compact={k:r[k] for k in ['case_id','G_W_K','Rth_K_W','capacity_rate_W_K','effectiveness','volume_flow_m3_s','mass_flow_kg_s','max_Re_Dh','laminar_scope','pressure_dissipation_W','pressure_Pa','blocked_channels']}
        compact.update({'Tb_at_60W_C':25+60/r['G_W_K'],'base_temperature_C_by_heat_load_W':{str(q):25+q/r['G_W_K'] for q in [40,60,80]},'thermal_limit_pass_60W':25+60/r['G_W_K']<=85,'all_numerical_gates_pass':all(r['gates'].values()),'side_channel_flow_fraction':sum(x['flow_fraction'] for x in m.hydraulic(p,b) if x['side'])})
        rows.append(compact)
    return {'design_id':design_id,'N_fins':N,'thickness_mm':t*1000,'interior_gap_mm':m.gap*1000,'fin_only_mass_g':2700*N*t*H*L*1000,'mass_limit_pass':2700*N*t*H*L<=.04,'cases':rows}

def sensitivity_task(cid,p,b,parameter,value):
    kwargs={'ks':205.,'ka':KA,'heatcap':RHO*CP,'mu':MU,'profile':'fd'}
    if parameter=='ks':kwargs['ks']=value
    elif parameter=='ka_multiplier':kwargs['ka']=KA*value
    elif parameter=='heatcap_multiplier':kwargs['heatcap']=RHO*CP*value
    elif parameter=='mu_multiplier':kwargs['mu']=MU*value
    elif parameter=='profile':kwargs['profile']=value
    m=PressureFin(**kwargs);r=m.solve(p,b,800);r.update({'case_id':cid,'sensitivity_parameter':parameter,'sensitivity_value':value,'gates':thermal_gates(r)});save(f'sensitivity_runs/{cid}_{parameter}_{value}.json',r)
    return {k:r[k] for k in ['case_id','sensitivity_parameter','sensitivity_value','G_W_K','Rth_K_W','mass_flow_kg_s','max_Re_Dh','energy_relative_balance_max','gates']}

def dominated(row,others):
    mass=row['fin_only_mass_g']; temp=next(r['Tb_at_60W_C'] for r in row['cases'] if r['case_id']=='combined_fault')
    return [a['design_id'] for a in others if a['design_id']!=row['design_id'] and a['fin_only_mass_g']<=mass and next(x['Tb_at_60W_C'] for x in a['cases'] if x['case_id']=='combined_fault')<=temp and (a['fin_only_mass_g']<mass or next(x['Tb_at_60W_C'] for x in a['cases'] if x['case_id']=='combined_fault')<temp)]

def main():
    v=json.loads((HERE/'verification.json').read_text())
    if v['status']!='passed' or v['plan_sha256']!=digest(HERE/'presweep_plan.json') or v['code_sha256']!=digest(HERE/'pressure_fin.py'):raise RuntimeError('verification must pass on current frozen model/plan')
    ts=time.monotonic();designs=[];sens=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        fs={pool.submit(design_task,N,t):('design',N,t) for N in [12,16,20] for t in [.0006,.00086,.0012]}
        for cid,p,b in [case_list()[0],case_list()[3]]:
            for param,vals in [('ks',[167.,237.]),('ka_multiplier',[.95,1.05]),('heatcap_multiplier',[.95,1.05]),('mu_multiplier',[.95,1.05]),('profile',['plug'])]:
                for value in vals:fs[pool.submit(sensitivity_task,cid,p,b,param,value)]=('sensitivity',cid,param,value)
        for f in as_completed(fs):
            meta=fs[f];r=f.result();(designs if meta[0]=='design' else sens).append(r);print(meta,'complete',flush=True)
    designs.sort(key=lambda r:(r['N_fins'],r['thickness_mm']));sens.sort(key=lambda r:(r['case_id'],r['sensitivity_parameter'],str(r['sensitivity_value'])))
    scope=[r for r in designs if all(c['laminar_scope'] and c['all_numerical_gates_pass'] for c in r['cases'])]
    for d in designs:
        d['all_cases_within_declared_Re_scope']=all(c['laminar_scope'] for c in d['cases']);d['dominated_by_all_extrapolations']=dominated(d,designs);d['dominated_by_scope_candidates']=dominated(d,scope) if d in scope else None
        d['pareto_within_Re_scope']=d in scope and not d['dominated_by_scope_candidates'];d['nominal_requirement_pass']=d['mass_limit_pass'] and next(c['thermal_limit_pass_60W'] for c in d['cases'] if c['case_id']=='nominal');d['combined_requirement_pass']=d['mass_limit_pass'] and next(c['thermal_limit_pass_60W'] for c in d['cases'] if c['case_id']=='combined_fault')
        for c in d['cases']:c['conditional_screen_pass']=c['laminar_scope'] and c['all_numerical_gates_pass'] and d['mass_limit_pass'] and c['thermal_limit_pass_60W']
    out={'status':'declared_synthetic_screen_completed','requirements':json.loads((HERE/'presweep_plan.json').read_text())['requirements_synthetic_not_aircraft'],'designs':designs,'all_numerical_gates_pass':all(c['all_numerical_gates_pass'] for d in designs for c in d['cases']),'plan_sha256':digest(HERE/'presweep_plan.json'),'code_sha256':digest(HERE/'pressure_fin.py'),'verification_sha256':digest(HERE/'verification.json'),'sweep_code_sha256':digest(__file__),'elapsed_s':time.monotonic()-ts,'important_caveat':'A declared synthetic screen following prior experimental work, not an unseen or blinded requirements test. Fixed-pressure branch closure changes flow fractions, not unblocked absolute flow. Fin-only mass and passive pressure dissipation are not system mass or electrical power.'}
    save('design_results.json',out);save('sensitivity_results.json',{'status':'illustrative_sensitivities_not_confidence_bounds','rows':sens,'plan_sha256':digest(HERE/'presweep_plan.json'),'code_sha256':digest(HERE/'pressure_fin.py'),'all_numerical_gates_pass':all(all(r['gates'].values()) for r in sens)})
    print('all complete',flush=True)
if __name__=='__main__':main()
