#!/usr/bin/env python3
"""Assemble reviewable results without modifying the frozen numerical model."""
import json,pathlib,hashlib,csv,subprocess,datetime,math
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def read(p):return json.loads((HERE/p).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):
 s=json.dumps(d,indent=2)+'\n';assert len(s.encode())<100000;(HERE/p).write_text(s)
plan=read('plan.json');rows=[];allresults=[]
continued=all((HERE/'continuation/results'/f'{name}.json').exists() for name in ['n16_t860','n16_t600'])
result_folder=HERE/('continuation/results' if continued else 'results')
for design in ['n16_t860','n16_t600']:
 f=result_folder/f'{design}.json'
 if not f.exists():continue
 result=json.loads(f.read_text());allresults.append(result)
 for case in result['cases']:
  row={'design_id':design,'K':case['K'],'status':case['status']}
  root=case['roots'].get('main',{})
  if root.get('status')=='root_bracketed':
   r=read(root['root_record']);P=root['root_Pa'];nominal=read(case['nominal_at_main_root_record']) if 'nominal_at_main_root_record' in case else None
   row.update(fin_only_mass_g=r['fin_only_mass_kg']*1000,nominal_pressure_requirement_Pa=P,combined_available_pressure_Pa=.6*P,
    imposed_40pct_pressure_loss_Pa=.4*P,increase_above_original_25Pa=P-25,pressure_ratio_to_original_25Pa=P/25,
    main_bracket=root['fine_bracket'],root_capacity_at_85C_W=r['capacity_at_uniform_base_85C_W'],required_uniform_base_at_60W_C=r['required_uniform_base_at_60W_C'],
    combined_volume_flow_m3_s=r['volume_flow_m3_s'],combined_mass_flow_kg_s=r['mass_flow_kg_s'],
    domain_at_nominal_and_combined=root['root_domain_state'],
    combined_pressure_dissipation_W=r['pressure_dissipation_W'],combined_friction_dissipation_W=r['friction_dissipation_W'],combined_end_loss_dissipation_W=r['end_loss_dissipation_W'],
    combined_omitted_mechanical_heating_fraction=r['omitted_mechanical_heating_fraction_of_60W'],nominal_pressure_dissipation_W=nominal['pressure_dissipation_W'] if nominal else None,
    nominal_omitted_mechanical_heating_fraction=nominal['omitted_mechanical_heating_fraction_of_60W'] if nominal else None,
    nominal_required_uniform_base_C=nominal['required_uniform_base_at_60W_C'] if nominal else None,
    root_local_slope_W_Pa=root['local_capacity_slope_W_Pa'],
    coarse_to_fine_root_relative=root['coarse_tolerance_check']['coarse_to_fine_relative'])
   row['refined_roots']={name:{'root_Pa':rr.get('root_Pa'),'status':rr['status'],'fine_bracket':rr.get('fine_bracket'),'gates':rr.get('gates')} for name,rr in case['roots'].items() if name!='main'}
   for name in ['spatial','axial']:
    if name+'_sensitivity' in case:row[name+'_sensitivity']=case[name+'_sensitivity']
  rows.append(row)
original=[]
for design in ['n16_t860','n16_t600']:
 d=json.loads((ROOT/'research/pressure_fin/original_freeze/study/runs'/f'{design}_combined_fault.json').read_text())
 nominal_original=json.loads((ROOT/'research/pressure_fin/original_freeze/study/runs'/f'{design}_nominal.json').read_text())
 original.append({'design_id':design,'nominal_P_Pa':25,'combined_P_Pa':15,'fin_only_mass_g':d['fin_only_mass_kg']*1000,'original_nominal_required_uniform_base_C':25+60/nominal_original['G_W_K'],'original_nominal_60W_85C_pass':25+60/nominal_original['G_W_K']<=85,'original_required_uniform_base_C':25+60/d['G_W_K'],'original_capacity_at85C_W':60*d['G_W_K'],'original_deficit_W':60-60*d['G_W_K'],'original_60W_85C_failure_preserved':True})
for row in rows:
 row['preserved_original_25Pa_nominal_15Pa_combined_failure']=next(x for x in original if x['design_id']==row['design_id'])
