#!/usr/bin/env python3
"""Read-only aggregate audit, with outputs confined to this ignored study."""
import json,pathlib,hashlib,subprocess,datetime,math
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((HERE/p).read_text())
plan=read('plan.json');summary=read('summary.json');results=[read(pathlib.Path('results')/(d['id']+'.json')) for d in plan['only_geometries']]
files=sorted(p for p in HERE.rglob('*') if p.is_file() and not p.name.endswith('.tmp'))
jsons=[p for p in files if p.suffix=='.json'];runs=[(p,json.loads(p.read_text())) for p in sorted((HERE/'runs').rglob('*.json'))]
input_checks={name:sha(ROOT/name)==value for name,value in plan['input_sha256'].items()}
source_code_hash=sha(HERE/'pressure_requirement.py');plan_hash=sha(HERE/'plan.json')
run_checks=[]
for p,r in runs:
 ds=r['domain_at_both_conditions'];rr=r['channels'];sealed=[x for x in rr if x['blocked']]
 d={
  'file':str(p.relative_to(HERE)),'all_declared_numerical_gates':all(r['gates'].values()),
  'pressure_inside_declared_absolute_interval':25<=r['nominal_pressure_budget_Pa']<=200,
  'both_condition_domain':all(s['within_domain'] and s['max_Re_Dh']<2300 and s['max_peak_Mach']<.1 for s in ds.values()),
  'mechanical_pressure_once':abs(sum(x['friction_dissipation_W']+x['end_loss_dissipation_W'] for x in rr)/r['pressure_dissipation_W']-1)<1e-12,
  'sealed_zero_advection':all(x['volume_flow_m3_s']==0 and x['mass_flow_kg_s']==0 and x['heat_transport_W_K']==0 for x in sealed),
  'exactly_declared_sealed_branch':r['blocked_channels']==([1] if r['condition']=='combined' else []),
  'temperature_is_uniform_base':abs(r['required_uniform_base_at_60W_C']-(25+60/r['G_W_K']))<1e-12,
  'pressure_fraction':abs(r['pressure_Pa']/r['nominal_pressure_budget_Pa']-(.6 if r['condition']=='combined' else 1))<1e-15,
  'source_hash':r['model_sha256']==source_code_hash and r['accepted_operator_sha256']==plan['input_sha256']['research/pressure_fin/original_freeze/study/pressure_fin.py'],
  'frozen_plan_hash':r['plan_sha256']==plan_hash,
 }
 run_checks.append(d)
root_checks=[]
for result in results:
 for case in result['cases']:
  for mesh,root in case['roots'].items():
   checks={'design_id':result['design_id'],'K':case['K'],'mesh':mesh,'root_bracketed':root['status']=='root_bracketed'}
   if root['status']=='root_bracketed':
    b=root['fine_bracket'];lr=[read(x['file']) for x in b];P=root['root_Pa'];r=read(root['root_record'])
    checks.update(all_declared_root_gates=all(root['gates'].values()),signs=lr[0]['capacity_at_uniform_base_85C_W']<=60<=lr[1]['capacity_at_uniform_base_85C_W'],
                  root_inside_bracket=b[0]['P_Pa']<=P<=b[1]['P_Pa'],bracket_width=b[1]['P_Pa']-b[0]['P_Pa']<.002,
                  residual=abs(r['capacity_at_uniform_base_85C_W']-60)<.001,
                  all_root_domain=all(s['within_domain'] for s in root['root_domain_state'].values()))
   root_checks.append(checks)
monotonic=[]
for result in results:
 pairs=[(c['K'],c.get('roots',{}).get('main',{}).get('root_Pa')) for c in result['cases']]
 monotonic.append({'design_id':result['design_id'],'roots':pairs,'K_increases_required_budget':len(pairs)==3 and all(p[1] is not None for p in pairs) and all(pairs[j][1]<pairs[j+1][1] for j in range(2))})
