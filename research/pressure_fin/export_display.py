#!/usr/bin/env python3
"""Standard-library lossless expansion of saved hydraulic symmetry classes.
No CFD/thermal solve and no fits. This does not change accepted source records.
"""
from __future__ import annotations
import json,hashlib,pathlib,sys
sys.dont_write_bytecode=True
PACKAGE=pathlib.Path(__file__).resolve().parents[2]

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text())
def write(p,obj):
    s=json.dumps(obj,indent=2,allow_nan=False)+'\n'
    if len(s.encode())>=100000:raise ValueError(f'JSON too large: {p}')
    pathlib.Path(p).parent.mkdir(parents=True,exist_ok=True);pathlib.Path(p).write_text(s)
def export(study,out,verified_records=None,snapshot_root=PACKAGE):
    def load(p):
        return json.loads(verified_records[pathlib.Path(p).relative_to(snapshot_root).as_posix()]) if verified_records is not None else read(p)
    def identity(p):
        return hashlib.sha256(verified_records[pathlib.Path(p).relative_to(snapshot_root).as_posix()]).hexdigest() if verified_records is not None else sha(p)
    study=pathlib.Path(study);out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    d=load(study/'design_results.json');p=load(study/'presweep_plan.json');base=load(study/'runs/n16_t860_nominal.json')
    side_C=base['channels'][0]['hydraulic_conductance_m3_s_Pa'];rho=p['primary_parameters']['air_rho_kg_m3'];nu=p['primary_parameters']['air_nu_m2_s'];H=p['geometry']['fin_height_and_duct_height_m'];B=p['geometry']['base_width_m'];D=p['geometry']['duct_width_m'];L=p['geometry']['length_m'];Tin=p['requirements_synthetic_not_aircraft']['inlet_temperature_C'];Tlim=p['requirements_synthetic_not_aircraft']['maximum_base_temperature_C'];Mlim=p['requirements_synthetic_not_aircraft']['fin_only_mass_budget_kg']*1000
    catalog=[]
    for design in d['designs']:
        ident=design['design_id'];N=design['N_fins'];t=design['thickness_mm']/1000;gap=(B-N*t)/(N-1);cases={}
        for c in design['cases']:
            rawpath=study/'runs'/f"{ident}_{c['case_id']}.json";raw=load(rawpath);blocked=c['blocked_channels'];qside=side_C*c['pressure_Pa'];qinter=(c['volume_flow_m3_s']-2*qside)/(N-1-len(blocked));branches=[]
            for i in range(N+1):
                side=i in (0,N);g=(D-B)/2 if side else gap;q=0. if i in blocked else qside if side else qinter;u=q/(g*H);dh=2*g*H/(g+H)
                branches.append({'index':i,'role':'adiabatic_floor_side_channel' if side else 'heated_floor_interior_channel','gap_m':g,'blocked':i in blocked,'volume_flow_m3_s':q,'mass_flow_kg_s':rho*q,'total_flow_fraction':q/c['volume_flow_m3_s'],'mean_speed_m_s':u,'Re_Dh':u*dh/nu})
            loads=[]
            for q in (40,60,80):
                Tb=Tin+q/c['G_W_K'];tp=Tb<=Tlim;mp=design['fin_only_mass_g']<=Mlim;sc=c['laminar_scope'];num=c['all_numerical_gates_pass'];reason=[]
                if not tp:reason.append('uniform_base_above_synthetic_limit')
                if not mp:reason.append('fin_only_mass_above_synthetic_budget')
                if not sc:reason.append('outside_declared_channel_Reynolds_scope')
                if not num:reason.append('numerical_gate_failure')
                loads.append({'heat_load_W':q,'required_uniform_base_temperature_C':Tb,'thermal_criterion_pass':tp,'fin_only_mass_criterion_pass':mp,'selected_scenario_condition_pass':tp and mp and sc and num,'screen_failure_reasons':reason})
            cases[c['case_id']]={'case_id':c['case_id'],'supply_pressure_drop_Pa':c['pressure_Pa'],'blocked_channel_indices':blocked,'G_W_K':c['G_W_K'],'Rth_K_W':c['Rth_K_W'],'mass_flow_kg_s':c['mass_flow_kg_s'],'volume_flow_m3_s':c['volume_flow_m3_s'],'hydraulic_dissipation_W':c['pressure_dissipation_W'],'max_channel_Re_Dh':c['max_Re_Dh'],'within_declared_Re_scope':c['laminar_scope'],'all_numerical_gates_pass':c['all_numerical_gates_pass'],'raw_mass_temperature_criterion_pass_at_60W':bool(design['mass_limit_pass'] and c['thermal_limit_pass_60W']),'Reynolds_qualified_conditional_pass_at_60W':c['conditional_screen_pass'],'side_channel_flow_fraction':c['side_channel_flow_fraction'],'heat_load_records':loads,'branches':branches,'source_record':{'file':rawpath.relative_to(study).as_posix(),'sha256':identity(rawpath)}}
        rec={'schema':'pressure_fin_display_v1','design_id':ident,'geometry':{'N_fins':N,'N_channels':N+1,'fin_thickness_m':t,'fin_height_m':H,'length_m':L,'base_width_m':B,'duct_width_m':D,'duct_height_m':H,'interior_gap_m':gap,'side_gap_m':(D-B)/2},'fin_only_aluminum_mass_g':design['fin_only_mass_g'],'nominal_reference_design':ident=='n16_t860','fixed_60W_combined_criterion':{'heat_load_W':60,'case_id':'combined_fault','synthetic_base_limit_C':Tlim,'synthetic_fin_only_budget_g':Mlim,'raw_mass_temperature_pass':bool(design['combined_requirement_pass']),'Reynolds_qualified_conditional_pass':cases['combined_fault']['Reynolds_qualified_conditional_pass_at_60W'],'status_is_unchanged_by_display_load_selection':True},'all_cases_within_declared_Re_scope':design['all_cases_within_declared_Re_scope'],'pareto_within_Re_scope':design['pareto_within_Re_scope'],'dominated_by_within_Re_scope':design['dominated_by_scope_candidates'],'dominated_by_all_extrapolations':design['dominated_by_all_extrapolations'],'cases':cases,'provenance':{'presweep_plan_sha256':d['plan_sha256'],'model_code_sha256':d['code_sha256'],'source_design_results_sha256':identity(study/'design_results.json'),'branch_expansion':'exact uniform-interior and invariant-side hydraulic symmetry classes; saved total flow minus two saved side flows gives remaining active interior flow; no fitted parameters'}}
        write(out/'candidates'/f'{ident}.json',rec)
        catalog.append({'design_id':ident,'file':f'candidates/{ident}.json','N_fins':N,'thickness_mm':t*1000,'fin_only_aluminum_mass_g':design['fin_only_mass_g'],'all_cases_within_declared_Re_scope':design['all_cases_within_declared_Re_scope'],'out_of_scope_case_ids':[k for k,r in cases.items() if not r['within_declared_Re_scope']],'pareto_within_Re_scope':design['pareto_within_Re_scope'],'dominated_by_within_Re_scope':design['dominated_by_scope_candidates'],'nominal_Tb_at_60W_C':cases['nominal']['heat_load_records'][1]['required_uniform_base_temperature_C'],'combined_Tb_at_60W_C':cases['combined_fault']['heat_load_records'][1]['required_uniform_base_temperature_C']})
    write(out/'catalog.json',{'schema':'pressure_fin_catalog_v1','default_selection':{'design_id':'n16_t860','case_id':'combined_fault','heat_load_W':60},'count':len(catalog),'candidates':catalog,'summary':load(study/'summary.json')})
    write(out/'out_of_scope_candidates.json',{'scope':'Candidates with at least one case above the declared channel Reynolds cutoff; each case keeps its own scope flag','candidates':[x for x in catalog if not x['all_cases_within_declared_Re_scope']]})
    write(out/'sensitivity_records.json',load(study/'sensitivity_results.json'))
    return catalog
if __name__=='__main__':
    raise SystemExit('Use reproduce.py; it writes fresh ignored output and never replaces accepted examples.')
