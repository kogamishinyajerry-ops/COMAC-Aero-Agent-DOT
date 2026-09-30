#!/usr/bin/env python3
"""Read Figure8 markers only after mathematical acceptance and hash-checked freeze."""
import json,time,pathlib,sys,math
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from conjugate_fin import *

DATA=HERE.parent/'figure-readout'/'fonseca2024_vector_readout.json'

def summarize(r):
    return {k:v for k,v in r.items() if k not in ['temperature_field_samples','mirrored_channel_contributions_W_K','mesh','method']}
def check_result(r):
    assert r['energy_relative_balance_max']<1e-8
    assert r['min_normalized_temperature']>=-1e-10 and r['max_normalized_temperature']<=1+1e-10

def solve_job(spec):
    m=Model(**spec['model']);return m.solve(spec['speed'],nz=spec['nz'],samples=spec.get('samples',False))

def main():
    frozen=json.loads((HERE/'frozen_numerics.json').read_text()); lim=json.loads((HERE/'independent_limits.json').read_text())
    assert frozen['status']=='numerics_frozen_before_experimental_comparison'
    assert frozen['code_sha256']==digest(HERE/'conjugate_fin.py')
    assert frozen['plan_sha256']==digest(HERE/'precomparison_plan.json')
    assert frozen['verification_sha256']==digest(HERE/'verification.json')
    assert lim['status']=='passed' and lim['code_sha256']==digest(HERE/'conjugate_fin.py')
    # The gate acknowledgement is written only after the independent reviewer reports no blocker.
    review=json.loads((HERE/'comparison_gate.json').read_text()); assert review['allow_comparison'] is True
    assert review['solver_sha256']==frozen['code_sha256']
    assert review['plan_sha256']==frozen['plan_sha256']
    src=json.loads(DATA.read_text()); markers=src['figure8_Rth']; assert len(markers)==12
    selected=frozen['selected']; nx=selected['gap_cells'];ny=selected['height_cells'];nz=selected['axial_steps']
    results=[]; material=[]; fields=[]
    pool=ProcessPoolExecutor(max_workers=3)
    primary_jobs=[{'model':{'nx':nx,'ny':ny,'ks':205.,'profile':profile},'speed':p['V_channel_inferred_m_s'],'nz':nz,'samples':i in [0,3]} for profile in ['fd','plug'] for i,p in enumerate(markers)]
    primary_iter=iter(pool.map(solve_job,primary_jobs))
    for profile in ['fd','plug']:
        for i,p in enumerate(markers):
            speed=p['V_channel_inferred_m_s']; want_samples=i in [0,3]
            r=next(primary_iter);check_result(r)
            obs=p['Rth_K_W']; graph=p['conservative_graphical_half_symbol_envelope'];Re=r['Re_Dh'];dRe_graph=graph['V_m_s']*(2*WI*H/(WI+H))/NU
            row={'marker_index':i,'profile':profile,'observed_approx_Rth_K_W':obs,'observed_approx_G_W_K':1/obs,
                 'author_uncertainty_separate':{'Rth_relative':.012,'Rth_absolute_K_W':.012*obs,'V_relative_range':[.037,.046],'Re_relative_range':[.046,.052],'coverage_convention':'not established here'},
                 'graphical_readout_envelope_separate':graph,
                 'laminar_nominal_scope':Re<=2300.,'laminar_author_Re_envelope_scope':Re*1.052<=2300.,'laminar_graphical_V_envelope_scope':Re+dRe_graph<=2300.,
                 'prediction':summarize(r),'relative_Rth_discrepancy':r['Rth_K_W']/obs-1,'relative_G_discrepancy':r['G_W_K']*obs-1,
                 'side_channels_G_fraction':r['mirrored_channel_contributions_W_K'][0]/r['G_W_K'],
                 'naive_17_central_channels_relative_G_bias':17*r['mirrored_channel_contributions_W_K'][-1]/r['G_W_K']-1,
                 'source_marker_drawing_index':p['drawing_index']}
            results.append(row)
            if want_samples:
                field={'profile':profile,'marker_index':i,'V_interior_m_s':speed,'normalization':'(T-Tin)/(Tb-Tin); no recovered absolute temperature run is implied','source_code_sha256':digest(HERE/'conjugate_fin.py'),'plan_sha256':digest(HERE/'precomparison_plan.json'),'freeze_sha256':digest(HERE/'frozen_numerics.json'),'readout_sha256':digest(DATA),'fields':r['temperature_field_samples']}
                name=f'temperature_fields_{profile}_marker_{i:02d}.json';(HERE/name).write_text(json.dumps(field,indent=2)+'\n');fields.append(name)
            print('comparison',profile,i,speed,'Re',Re,'Rmodel',r['Rth_K_W'],'relative_R',row['relative_Rth_discrepancy'],flush=True)
            if i in [3,11]:
                partial={'status':'comparison_in_progress','profile_just_completed':profile,'last_marker':i,'source_readout_sha256':digest(DATA),'model_code_sha256':digest(HERE/'conjugate_fin.py'),'freeze_sha256':digest(HERE/'frozen_numerics.json'),'results_so_far':results}
                (HERE/'comparison_progress.json').write_text(json.dumps(partial,indent=2)+'\n')
    # Material and printed-area mapping are shown only in the predeclared laminar scope.
    scoped=[p for p in markers if p['V_channel_inferred_m_s']*(2*WI*H/(WI+H))/NU<=2300]
    material_jobs=[{'model':{'nx':nx,'ny':ny,'ks':ks,'profile':'fd'},'speed':p['V_channel_inferred_m_s'],'nz':nz} for ks in [167.,237.] for p in scoped]
    material_iter=iter(pool.map(solve_job,material_jobs))
    for ks in [167.,237.]:
        for p in scoped:
            r=next(material_iter);check_result(r)
            material.append({'ks_W_m_K':ks,'V_m_s':p['V_channel_inferred_m_s'],'G_W_K':r['G_W_K'],'Rth_K_W':r['Rth_K_W']})
    mapping=[]
    mapping_jobs=[{'model':{'nx':nx,'ny':ny,'profile':'fd'},'speed':p['V_channel_inferred_m_s']*.00186/WI,'nz':nz} for p in scoped]
    mapping_iter=iter(pool.map(solve_job,mapping_jobs))
    for p in scoped:
        speed=p['V_channel_inferred_m_s']*.00186/WI;r=next(mapping_iter);check_result(r)
        mapping.append({'reported_V_m_s':p['V_channel_inferred_m_s'],'alternative_actual_V_m_s':speed,'G_W_K':r['G_W_K'],'Rth_K_W':r['Rth_K_W']})
    props=[]
    prop_jobs=[{'model':{'nx':nx,'ny':ny,'ka':KA*(factor if which=='k_air' else 1),'heatcap':RHO*CP*(factor if which=='volumetric_heat_capacity' else 1)},'speed':10.,'nz':nz} for which in ['k_air','volumetric_heat_capacity'] for factor in [.95,1.05]]
    prop_iter=iter(pool.map(solve_job,prop_jobs))
    for which in ['k_air','volumetric_heat_capacity']:
        for factor in [.95,1.05]:
            r=next(prop_iter);check_result(r)
            props.append({'property':which,'factor':factor,'speed_m_s':10.,'G_W_K':r['G_W_K'],'Rth_K_W':r['Rth_K_W']})
    pool.shutdown()
    stats=[]
    for profile in ['fd','plug']:
        for within in [True,False]:
            rows=[r for r in results if r['profile']==profile and r['laminar_nominal_scope']==within]
            err=np.array([r['relative_Rth_discrepancy'] for r in rows])
            stats.append({'profile':profile,'nominal_laminar_scope':within,'count':len(rows),'relative_Rth_min':float(err.min()),'relative_Rth_max':float(err.max()),'relative_Rth_mean':float(err.mean()),'relative_Rth_mean_absolute':float(np.mean(abs(err)))})
    out={'status':'untuned_bounded_model_comparison_not_exact_run_or_aircraft_validation','source_doi':'10.17533/udea.redin.20230417','source_pdf_sha256':src['source_sha256'],'source_readout_sha256':digest(DATA),'model_code_sha256':digest(HERE/'conjugate_fin.py'),'comparison_code_sha256':digest(__file__),'plan_sha256':digest(HERE/'precomparison_plan.json'),'freeze_sha256':digest(HERE/'frozen_numerics.json'),'independent_limits_sha256':digest(HERE/'independent_limits.json'),'independent_review_gate':review,
         'geometry':{'interior_gap_m':WI,'side_gap_m':WS,'height_m':H,'length_m':L,'fin_thickness_m':T,'hydraulic_diameter_m':2*WI*H/(WI+H)},
         'nominal_properties':{'ks_W_m_K':205.,'rho_kg_m3':RHO,'cp_J_kg_K':CP,'k_air_W_m_K':KA,'nu_m2_s':NU,'derived_Pr':NU*RHO*CP/KA,'source_separately_printed_Pr_not_used':.7},
         'numerics':selected,'results':results,'summary_discrepancies':stats,'material_sensitivity_primary_fd_in_scope':material,'reported_area_mapping_sensitivity_primary_fd_in_scope':mapping,'air_property_sensitivities_at_predeclared_10_m_s':props,'temperature_field_files':fields,
         'limitations':['Prescribed fully developed and plug profiles are model-form sensitivity cases, not an entrance-flow solution or confidence bounds.','No axial solid conduction, axial fluid conduction, cross-flow, turbulence, base spreading, contact resistance or duct heat loss.','Source numerical air properties are assumptions, not recovered per-run experimental conditions.','Material conductivities are independently declared scenarios; tested alloy remains unidentified.','Rth target is approximately graph-read, loss-corrected; author uncertainty and graphical allowance are kept separate.','12 recoverable markers retained; a thirteenth claimed experiment is not invented.','The high-speed cases exceed the predeclared Re2300 scope and cannot validate this laminar model.','Nominal source velocity range and stated approximate Re range are not algebraically identical under the recovered physical dimensions.']}
    (HERE/'comparison.json').write_text(json.dumps(out,indent=2)+'\n')
    assert (HERE/'comparison.json').stat().st_size<100000
    print(json.dumps(stats,indent=2),flush=True)
if __name__=='__main__':main()
