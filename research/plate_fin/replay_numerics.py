#!/usr/bin/env python3
"""Optional offline research replay of unchanged equations and frozen cases.

This is a post-comparison packaging/equivalence run. It never rewrites the
original freeze, changes a coefficient, reads a PDF, or downloads anything.
Requires existing NumPy/SciPy; the application does not import this module.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,math,os,pathlib
from concurrent.futures import ProcessPoolExecutor
from conjugate_fin import Model,KA,RHO,CP,WI
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]; DATA=ROOT/'examples/plate_fin_experiment'; ARCHIVE=HERE/'original_freeze'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text())
def work(job):
    m=Model(**job['model']);r=m.solve(job['speed'],nz=job['nz'],samples=job.get('samples',False));return r

def numeric_diff(actual,expected,path=''):
    diffs=[]
    if isinstance(expected,bool) or expected is None or isinstance(expected,str):
        if actual!=expected:raise AssertionError(f'Non-numeric mismatch: {path}')
    elif isinstance(expected,(int,float)):
        if not isinstance(actual,(int,float)) or isinstance(actual,bool) or not math.isfinite(actual):raise AssertionError(path)
        delta=abs(float(actual)-float(expected));diffs.append(delta)
        if not math.isclose(actual,expected,rel_tol=1e-11,abs_tol=1e-12):raise AssertionError(f'Numeric payload differs: {path}: {actual} versus {expected}')
    elif isinstance(expected,list):
        if len(actual)!=len(expected):raise AssertionError(path)
        for i,(a,b) in enumerate(zip(actual,expected)):diffs+=numeric_diff(a,b,f'{path}[{i}]')
    elif isinstance(expected,dict):
        for k,v in expected.items():diffs+=numeric_diff(actual[k],v,f'{path}.{k}')
    else:raise TypeError(type(expected))
    return diffs

def independent_review():
    path=ARCHIVE/'review/independent_review.py'
    spec=importlib.util.spec_from_file_location('packaged_fin_independent_review',path); module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return {'spectral_reference':module.spectral_reference(),'topology_and_symmetry':module.topology_and_symmetry(),'local_residual_and_interfaces':module.local_residual_and_interfaces(),'low_conductivity_limit':module.low_conductivity_limit(),'observed_spatial_order':module.observed_spatial_order()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,required=True);ap.add_argument('--workers',type=int,default=3);args=ap.parse_args()
    if not 1<=args.workers<=4:raise ValueError('Use1 to4 local workers')
    freeze=load(ARCHIVE/'frozen_numerics.json'); original=load(ARCHIVE/'comparison.json');src=load(HERE/'inputs/figure8_markers.json')
    assert sha(HERE/'conjugate_fin.py')==freeze['code_sha256']==sha(ARCHIVE/'conjugate_fin.py')
    assert sha(HERE/'precomparison_plan.json')==freeze['plan_sha256']==sha(ARCHIVE/'precomparison_plan.json')
    assert sha(ARCHIVE/'verification.json')==freeze['verification_sha256']
    grid=freeze['selected'];assert grid=={'gap_cells':48,'height_cells':144,'axial_steps':1600,'method':'backward_euler','half_array_symmetry':True}
    common={'nx':grid['gap_cells'],'ny':grid['height_cells']};nz=grid['axial_steps'];jobs=[];expected=[]
    for row in original['results']:
        i=row['marker_index'];profile=row['profile'];speed=src['rows'][i]['V_channel_inferred_m_s']
        assert speed==row['prediction']['V_interior_m_s']
        jobs.append({'id':f'primary_{profile}_{i:02d}','model':dict(common,ks=205.,profile=profile),'speed':speed,'nz':nz,'samples':i in [0,3]});expected.append(('primary',row))
    for row in original['material_sensitivity_primary_fd_in_scope']:
        jobs.append({'id':f'material_{row["ks_W_m_K"]:g}_{row["V_m_s"]:.9f}','model':dict(common,ks=row['ks_W_m_K'],profile='fd'),'speed':row['V_m_s'],'nz':nz});expected.append(('material',row))
    for row in original['reported_area_mapping_sensitivity_primary_fd_in_scope']:
        jobs.append({'id':f'area_mapping_{row["reported_V_m_s"]:.9f}','model':dict(common,profile='fd'),'speed':row['reported_V_m_s']*.00186/WI,'nz':nz});expected.append(('mapping',row))
    for row in original['air_property_sensitivities_at_predeclared_10_m_s']:
        which=row['property'];f=row['factor'];jobs.append({'id':f'air_{which}_{f}','model':dict(common,ka=KA*(f if which=='k_air' else 1),heatcap=RHO*CP*(f if which=='volumetric_heat_capacity' else 1)),'speed':10.,'nz':nz});expected.append(('air',row))
    assert len(jobs)==40;rows=[];all_diff=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for job,(kind,ref),r in zip(jobs,expected,pool.map(work,jobs)):
            assert r['energy_relative_balance_max']<1e-8 and r['min_normalized_temperature']>=-1e-10 and r['max_normalized_temperature']<=1+1e-10
            diffs=[]
            if kind=='primary':
                diffs+=numeric_diff(r,ref['prediction'],job['id'])
                diffs+=numeric_diff(r['Rth_K_W']/ref['observed_approx_Rth_K_W']-1,ref['relative_Rth_discrepancy'])
                diffs+=numeric_diff(r['mirrored_channel_contributions_W_K'][0]/r['G_W_K'],ref['side_channels_G_fraction'])
                diffs+=numeric_diff(17*r['mirrored_channel_contributions_W_K'][-1]/r['G_W_K']-1,ref['naive_17_central_channels_relative_G_bias'])
                if job['samples']:
                    name=f'temperature_fields_{ref["profile"]}_marker_{ref["marker_index"]:02d}.json';sample=load(ARCHIVE/name)
                    diffs+=numeric_diff(r['temperature_field_samples'],sample['fields'],name)
            else:
                diffs+=numeric_diff(r['G_W_K'],ref['G_W_K']);diffs+=numeric_diff(r['Rth_K_W'],ref['Rth_K_W'])
            all_diff+=diffs; rows.append({'case_id':job['id'],'kind':kind,'G_W_K':r['G_W_K'],'Rth_K_W':r['Rth_K_W'],'maximum_absolute_payload_difference':max(diffs,default=0.),'energy_relative_balance_max':r['energy_relative_balance_max']})
            print(job['id'],r['Rth_K_W'],'max difference',max(diffs,default=0.),flush=True)
    review=independent_review();expected_review=load(ARCHIVE/'review/independent_review.json');review_diff=numeric_diff(review,{k:expected_review[k] for k in review})
    checks={'all40_cases_replayed':len(rows)==40,'numeric_payload_equivalent':True,'small_field_samples_equivalent':True,'independent_review_numeric_payload_equivalent':True,'solver_bytes_unchanged':True,'precomparison_plan_bytes_unchanged':True,'all_replayed_energy_and_temperature_gates_pass':True,'no_source_pdf_required':True}
    out={'schema_version':1,'study_id':'plate_fin_2024','status':'post_comparison_packaging_numeric_replay_passed','all_passed':True,'checks':checks,'chronology':'Packaging-only replay performed after experimental residuals were already observed. It preserves, and does not replace, the original precomparison freeze.','equations_grids_materials_properties_and_scenarios_changed':False,'physical_validation_pass':None,'aircraft_transfer_authorized':False,'application_dependencies_added':False,'source_pdf_required':False,'source_pdf_redistributed':False,'original_solver_sha256':sha(ARCHIVE/'conjugate_fin.py'),'packaged_solver_sha256':sha(HERE/'conjugate_fin.py'),'original_precomparison_freeze_sha256':sha(ARCHIVE/'frozen_numerics.json'),'original_comparison_sha256':sha(ARCHIVE/'comparison.json'),'packaged_marker_transcription_sha256':sha(HERE/'inputs/figure8_markers.json'),'replay_script_sha256':sha(__file__),'numeric_equivalence_tolerance':{'relative':1e-11,'absolute':1e-12},'maximum_absolute_payload_difference':max(all_diff,default=0.),'maximum_absolute_independent_review_difference':max(review_diff,default=0.),'cases':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');assert args.output.stat().st_size<100000;print(args.output,flush=True)
if __name__=='__main__':main()