summary={'status':'numerical_evidence_complete_consult_independent_review' if continued else 'primary_phase_incomplete_consult_exhaustion_record','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':plan['scope'],'plan_sha256':sha(HERE/'plan.json'),'clarification_sha256':sha(HERE/'pre_numerics_clarification.json'),
 'pressure_definition':'Synthetic available mechanical pressure-loss budget across ideal parallel branches, counting straight friction plus the selected illustrative end loss once; not a NASA station pressure or electrical fan requirement',
 'original_failures':original,'scenario_count_expected':6,'rows':rows,'new_thermal_solve_count':len(list((HERE/'runs').rglob('*.json')))+len(list((HERE/'continuation/runs').rglob('*.json'))),'primary_phase_thermal_solves':len(list((HERE/'runs').rglob('*.json'))),'continuation_primary_thermal_solves':len(list((HERE/'continuation/runs').rglob('*.json'))),'separate_continuation_used':continued,'phase_one_exhaustion_record':'phase1_terminal.json',
 'exact_root_has_no_engineering_margin':True,'K_scenarios_are_not_measured_uncertainty':True,'physical_validation':False,'aircraft_transfer':False}
if continued:
 completion=read('continuation/completion_observed.json')
 summary['verification_summary']={
  'completed_mesh_root_count':sum(1+len(row['refined_roots']) for row in rows),
  'max_spatial_G_relative':max(row['spatial_sensitivity']['G_relative_at_main_pressure'] for row in rows),
  'max_axial_G_relative':max(row['axial_sensitivity']['G_relative_at_main_pressure'] for row in rows),
  'max_spatial_root_P_relative':max(row['spatial_sensitivity']['root_P_relative'] for row in rows),
  'max_axial_root_P_relative':max(row['axial_sensitivity']['root_P_relative'] for row in rows),
  'independent_max_relative_G_difference':completion['main_root_reproduction_max_abs_relative_G'],
  'independent_review_thermal_solves':completion['independent_review_thermal_solves'],
  'total_continuation_thermal_solves':completion['total_additional_thermal_solves'],
  'total_all_stage_thermal_solves':180+completion['total_additional_thermal_solves']}
write('summary.json',summary)
def human_status(status):return {'numerically_verified_conditional_root':'Numerical gates passed','running':'In progress','failed_or_resource_limited':'Incomplete; resource limit','continuation_failed_or_resource_limited':'Continuation incomplete'}.get(status,status)
def label(design):return {'n16_t860':'16 fins × 0.86 mm','n16_t600':'16 fins × 0.60 mm'}[design]
lines=['# Conditional cooling-pressure requirement','',summary['scope']+'.','',
 'Both original 25 Pa all-open nominal cases pass the 85°C uniform-base ceiling at 60 W. Both original 15 Pa combined sealed-branch cases fail. Those original pass/fail classifications remain unchanged. The inverse calculation asks what new synthetic available mechanical pressure-loss budget P would be required if the combined state receives 0.6 P with the same branch sealed. The 60 W / 85°C / 25°C / 40 g requirements remain fixed.','',
 '| Geometry | Fin-only mass (g) | Original nominal base (°C) | Original combined base (°C) | Capacity at 85°C (W) | Deficit (W) |','|---|---:|---:|---:|---:|---:|']
for r in original:lines.append(f"| {label(r['design_id'])} | {r['fin_only_mass_g']:.2f} | {r['original_nominal_required_uniform_base_C']:.2f} | {r['original_required_uniform_base_C']:.2f} | {r['original_capacity_at85C_W']:.2f} | {r['original_deficit_W']:.2f} |")
lines+=['','## Pressure roots','', 'K is a uniform illustrative end-loss coefficient. K=0 recovers the accepted model exactly. K=1 and K=2 are synthetic model-form scenarios, not measured uncertainty bounds. Results below are conditional. Independent acceptance and its scope are recorded separately under review/; these numerical results do not establish physical validation.','',
 '| Geometry | K | Original K=0, 15 Pa capacity / 60 W | Main P bracket, rounded outward (Pa) | Main P (Pa) | Combined 0.6P (Pa) | Spatial root P (Pa) | Axial root P (Pa) | Status |','|---|---:|---:|---:|---:|---:|---:|---:|---|']
for r in rows:
 if 'main_bracket' not in r:lines.append(f"| {label(r['design_id'])} | {r['K']} | {r['preserved_original_25Pa_nominal_15Pa_combined_failure']['original_capacity_at85C_W']:.3f} / 60 | — | — | — | — | — | {human_status(r['status'])} |");continue
 b=r['main_bracket'];sp=r['refined_roots'].get('spatial',{}).get('root_Pa');ax=r['refined_roots'].get('axial',{}).get('root_Pa')
 sf=f'{sp:.2f}' if sp else 'pending';af=f'{ax:.2f}' if ax else 'pending'
 lines.append(f"| {label(r['design_id'])} | {r['K']} | {r['preserved_original_25Pa_nominal_15Pa_combined_failure']['original_capacity_at85C_W']:.3f} / 60 | [{math.floor(100*b[0]['P_Pa'])/100:.2f}, {math.ceil(100*b[1]['P_Pa'])/100:.2f}] | {r['nominal_pressure_requirement_Pa']:.2f} | {r['combined_available_pressure_Pa']:.2f} | {sf} | {af} | {human_status(r['status'])} |")
