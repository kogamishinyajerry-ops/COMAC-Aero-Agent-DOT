"""Independent arithmetic and provenance review of retained study artifacts."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
ROOT=HERE.parents[4]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())


def main():
    plan=load(STUDY/'plan.json')
    input_checks={p:sha(ROOT/p)==digest for p,digest in plan['input_sha256'].items()}
    summaries=[load(STUDY/'continuation/results'/f'{name}.json') for name in ('n16_t860','n16_t600')]
    run_paths=sorted((STUDY/'runs').rglob('*.json'))+sorted((STUDY/'continuation/runs').rglob('*.json'))
    runs={str(path.relative_to(STUDY)):load(path) for path in run_paths}
    fail=[]
    model_hash=sha(STUDY/'pressure_requirement.py')
    maxima={'energy_relative':0.,'equation_relative':0.,'pressure_relative':0.,'force_relative':0.,
            'hydraulic_mean_relative':0.,'Mach_bound':0.,'Re':0.,'mechanical_dissipation_fraction_60W':0.,
            'both_conditions_max_Re':0.,'both_conditions_max_Mach_bound':0.}
    for path,r in runs.items():
        dp,P,K=r['pressure_Pa'],r['nominal_pressure_budget_Pa'],r['end_loss_K']
        N,t=r['N_fins'],r['thickness_mm']/1000
        channels=r['channels']
        q=sum(c['volume_flow_m3_s'] for c in channels)
        fsum=sum(c['flow_fraction'] for c in channels)
        expected_blocked=[1] if r['condition']=='combined' else []
        checks={'source_hash':r['model_sha256']==model_hash,
            'plan_hash':r['plan_sha256']==sha(STUDY/'plan.json'),
            'accepted_operator_hash':r['accepted_operator_sha256']==plan['input_sha256']['research/pressure_fin/original_freeze/study/pressure_fin.py'],
            'geometry_scope':N==16 and r['thickness_mm'] in (.6,.86),
            'K_scope':K in (0,1,2), 'conditions':r['condition'] in ('nominal','combined'),
            'pressure_mapping':dp==(.6*P if r['condition']=='combined' else P),
            'sealed_set':r['blocked_channels']==expected_blocked,
            'energy':r['energy_relative_balance_max']<1e-8,
            'equation':r['componentwise_thermal_equation_residual_relative']<1e-8,
            'maximum_principle':r['min_normalized_T']>=-1e-9 and r['max_normalized_T']<=1+1e-9,
            'capacity':r['G_W_K']<=r['capacity_rate_W_K']*(1+1e-9),
            'mass':r['mass_transport_closure_relative']<1e-12,
            'pressure':r['pressure_closure_relative']<1e-12,
            'poisson':r['max_poisson_relative_residual']<1e-9 and r['max_poisson_force_balance_relative']<1e-9,
            'exact_hydraulics':r['max_hydraulic_flow_exact_relative_error']<.002,
            'width_closure':r['geometry_width_closure_m']<1e-14,
            'fin_only_mass':abs(r['fin_only_mass_kg']/(2700*N*t*.0113*.09)-1)<1e-14,
            'heat_target_arithmetic':r['capacity_at_uniform_base_85C_W']==60*r['G_W_K'],
            'base_temperature_arithmetic':r['required_uniform_base_at_60W_C']==25+60/r['G_W_K'],
            'dissipation':abs(r['pressure_dissipation_W']/(dp*q)-1)<1e-12,
            'dissipation_split':abs((r['friction_dissipation_W']+r['end_loss_dissipation_W'])/(dp*q)-1)<1e-12,
            'fraction':abs(fsum-1)<1e-12,
            'all_stored_gates':all(r['gates'].values()),
            'nominal_and_combined_scope':all(x['within_domain'] and x['max_Re_Dh']<2300 and x['max_peak_Mach']<.1 for x in r['domain_at_both_conditions'].values()),
            'active_Re_and_Mach':r['max_Re_Dh']<2300 and r['max_peak_Mach']<.1,
        }
        for c in channels:
            u=c['mean_speed_m_s'];width=c['gap_mm']/1000
            if c['blocked']:
                checks['sealed_zero_'+str(c['channel'])]=u==c['volume_flow_m3_s']==c['heat_transport_W_K']==0
                continue
            reconstructed=c['a_Pa_s_m']*u+.5*1.204*K*u*u
            checks['channel_'+str(c['channel'])]=(abs(reconstructed/dp-1)<1e-12 and
                abs(c['volume_flow_m3_s']/(u*width*.0113)-1)<1e-12 and
                abs(c['Re_Dh']/(u*2*width*.0113/((width+.0113)*1.516e-5))-1)<1e-12 and
                c['peak_Mach']>=c['sampled_peak_Mach'] and
                abs((c['friction_dissipation_W']+c['end_loss_dissipation_W'])/(dp*c['volume_flow_m3_s'])-1)<1e-12)
        if not all(checks.values()):
            fail.append({'record':path,'failed_checks':[key for key,value in checks.items() if not value]})
        for key,value in [('energy_relative',r['energy_relative_balance_max']),('equation_relative',r['componentwise_thermal_equation_residual_relative']),
                          ('pressure_relative',r['pressure_closure_relative']),('force_relative',r['max_poisson_force_balance_relative']),
                          ('hydraulic_mean_relative',r['max_hydraulic_flow_exact_relative_error']),('Mach_bound',r['max_peak_Mach']),
                          ('Re',r['max_Re_Dh']),('mechanical_dissipation_fraction_60W',r['pressure_dissipation_W']/60),
                          ('both_conditions_max_Re',max(x['max_Re_Dh'] for x in r['domain_at_both_conditions'].values())),
                          ('both_conditions_max_Mach_bound',max(x['max_peak_Mach'] for x in r['domain_at_both_conditions'].values()))]:
            maxima[key]=max(maxima[key],value)
    root_rows=[]
    original_rows=[]
    complete=all(s['status']=='continuation_complete_pending_independent_review' for s in summaries)
    for summary in summaries:
        design=summary['design_id']
        for repro in summary.get('K0_reproduction',[]):
            r=runs[repro['record']]
            tag='nominal' if repro['condition']=='nominal' else 'combined_fault'
            old=load(ROOT/'research/pressure_fin/original_freeze/study/runs'/f'{design}_{tag}.json')
            keys=['G_W_K','volume_flow_m3_s','mass_flow_kg_s','max_Re_Dh','pressure_dissipation_W']
            errors={key:abs(r[key]/old[key]-1) for key in keys}
            original_rows.append({'design':design,'condition':tag,'maximum_reproduction_error':max(errors.values()),
                                 'required_base_C':25+60/old['G_W_K'],'original_temperature_pass':25+60/old['G_W_K']<=85,
                                 'K0_reproduction_pass':max(errors.values())<1e-12})
        for case in summary['cases']:
            for mesh_name,root in case['roots'].items():
                if root['status']!='root_bracketed':
                    root_rows.append({'design':design,'K':case['K'],'mesh':mesh_name,'status':root['status']})
                    continue
                main=case['roots']['main']
                r=runs[root['root_record']]
                b=root['fine_bracket']
                lo,hi=(runs[x['file']] for x in b)
                bracket_width=b[1]['P_Pa']-b[0]['P_Pa']
                slope=(hi['capacity_at_uniform_base_85C_W']-lo['capacity_at_uniform_base_85C_W'])/bracket_width
                checks={'bracket_record_identity':all(x['P_Pa']==runs[x['file']]['nominal_pressure_budget_Pa'] and x['capacity_W']==runs[x['file']]['capacity_at_uniform_base_85C_W'] for x in b),
                        'bracket_sign':lo['capacity_at_uniform_base_85C_W']<=60<=hi['capacity_at_uniform_base_85C_W'],
                        'root_contained':b[0]['P_Pa']<=root['root_Pa']<=b[1]['P_Pa'],
                        'root_record_identity':r['nominal_pressure_budget_Pa']==root['root_Pa'],
                        'bracket_width':0<bracket_width<.002,
                        'root_heat_residual':abs(60*r['G_W_K']-60)<.001,
                        'local_positive_slope':slope>0,
                        'nominal_domain':root['domain']['lower_Pa']<=root['root_Pa']<=root['domain']['upper_Pa'],
                        'all_root_gates':all(root['gates'].values())}
                coarse=root['coarse_tolerance_check']
                if coarse is not None:
                    checks['loose_to_fine_tolerance']=abs(coarse['root_Pa']/root['root_Pa']-1)<.0001
                if mesh_name!='main':
                    sensitivity=case[mesh_name+'_sensitivity']
                    at_main=runs[sensitivity['record_at_main_pressure']]
                    main_record=runs[main['root_record']]
                    gdiff=abs(at_main['G_W_K']/main_record['G_W_K']-1)
                    pdiff=abs(root['root_Pa']/main['root_Pa']-1)
                    checks['G_refinement_gate']=gdiff<(.005 if mesh_name=='spatial' else .002)
                    checks['P_refinement_gate']=pdiff<(.01 if mesh_name=='spatial' else .005)
                else:
                    gdiff=pdiff=0.
                root_rows.append({'design':design,'K':case['K'],'mesh':mesh_name,'status':root['status'],
                    'P_Pa':root['root_Pa'],'combined_P_Pa':.6*root['root_Pa'],'bracket_width_Pa':bracket_width,
                    'heat_residual_W':60*r['G_W_K']-60,'sampled_heat_slope_W_per_Pa':slope,
                    'G_refinement_relative':gdiff,'P_refinement_relative':pdiff,'checks':checks})
    checks={'immutable_inputs':all(input_checks.values()),'all_retained_runs':len(fail)==0,
            'original_K0_reproduced':len(original_rows)==4 and all(x['K0_reproduction_pass'] for x in original_rows),
            'original_nominal_pass_combined_fail':all(x['original_temperature_pass']==(x['condition']=='nominal') for x in original_rows),
            'eighteen_bracketed_roots':len(root_rows)==18 and all(r['status']=='root_bracketed' for r in root_rows),
            'root_and_refinement_gates':all(all(r.get('checks',{'incomplete':False}).values()) for r in root_rows),
            'both_studies_complete':complete,
            'all_scenarios_retained':all([c['K'] for c in s['cases']]==[0,1,2] for s in summaries),
            'new_study_files_within_limits':all(p.stat().st_size<100000 for p in STUDY.rglob('*.json'))}
    if complete:
        checks['solve_count_matches_records']=sum(s['new_thermal_solve_count']+s.get('additional_primary_thermal_solve_count',0) for s in summaries)==len(runs)
    limitations=[{'design':s['design_id'],'K':c['K'],'status':c['status'],'error':c.get('error'),
                  'completed_root_meshes':list(c['roots'])} for s in summaries for c in s['cases']
                 if c['status']!='numerically_verified_conditional_root']
    known_bad_root=any(r.get('checks') and not all(r['checks'].values()) for r in root_rows)
    hard_failure=not all(input_checks.values()) or bool(fail) or known_bad_root or any(not r['K0_reproduction_pass'] for r in original_rows)
    result={'status':'passed' if all(checks.values()) else ('failed' if hard_failure else 'incomplete'),
            'checks':checks,'reviewed_run_count':len(runs),'worst_retained_run_diagnostics':maxima,
            'failed_run_checks':fail,'root_reviews':root_rows,'original_screen_reproduction':original_rows,
            'input_hash_checks':input_checks,'completion_limitations':limitations,'review_code_sha256':sha(Path(__file__)),
            'candidate_code_sha256':model_hash,'plan_sha256':sha(STUDY/'plan.json'),
            'new_thermal_marches':0,'scope':'Artifact arithmetic/provenance review; independent thermal reproduction reported separately'}
    continuation_plan=load(STUDY/'continuation/plan.json')
    result['continuation_plan_sha256']=sha(STUDY/'continuation/plan.json')
    result['phase_one_snapshot_hashes_preserved']=all(sha(STUDY/path)==digest for path,digest in continuation_plan['phase_one_input_sha256'].items())
    result['original_repository_checks']= {key:load(STUDY/'phase1_readout/audit.json')['gates'][key] for key in ('tracked_tree_unchanged','checkpoint_unchanged')}
    result['phase_one_primary_count']=180
    result['additional_primary_count']=len(runs)-180
    result['checks']['continuation_primary_budget']=len(runs)-180<=8
    result['checks']['phase_one_snapshot_preserved']=result['phase_one_snapshot_hashes_preserved']
    if not all(result['checks'].values()) and result['status']=='passed': result['status']='failed_or_incomplete'
    encoded=json.dumps(result,indent=2,allow_nan=False)+'\n'
    assert len(encoded.encode())<100000
    Path(__file__).with_suffix('.json').write_text(encoded)
    print(json.dumps({'status':result['status'],'checks':checks,'runs':len(runs),'worst_diagnostics':maxima},indent=2))


if __name__=='__main__':
    main()
