#!/usr/bin/env python3
"""Cross-check saved results, provenance, file limits and physical orderings."""
from pressure_fin import *
def main():
    data=json.loads((HERE/'design_results.json').read_text());sens=json.loads((HERE/'sensitivity_results.json').read_text());ver=json.loads((HERE/'verification.json').read_text());manifest=json.loads((HERE/'manifest.json').read_text());summary=json.loads((HERE/'summary.json').read_text());issues=[]
    for e in manifest['artifacts']:
        p=HERE/e['file']
        if not p.exists() or digest(p)!=e['sha256'] or p.stat().st_size!=e['bytes']:issues.append(e['file'])
    mass_errors=[];orders=[];retained=[]
    for d in data['designs']:
        mass=2700*d['N_fins']*d['thickness_mm']/1000*H*L*1000;mass_errors.append(abs(mass-d['fin_only_mass_g']))
        c={r['case_id']:r for r in d['cases']};orders.append(c['nominal']['G_W_K']>c['pressure_loss']['G_W_K']>c['combined_fault']['G_W_K'] and c['nominal']['G_W_K']>c['asymmetric_blockage']['G_W_K']>c['combined_fault']['G_W_K'])
        retained.append(len(c)==4 and 'dominated_by_all_extrapolations' in d and 'dominated_by_scope_candidates' in d)
        for r in d['cases']:
            expected=d['mass_limit_pass'] and r['thermal_limit_pass_60W'] and r['laminar_scope'] and r['all_numerical_gates_pass']
            if expected!=r['conditional_screen_pass']:issues.append(d['design_id']+':'+r['case_id']+':conditional')
    base=next(d for d in data['designs'] if d['design_id']=='n16_t860'); material=[]
    for cid in ['nominal','combined_fault']:
        primary=next(c['G_W_K'] for c in base['cases'] if c['case_id']==cid);values={r['sensitivity_value']:r['G_W_K'] for r in sens['rows'] if r['case_id']==cid and r['sensitivity_parameter']=='ks'};material.append(values[167.]<primary<values[237.])
    limits=[]
    for p in HERE.rglob('*'):
        if p.is_file() and ((p.suffix=='.json' and p.stat().st_size>=100000) or (p.suffix in ('.pyc','.png','.pdf','.npz','.npy') and p.stat().st_size>=250000)):limits.append(str(p.relative_to(HERE)))
    gates={'nineteen_verification_gates':len(ver['gates'])==19 and all(ver['gates'].values()),'all_36_design_cases_numerically_passed':len(data['designs'])==9 and all(r['all_numerical_gates_pass'] for d in data['designs'] for r in d['cases']),'all_18_sensitivities_numerically_passed':len(sens['rows'])==18 and all(all(r['gates'].values()) for r in sens['rows']),'same_frozen_plan_and_model':ver['plan_sha256']==digest(HERE/'presweep_plan.json')==data['plan_sha256']==sens['plan_sha256'] and ver['code_sha256']==digest(HERE/'pressure_fin.py')==data['code_sha256']==sens['code_sha256'],'original_model_unchanged':digest(SOURCE)=='bdf9998a7f20cdd5d75fef2f5f0e49c9344ebc1e6f31a5ac955bff366d6c9d4c','mass_recomputed_from_fins_only':max(mass_errors)<1e-12,'every_case_and_dominance_flag_retained':all(retained),'pass_flags_include_applicability':not any(':conditional' in x for x in issues),'fault_G_ordering':all(orders),'baseline_material_monotonicity':all(material),'manifest_entries_match':not issues,'file_limits':not limits}
    result={'status':'passed' if all(gates.values()) else 'failed','gates':gates,'manifest_or_pass_issues':issues,'file_limit_failures':limits,'maximum_mass_recomputation_difference_g':max(mass_errors),'audit_code_sha256':digest(__file__),'scope':'Artifact and internal-consistency audit only; numerical verification and screening are not aircraft validation'};save('artifact_audit.json',result);print(json.dumps(result,indent=2))
    if not all(gates.values()):raise SystemExit(1)
if __name__=='__main__':main()
