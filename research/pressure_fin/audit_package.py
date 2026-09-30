#!/usr/bin/env python3
"""Standard-library integrity, source-to-display and independent arithmetic audit.
This deliberately does not import NumPy/SciPy or rerun the thermal PDE.
"""
from __future__ import annotations
import hashlib,json,math,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[2]
RP='research/pressure_fin/'; EP='examples/pressure_fin_tradeoff/'; MP=EP+'package_manifest.json'
SCI=ROOT/RP; STUDY=SCI/'original_freeze/study'; EXAMPLES=ROOT/EP
def read(p):return json.loads(pathlib.Path(p).read_text())
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def near(a,b,rtol=1e-11,atol=1e-13):return abs(a-b)<=atol+rtol*max(abs(a),abs(b))
def poisson_mean(w,h):
    a,b=sorted((w,h));return a*a/12*(1-192*a/(math.pi**5*b)*math.fsum(math.tanh(n*math.pi*b/(2*a))/n**5 for n in range(1,4000,2)))
def deficit_dn(length,alpha_z_u):return math.fsum(8/(math.pi*n)**2*math.exp(-alpha_z_u*(n*math.pi/(2*length))**2) for n in range(1,10000,2))
def strict_json(raw):
    if len(raw)>=100000:raise ValueError('JSON exceeds bounded contract')
    def reject(value):raise ValueError('Nonfinite JSON: '+value)
    result=json.loads(raw,parse_constant=reject)
    def walk(x):
        if isinstance(x,float) and not math.isfinite(x):raise ValueError('Nonfinite numeric JSON')
        if isinstance(x,dict):
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(result);return result
def bounded_read(p,limit,expected=None):
    n=p.stat().st_size
    if n>=limit or (expected is not None and n!=expected):raise ValueError('Artifact fails size preflight: '+str(p))
    with p.open('rb') as f:raw=f.read(limit)
    if len(raw)!=n or len(raw)>=limit:raise ValueError('Artifact changed size or exceeds bound')
    return raw