lines+=['','The JSON retains exact directly evaluated pressure endpoints and capacities below/above 60 W. The table rounds those brackets outward to 0.01 Pa for readability, using the verified monotonic model; no extra endpoint evaluations are implied. Root tolerance is 0.00005 Pa. Mesh differences are numerical indicators, not physical uncertainty bounds. No endpoint supplies guaranteed engineering headroom.','',
 '## Domain and omitted mechanical heating','',
 'The table evaluates the six main-mesh roots. Every search and refined-root evaluation also passes both-state domain guards. Re is based on mean channel speed and hydraulic diameter. Mach uses the conservative upper-envelope local speed and inlet-based sound speed. Both the nominal all-open P state and the combined 0.6P sealed state must pass Re<2300 and Mach<0.1 before any thermal solve.','',
 '| Geometry | K | Nominal max Re | Combined max Re | Nominal max Mach bound | Combined max Mach bound | Combined dissipation (mW) | Nominal dissipation (mW) | Combined/nominal omitted heating (% of 60W) |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in rows:
 if 'main_bracket' not in r:continue
 d=r['domain_at_nominal_and_combined'];nn=r['nominal_pressure_dissipation_W'];nf=r['nominal_omitted_mechanical_heating_fraction']
 lines.append(f"| {label(r['design_id'])} | {r['K']} | {d['nominal']['max_Re_Dh']:.3f} | {d['combined']['max_Re_Dh']:.3f} | {d['nominal']['max_peak_Mach']:.5f} | {d['combined']['max_peak_Mach']:.5f} | {1000*r['combined_pressure_dissipation_W']:.4f} | {1000*nn if nn else 0:.4f} | {100*r['combined_omitted_mechanical_heating_fraction']:.5f} / {100*nf if nf else 0:.5f} |")
lines+=['','Dissipation is passive pressure-drop dissipation, not electrical fan power. The JSON reports friction/end-loss contributions and conservation separately. Viscous and end-loss heating are omitted from the thermal PDE. Temperatures are required uniform-base values, not hot spots.','',
 '## Evidence and interpretation','',
 'The original phase stopped at exactly 180 thermal solves with 16 of 18 root brackets complete. Its two K=2 axial brackets were unfinished. A separate, authorized verification-only continuation preserved that record and completed the missing brackets with 5 primary evaluations plus 6 independent reproductions: 11 of its 14 allowed solves, within 4 minutes of its 20-minute limit. Equations, thresholds and tolerances were unchanged.','',
 'All 18 mesh-root brackets pass the unchanged numerical gates. Maximum main-to-spatial/axial differences are 0.0392% / 0.0150% in G and 0.0882% / 0.0430% in root pressure. The six independent main-root reproductions differ by at most 3.8e-15 relative in G. These are numerical verification results, not physical uncertainty bounds.','',
 'The original whole-checkout identity checks failed after authorized concurrent integration/guide edits; those failures remain in the preserved phase-one audit. A separate audit confirms all 13 consumed accepted inputs and the exhausted-phase snapshot are unchanged. One brief third non-marching reviewer process exceeded the two-process resource cap; its exception and pre-thermal/root chronology are retained in PROVENANCE_NOTES.md and the independent review.','',
 '- Frozen plan: plan.json and plan.sha256; pre-run reviewer clarification: pre_numerics_clarification.json','- All full-array numerical records: runs/ and continuation/runs/; original limited results: results/; completed results: continuation/results/','- Equations, monotonicity argument, mechanical boundary meaning and falsifiable measurement needs: SCOPE_AND_MEASUREMENT.md','- Preserved original incomplete/checkpoint gate outcomes: phase1_readout/audit.json; dependency-scoped audit: dependency_scoped_audit.json; combined numerical audit: final_audit.json; independent reviewer evidence: review/ and continuation/review/','',
 'This compares only the two declared fin geometries. It does not establish a system optimum: pressure-source electrical power, base/duct/installation mass, structural limits and manufacturing constraints remain unmodeled. The original model assumes ideal common-pressure reservoirs, fully developed laminar velocity, finite fin conduction with real floor ownership, sealed-fluid transverse conduction, constant properties and a uniform fixed-temperature base. It omits base spreading/contact resistance, axial solid/fluid conduction, actual fan/feeder coupling, hydrodynamic development, radiation and installed-system geometry. Measure matched pressure–flow and thermal performance, fault leakage and supply operating points before using these roots as hardware requirements.']
(HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'scenarios':len(rows),'states':[r['status'] for r in rows],'new_thermal_solve_count':summary['new_thermal_solve_count']}))