maxima={k:max(r[k] for p,r in runs) for k in ['energy_relative_balance_max','componentwise_thermal_equation_residual_relative','mass_transport_closure_relative','pressure_closure_relative','max_poisson_relative_residual','max_poisson_force_balance_relative','max_hydraulic_flow_exact_relative_error','dissipation_split_relative_error']}
worst_omitted=max(r['omitted_mechanical_heating_fraction_of_60W'] for p,r in runs)
def flags_pass(d):return all(v for k,v in d.items() if isinstance(v,bool))
tracked_clean=subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode==0
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
gates={
 'six_scenarios_retained':sum(len(r['cases']) for r in results)==6,
 'all_scenarios_complete':all(c['status']=='numerically_verified_conditional_root' for r in results for c in r['cases']),
 '18_mesh_roots':len(root_checks)==18,
 'every_root_checked':all(flags_pass(c) for c in root_checks),
 'all_saved_thermal_runs_pass':all(flags_pass(c) for c in run_checks),
 'original_K0_reproduced':all(c['pass'] for r in results for c in r['K0_reproduction']),
 'original_failures_preserved':all(r['original_60W_85C_failure_preserved'] and r['original_deficit_W']>0 for r in summary['original_failures']),
 'all_input_hashes_unchanged':all(input_checks.values()),'tracked_tree_unchanged':tracked_clean,'checkpoint_unchanged':head==plan['checkpoint'],
 'plan_hash_unchanged':plan_hash==(HERE/'plan.sha256').read_text().split()[0],
 'clarification_hash_unchanged':sha(HERE/'pre_numerics_clarification.json')==(HERE/'pre_numerics_clarification.sha256').read_text().split()[0],
 'K_requires_more_pressure':all(x['K_increases_required_budget'] for x in monotonic),
 'all_JSON_below_100KB':all(p.stat().st_size<100000 for p in jsons),
 'all_binary_below_250KB':all(p.stat().st_size<250000 for p in files if p.suffix in ['.pyc','.png','.pdf','.npz','.npy']),
 'primary_thermal_solve_count_within_budget':len(runs)<=180,
}
out={'status':'passed_pending_independent_review' if all(gates.values()) else 'failed_or_incomplete','gates':gates,'input_checks':input_checks,'thermal_run_count':len(runs),'root_count':len(root_checks),'root_checks':root_checks,'K_monotonicity':monotonic,'maximum_numerical_residuals':maxima,'maximum_omitted_heating_fraction_all_search_records':worst_omitted,'max_JSON_bytes':max(p.stat().st_size for p in jsons),'max_binary_bytes':max([p.stat().st_size for p in files if p.suffix in ['.pyc','.png','.pdf','.npz','.npy']]+[0]),'plan_sha256':plan_hash,'model_sha256':source_code_hash,'physical_validation':False,'aircraft_transfer':False,'chronology_clarification':'Pre-numerics clarification preceded primary thermal solves and inverse roots; independent raw Poisson/scalar hydraulic checks had already run after original plan freeze. Frozen bytes retained; see PROVENANCE_NOTES.md.'}
resource_file=HERE/'review/independent/execution_notes.json'
if resource_file.exists():
 out['independent_execution_resource_ledger']=json.loads(resource_file.read_text())
 out['parallel_resource_cap_observed']=not bool(out['independent_execution_resource_ledger'].get('resource_exceptions',[]))
 if all(gates.values()) and not out['parallel_resource_cap_observed']:
  out['status']='passed_numerics_with_documented_resource_deviation_pending_independent_review'
s=json.dumps(out,indent=2)+'\n';assert len(s.encode())<100000;(HERE/'audit.json').write_text(s)
# Split per-run audit records to stay well below 100KB.
for i in range(0,len(run_checks),50):
 p=HERE/'audit'/f'run_checks_{i//50:02d}.json';p.parent.mkdir(exist_ok=True);s=json.dumps(run_checks[i:i+50],indent=2)+'\n';assert len(s.encode())<100000;p.write_text(s)
print(json.dumps({'status':out['status'],'gates':gates,'thermal_run_count':len(runs),'root_count':len(root_checks)}))

raise SystemExit(0 if all(gates.values()) else 1)
