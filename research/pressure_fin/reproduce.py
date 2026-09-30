#!/usr/bin/env python3
"""Safe default: audit pinned evidence and write fresh ignored display output.
Scientific reruns are explicit, optional, and staged in the new output folder.
"""
from __future__ import annotations
import argparse,datetime,importlib.metadata,json,os,pathlib,shutil,subprocess,sys,uuid
sys.dont_write_bytecode=True
from audit_package import audit
from export_display import export,read,write,sha
ROOT=pathlib.Path(__file__).resolve().parents[2];SCI=ROOT/'research/pressure_fin';PIN=ROOT/'examples/pressure_fin_tradeoff';FREEZE=SCI/'original_freeze'

def fresh_output(value=None):
    outroot=ROOT/'output';outroot.mkdir(exist_ok=True)
    if outroot.is_symlink():raise ValueError('output root must not be a symlink')
    p=(ROOT/value if value and not pathlib.Path(value).is_absolute() else pathlib.Path(value)) if value else outroot/('replay-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    p=p.resolve()
    if not p.is_relative_to(outroot.resolve()) or p==outroot.resolve():raise ValueError('output must be a new child of package/output; pinned examples cannot be overwritten')
    if p.exists():raise ValueError('output already exists; refusing overwrite')
    p.mkdir(parents=True);return p

def selected(record,cid,q):
    c=record['cases'][cid];load=next(r for r in c['heat_load_records'] if r['heat_load_W']==q)
    return {'design_id':record['design_id'],'geometry':record['geometry'],'fin_only_aluminum_mass_g':record['fin_only_aluminum_mass_g'],'fixed_60W_combined_criterion':record['fixed_60W_combined_criterion'],'case_id':cid,'supply_pressure_drop_Pa':c['supply_pressure_drop_Pa'],'required_uniform_base_temperature_C':load['required_uniform_base_temperature_C'],'selected_scenario_condition_pass':load['selected_scenario_condition_pass'],'selected_scenario_failure_reasons':load['screen_failure_reasons'],'within_declared_Re_scope':c['within_declared_Re_scope'],'max_channel_Re_Dh':c['max_channel_Re_Dh'],'G_W_K':c['G_W_K'],'hydraulic_dissipation_W':c['hydraulic_dissipation_W'],'blocked_channel_indices':c['blocked_channel_indices'],'branches':c['branches']}

def stage_scientific(out,snapshot):
    stage=out/'scientific';study=stage/'study';study.mkdir(parents=True)
    sp='research/pressure_fin/original_freeze/study/';fp='research/pressure_fin/original_freeze/fin-study/'
    for name,raw in snapshot.items():
        if name.startswith(sp):
            rel=pathlib.PurePosixPath(name[len(sp):])
            if len(rel.parts)==1 and (rel.suffix=='.py' or rel.name=='presweep_plan.json'):(study/rel.name).write_bytes(raw)
        elif name.startswith(fp):
            target=stage/'fin-study'/name[len(fp):];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return study

def scientific(mode,out,design,cid,snapshot):
    study=stage_scientific(out,snapshot);env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');statuses=[]
    def execute(args):
        p=subprocess.run([sys.executable,*args],cwd=study,env=env,capture_output=True,text=True)
        statuses.append({'command':args,'exit_code':p.returncode,'stdout_tail':p.stdout[-6000:],'stderr_tail':p.stderr[-4000:]})
        if p.returncode:raise RuntimeError('scientific subprocess failed: '+p.stderr[-1200:])
    status={'mode':mode,'status':'running','not_aircraft_validation':True,'staged_sources_are_exact_copies':True}
    try:
        if mode=='baseline':
            rec=json.loads(snapshot[f'examples/pressure_fin_tradeoff/candidates/{design}.json']);g=rec['geometry'];c=rec['cases'][cid]
            code="""import json,sys
from pressure_fin import PressureFin,save,thermal_gates
N,t,p=int(sys.argv[1]),float(sys.argv[2]),float(sys.argv[3]); blocked=json.loads(sys.argv[4]); expected=float(sys.argv[5])
r=PressureFin(N,t).solve(p,blocked,800,details=True);r['gates']=thermal_gates(r);r['frozen_expected_G_W_K']=expected;r['frozen_G_relative_difference']=abs(r['G_W_K']/expected-1);r['replay_matches_frozen']=r['frozen_G_relative_difference']<1e-10 and all(r['gates'].values());save('scientific_replay.json',r)
if not r['replay_matches_frozen']:raise SystemExit(1)
"""
            execute(['-c',code,str(g['N_fins']),str(g['fin_thickness_m']),str(c['supply_pressure_drop_Pa']),json.dumps(c['blocked_channel_indices']),str(c['G_W_K'])]);status['record']=read(study/'scientific_replay.json')
        else:
            for script in ['verify_tradeoff.py','check_inherited_operator.py','run_sweep.py','check_screen_point.py','summarize_results.py','audit_study.py','summarize_results.py','audit_study.py']:execute([script])
            fresh=read(study/'design_results.json');pinned=json.loads(snapshot['research/pressure_fin/original_freeze/study/design_results.json']);diff=[]
            for a,b in zip(fresh['designs'],pinned['designs']):
                for ca,cb in zip(a['cases'],b['cases']):diff.append(abs(ca['G_W_K']/cb['G_W_K']-1))
            status['maximum_frozen_G_relative_difference']=max(diff)
            if max(diff)>=1e-10:raise RuntimeError('full replay disagrees with frozen numerical conductance')
            export(study,out/'scientific_display')
        status['status']='passed'
    except Exception as e:
        status['status']='failed';status['error']=str(e)
    status['commands']=statuses
    for pkg in ['numpy','scipy']:
        try:status[pkg+'_version']=importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:status[pkg+'_version']='unavailable'
    write(out/'scientific_status.json',status)
    if status['status']!='passed':raise RuntimeError(status.get('error','scientific failure'))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--design',default='n16_t860');parser.add_argument('--case',dest='case_id',choices=['nominal','pressure_loss','asymmetric_blockage','combined_fault'],default='combined_fault');parser.add_argument('--heat-load',type=int,choices=[40,60,80],default=60);parser.add_argument('--output');parser.add_argument('--scientific',choices=['none','baseline','full'],default='none');args=parser.parse_args()
    result,snapshot,manifest_identity=audit(ROOT,return_verified_records=True)
    def pinned(name):return json.loads(snapshot['examples/pressure_fin_tradeoff/'+name])
    if result['status']!='passed':print(json.dumps(result,indent=2));raise SystemExit(1)
    cat=pinned('catalog.json');ids=[x['design_id'] for x in cat['candidates']]
    if args.design not in ids:parser.error('unknown design; choose '+', '.join(ids))
    out=fresh_output(args.output);write(out/'audit.json',result);export(FREEZE/'study',out/'display',verified_records=snapshot,snapshot_root=ROOT)
    generated=[p for p in (out/'display').rglob('*.json')];same=all(p.read_bytes()==snapshot['examples/pressure_fin_tradeoff/'+p.relative_to(out/'display').as_posix()] for p in generated)
    if not same:raise RuntimeError('fresh display expansion does not match pinned records')
    sel=pinned(f'candidates/{args.design}.json');baseline=pinned('candidates/n16_t860.json');contract=pinned('ui_contract.json')
    view={'schema':'pressure_fin_selected_view_v1','selection':{'design_id':args.design,'case_id':args.case_id,'heat_load_W':args.heat_load},'baseline':selected(baseline,args.case_id,args.heat_load),'selected':selected(sel,args.case_id,args.heat_load),'all_nine_fixed_60W_combined_scatter':cat['candidates'],'fixed_design_criteria':contract['synthetic_fixed_design_criteria'],'required_labels':contract['required_labels'],'branch_pressure_warning':contract['branch_flow_bars']['pressure_warning'],'fresh_display_bytes_match_pinned':same,'package_manifest_sha256':manifest_identity};write(out/'selected_view.json',view)
    if args.scientific!='none':scientific(args.scientific,out,args.design,args.case_id,snapshot)
    post,post_snapshot,post_identity=audit(ROOT,expected_manifest_sha256=manifest_identity,return_verified_records=True)
    if post_snapshot!=snapshot:raise RuntimeError('Pinned package changed during reproduction')
    print(json.dumps({'status':'passed','output_directory':str(out),'selected_view':str(out/'selected_view.json'),'standard_library_audit_checks':len(result['checks']),'scientific_mode':args.scientific,'pinned_examples_unchanged':True,'manifest_sha256':manifest_identity},indent=2))
if __name__=='__main__':main()