def audit(root=ROOT,expected_manifest_sha256=None,return_verified_records=False):
    root=pathlib.Path(root); sci=root/'research/pressure_fin';study=sci/'original_freeze/study';examples=root/'examples/pressure_fin_tradeoff';checks={};failures=[]
    def check(name,value):
        value=bool(value);checks[name]=value
        if not value:failures.append(name)
    root=root.resolve();sci=root/RP;study=sci/'original_freeze/study';examples=root/EP
    manifest_path=root/MP
    if not manifest_path.is_file() or manifest_path.is_symlink() or not manifest_path.resolve().is_relative_to(root):raise ValueError('Invalid manifest location')
    manifest_raw=bounded_read(manifest_path,100000);manifest_sha=hashlib.sha256(manifest_raw).hexdigest()
    if expected_manifest_sha256 and manifest_sha!=expected_manifest_sha256:raise ValueError('Manifest identity differs from pinned hash')
    manifest=strict_json(manifest_raw);files=manifest['files'];records={};bad=[]
    for e in files:
        name=e['path'];rel=pathlib.PurePosixPath(name)
        if name!=e['proposed_repository_path'] or rel.is_absolute() or '..' in rel.parts or name in records or not name.startswith((RP,EP)):raise ValueError('Invalid or duplicate manifest path')
        p=root/name
        if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Missing or escaping artifact: '+name)
        if '__pycache__' in rel.parts or p.suffix.lower() in ('.pyc','.log','.npz','.npy','.pdf'):raise ValueError('Forbidden publication artifact')
        if not isinstance(e['bytes'],int) or isinstance(e['bytes'],bool) or e['bytes']<0:raise ValueError('Invalid artifact byte count')
        raw=bounded_read(p,100000 if p.suffix=='.json' else 250000,e['bytes'])
        if hashlib.sha256(raw).hexdigest()!=e['sha256']:raise ValueError('Artifact hash mismatch: '+name)
        if p.suffix=='.json':strict_json(raw)
        records[name]=raw
    def read(path):return strict_json(records[pathlib.Path(path).relative_to(root).as_posix()])
    def sha(path):return hashlib.sha256(records[pathlib.Path(path).relative_to(root).as_posix()]).hexdigest()
    check('manifest_hashes_and_sizes',len(records)==manifest['files_count'] and sum(map(len,records.values()))==manifest['total_listed_bytes'])
    unexpected=[];forbidden=[];large=[]
    for tree in (sci,examples):
        for p in tree.rglob('*'):
            rel=p.relative_to(root)
            if p.is_file():
                if rel.as_posix() not in records and rel.as_posix()!=MP:unexpected.append(rel.as_posix())
                if '__pycache__' in rel.parts or p.suffix.lower() in ('.pyc','.log','.npz','.pdf'):forbidden.append(rel.as_posix())
                if p.suffix=='.json' and p.stat().st_size>=100000:large.append(rel.as_posix())
    check('no_unlisted_payload_files',not unexpected);check('no_caches_logs_npz_or_pdf',not forbidden);check('bounded_file_sizes',not large)
    provenance=read(sci/'freeze_provenance.json')
    check('every_frozen_scientific_byte_preserved',all(len(records[(sci/e['archive']).relative_to(root).as_posix()])==e['bytes'] and sha(sci/e['archive'])==e['sha256'] for e in provenance['copied']))
    plan=read(study/'presweep_plan.json');v=read(study/'verification.json');d=read(study/'design_results.json');s=read(study/'sensitivity_results.json');summary=read(study/'summary.json');review=read(study/'review/final_review_gate.json');cat=read(examples/'catalog.json')
    check('model_and_plan_identity',v['plan_sha256']==sha(study/'presweep_plan.json')==d['plan_sha256']==s['plan_sha256'] and v['code_sha256']==sha(study/'pressure_fin.py')==d['code_sha256']==s['code_sha256'])
    check('original_solver_identity',sha(sci/'original_freeze/fin-study/conjugate_fin.py')==v['original_model_sha256']=='bdf9998a7f20cdd5d75fef2f5f0e49c9344ebc1e6f31a5ac955bff366d6c9d4c')
    check('independent_final_review_matches_records',all(review['checks'].values()) and review['design_results_sha256']==sha(study/'design_results.json') and review['sensitivity_results_sha256']==sha(study/'sensitivity_results.json') and review['summary_sha256']==sha(study/'summary.json'))
    check('all_nineteen_declared_math_gates',len(v['gates'])==19 and all(v['gates'].values()))
    check('nine_geometries_36_cases_18_sensitivities',len(d['designs'])==9 and sum(len(x['cases']) for x in d['designs'])==36 and len(s['rows'])==18 and len(cat['candidates'])==9)
    params=plan['primary_parameters']; rho=params['air_rho_kg_m3'];nu=params['air_nu_m2_s'];cp=params['air_cp_J_kg_K'];ka=params['air_k_W_m_K'];mu=rho*nu; req=plan['requirements_synthetic_not_aircraft']; Tin=req['inlet_temperature_C'];Tlim=req['maximum_base_temperature_C'];Mlim=req['fin_only_mass_budget_kg']*1000
    all_records={};channel_errors=[];raw_good=[];mass_good=[];temp_good=[];scope_good=[];fixed_good=[];flow_good=[];branch_good=[];criterion_good=[]
    for design in d['designs']:
        ident=design['design_id'];rec=read(examples/'candidates'/f'{ident}.json');all_records[ident]=rec;g=rec['geometry'];N=g['N_fins'];mass=2700*N*g['fin_thickness_m']*g['fin_height_m']*g['length_m']*1000
        mass_good.append(near(mass,rec['fin_only_aluminum_mass_g']) and near(mass,design['fin_only_mass_g']) and near(N*g['fin_thickness_m']+(N-1)*g['interior_gap_m']+2*g['side_gap_m'],g['duct_width_m']))
        dc={c['case_id']:c for c in design['cases']}
        fixed=rec['fixed_60W_combined_criterion'];fixed_good.append(fixed['heat_load_W']==60 and fixed['case_id']=='combined_fault' and fixed['status_is_unchanged_by_display_load_selection'] is True and fixed['raw_mass_temperature_pass']==design['combined_requirement_pass'] and fixed['Reynolds_qualified_conditional_pass']==dc['combined_fault']['conditional_screen_pass'])
        for cid,c in rec['cases'].items():
            source=study/'runs'/f'{ident}_{cid}.json';raw=read(source);raw_good.append(c['source_record']['sha256']==sha(source) and near(c['G_W_K'],raw['G_W_K']) and all(raw['gates'].values()) and raw['energy_relative_balance_max']<1e-8 and raw['componentwise_thermal_equation_residual_relative']<1e-8 and raw['mass_transport_closure_relative']<1e-12 and raw['max_poisson_relative_residual']<1e-9 and raw['max_poisson_force_balance_relative']<1e-9 and raw['max_hydraulic_flow_exact_relative_error']<.002)
            branches=c['branches'];flow_good.append(len(branches)==N+1 and near(sum(b['volume_flow_m3_s'] for b in branches),c['volume_flow_m3_s']) and near(sum(b['mass_flow_kg_s'] for b in branches),c['mass_flow_kg_s']) and near(sum(b['total_flow_fraction'] for b in branches),1) and near(c['hydraulic_dissipation_W'],c['supply_pressure_drop_Pa']*c['volume_flow_m3_s']))
            branch_good.append(c['blocked_channel_indices']==([] if cid in ('nominal','pressure_loss') else [1]))
            for b in branches:
                blocked=b['index'] in c['blocked_channel_indices'];branch_good.append(b['blocked']==blocked and (b['volume_flow_m3_s']==0 if blocked else b['volume_flow_m3_s']>0) and near(b['mass_flow_kg_s'],rho*b['volume_flow_m3_s']))
                if not blocked:
                    exact=c['supply_pressure_drop_Pa']*poisson_mean(b['gap_m'],g['fin_height_m'])/(mu*g['length_m'])*b['gap_m']*g['fin_height_m'];channel_errors.append(abs(b['volume_flow_m3_s']/exact-1))
            remax=max(b['Re_Dh'] for b in branches);scope_good.append(near(remax,c['max_channel_Re_Dh']) and c['within_declared_Re_scope']==(remax<2300)==dc[cid]['laminar_scope'])
            for load in c['heat_load_records']:
                q=load['heat_load_W'];Tb=Tin+q/c['G_W_K'];expected=Tb<=Tlim and mass<=Mlim and remax<2300 and c['all_numerical_gates_pass'];temp_good.append(q in (40,60,80) and near(Tb,load['required_uniform_base_temperature_C']));criterion_good.append(load['selected_scenario_condition_pass']==expected and load['thermal_criterion_pass']==(Tb<=Tlim) and load['fin_only_mass_criterion_pass']==(mass<=Mlim))
            expected60=(Tin+60/c['G_W_K']<=Tlim and mass<=Mlim);criterion_good.append(c['raw_mass_temperature_criterion_pass_at_60W']==expected60 and c['Reynolds_qualified_conditional_pass_at_60W']==(expected60 and remax<2300 and c['all_numerical_gates_pass']))
        for a,b in [('nominal','asymmetric_blockage'),('pressure_loss','combined_fault')]:
            aa=rec['cases'][a];bb=rec['cases'][b]
            for ba,bbch in zip(aa['branches'],bb['branches']):
                if not bbch['blocked']:flow_good.append(near(ba['volume_flow_m3_s'],bbch['volume_flow_m3_s'],atol=1e-16))
            flow_good.append(near(aa['volume_flow_m3_s']-bb['volume_flow_m3_s'],aa['branches'][1]['volume_flow_m3_s'],atol=1e-16))
        for bn,bc in zip(rec['cases']['nominal']['branches'],rec['cases']['combined_fault']['branches']):
            if not bc['blocked']:flow_good.append(near(bc['volume_flow_m3_s'],.6*bn['volume_flow_m3_s'],atol=1e-16))
    check('fin_only_mass_and_geometry',all(mass_good));check('source_to_display_and_saved_numeric_residuals',all(raw_good));check('every_heat_load_temperature_is_linear_arithmetic',all(temp_good));check('all_case_Regime_flags_retained',all(scope_good));check('fixed_60W_combined_criterion_cannot_change_with_display_load',all(fixed_good));check('raw_criteria_distinct_from_conditional_flags',all(criterion_good));check('sealed_indices_zero_flow_and_exact_branch_counts',all(branch_good));check('branch_network_and_pressure_reduction_identities',all(flow_good));check('independent_rectangular_series_all_branches',max(channel_errors)<.002)
    def dom(a,pool):
        am=a['fin_only_mass_g'];at=next(c['Tb_at_60W_C'] for c in a['cases'] if c['case_id']=='combined_fault');out=[]
        for b in pool:
            bm=b['fin_only_mass_g'];bt=next(c['Tb_at_60W_C'] for c in b['cases'] if c['case_id']=='combined_fault')
            if a['design_id']!=b['design_id'] and bm<=am and bt<=at and (bm<am or bt<at):out.append(b['design_id'])
        return sorted(out)
    qualified=[x for x in d['designs'] if all(c['laminar_scope'] for c in x['cases'])];dominance=True
    for design in d['designs']:
        rec=all_records[design['design_id']];expected=dom(design,qualified) if design in qualified else None;dominance &= (sorted(rec['dominated_by_within_Re_scope']) if rec['dominated_by_within_Re_scope'] is not None else None)==expected and sorted(rec['dominated_by_all_extrapolations'])==dom(design,d['designs']) and rec['pareto_within_Re_scope']==(design in qualified and not expected)
    check('scoped_and_unrestricted_dominance_recomputed',dominance)
    retained=read(examples/'out_of_scope_candidates.json')['candidates'];check('out_of_scope_points_separate_and_retained',sorted(x['design_id'] for x in retained)==['n12_t600','n12_t860'] and all(x['design_id'] in all_records for x in retained))
    check('zero_combined_passes_preserved',not any(r['fixed_60W_combined_criterion']['Reynolds_qualified_conditional_pass'] for r in all_records.values()) and summary['combined_conditional_screen_pass_design_ids']==[])
    grid=[]
    for name in ['baseline_nominal','baseline_combined','wide_nominal','dense_combined']:
        coarse=read(study/'verification_runs'/f'{name}_48_800.json');fine=read(study/'verification_runs'/f'{name}_64_800.json');ax=read(study/'verification_runs'/f'{name}_48_1600.json');decl=next(x for x in v['grid_comparisons'] if x['probe']==name);sp=abs(coarse['G_W_K']/fine['G_W_K']-1);az=abs(coarse['G_W_K']/ax['G_W_K']-1);grid.append(sp<.005 and az<.002 and near(sp,decl['spatial_G_relative']) and near(az,decl['axial_G_relative']))
    check('four_declared_mesh_probe_comparisons_recomputed',all(grid))
    analytical=[]
    for r in v['analytic_plug_rows']:
        rec=all_records[f"n{r['N']}_t{round(r['t_mm']*1000)}"];g=rec['geometry'];exact=0.
        for b in rec['cases']['nominal']['branches']:
            az=ka/(rho*cp)*g['length_m']/b['mean_speed_m_s'];deficit=deficit_dn(b['gap_m'],az) if b['role'].startswith('adiabatic') else deficit_dn(b['gap_m']/2,az)*deficit_dn(g['fin_height_m'],az);exact+=rho*cp*b['volume_flow_m3_s']*(1-deficit)
        analytical.append(near(exact,r['analytic_W_K']) and abs(r['numerical_W_K']/exact-1)<.005)
    check('independent_isothermal_plug_series_recomputed',all(analytical))
    check('18_sensitivities_remain_separate_and_pass_numerically',read(examples/'sensitivity_records.json')==s and all(all(r['gates'].values()) for r in s['rows']))
    result={'status':'passed' if all(checks.values()) else 'failed','audit_scope':'Standard-library integrity, source-to-display, network identities, dominance, and independent analytical arithmetic; does not rerun the thermal PDE or establish aircraft validation','checks':checks,'failures':failures,'manifest_mismatches':bad,'unexpected_files':unexpected,'forbidden_files':forbidden,'oversize_files':large,'maximum_rectangular_flow_relative_error':max(channel_errors),'fixed_design_heat_load_W':60,'combined_conditional_pass_count':0,'source_checkpoint':'14d72777b434d025c87f560b9e3e9c24fd786865','manifest_sha256':manifest_sha,'listed_file_count':len(records),'listed_bytes':sum(map(len,records.values())),'physical_validation_pass':None,'aircraft_transfer_authorized':False}
    if return_verified_records and result['status']!='passed':raise ValueError('Evidence audit failed: '+', '.join(failures))
    return (result,records,manifest_sha) if return_verified_records else result
if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=pathlib.Path,default=ROOT);ap.add_argument('--expected-manifest-sha256');args=ap.parse_args()
    result=audit(args.root,args.expected_manifest_sha256);print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='passed' else 1)
