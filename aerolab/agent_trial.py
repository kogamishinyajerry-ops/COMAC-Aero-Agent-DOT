"""Provider-neutral deterministic tools for a native-assistant engineering trial.

The assistant, not this adapter, chooses designs and next actions. Every evaluate
executes the frozen PDE. No optimizer, model API or autonomous agent is included.
"""
from __future__ import annotations
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'research/native_agent_trial/protocol.json'
PROTOCOL_SHA = '7637f775ae3f670589b8abc7ab4e96abfe8b44f809fbe17b8fcc9ee40604e8ae'
PACKAGE_SHA = '48a9e676091b680c355d25127f625c83130105fcfbbd16cfa1f088257f860b41'
MODEL_PATHS = ('research/pressure_fin/original_freeze/study/pressure_fin.py', 'research/pressure_fin/original_freeze/fin-study/conjugate_fin.py')
MODEL_SHAS = ('24e1603c895e1f268a8aadcbc58a520fef606c108738d98f73898d89f873c08c', 'bdf9998a7f20cdd5d75fef2f5f0e49c9344ebc1e6f31a5ac955bff366d6c9d4c')
MESHES = {'primary': (48,144,800), 'spatial': (64,192,800), 'axial': (48,144,1600)}
IDS = tuple(f'n{n}_t{t}' for n in (12,16,20) for t in (600,860,1200))


def sha(raw): return hashlib.sha256(raw).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dumps(value):
    def scalar(x):
        if hasattr(x, 'item'): return x.item()
        raise TypeError(type(x).__name__)
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False, default=scalar)+'\n').encode()
def write(path, value):
    raw=dumps(value)
    if len(raw)>=100000: raise ValueError('JSON exceeds 100 kB contract')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): raise ValueError('refusing to overwrite evidence: '+str(path))
    path.write_bytes(raw)
    return sha(raw)
def read(path): return json.loads(path.read_bytes())
def identifier(s): return isinstance(s,str) and bool(re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',s))
def finite(x,low,high): return type(x) in (int,float) and math.isfinite(x) and low<=x<=high

def validate_task(t):
    required={'task_id','brief','inlet_temperature_C','max_base_temperature_C','max_fin_mass_g','cases','objective'}
    if not isinstance(t,dict) or set(t)!=required: raise ValueError('task fields must match frozen schema exactly')
    if not identifier(t['task_id']) or not isinstance(t['brief'],str) or not t['brief']: raise ValueError('invalid task identifier/brief')
    if type(t['inlet_temperature_C']) not in (int,float) or t['inlet_temperature_C']!=25: raise ValueError('Tin must be 25 C')
    if not finite(t['max_base_temperature_C'],40,130) or not finite(t['max_fin_mass_g'],15,80): raise ValueError('constraint outside frozen task family')
    if t['objective'] not in ('find_feasible','minimize_fin_mass_among_evaluated'): raise ValueError('invalid objective')
    if not isinstance(t['cases'],list) or not 2<=len(t['cases'])<=4: raise ValueError('2..4 cases required')
    seen=set()
    for c in t['cases']:
        if not isinstance(c,dict) or set(c)!={'case_id','pressure_Pa','blocked_channels','heat_load_W'}: raise ValueError('invalid case fields')
        if not identifier(c['case_id']) or c['case_id'] in seen: raise ValueError('invalid/duplicate case id')
        seen.add(c['case_id'])
        if not finite(c['pressure_Pa'],5,25) or not finite(c['heat_load_W'],10,80): raise ValueError('case outside frozen family')
        if c['blocked_channels'] not in ([],[1]) or any(type(i) is not int for i in c['blocked_channels']): raise ValueError('only [] or integer [1] blockage allowed')
    return t

def design(d):
    if d not in IDS: raise ValueError('unknown frozen candidate')
    n,t=d[1:].split('_t');return int(n),int(t)*1e-6

def geometry(d):
    n,t=design(d)
    return {'N_fins':n,'fin_thickness_m':t,'base_width_m':.0415,'duct_width_m':.0452,'length_m':.09,'fin_height_m':.0113,'interior_gap_m':(.0415-n*t)/(n-1),'fin_only_mass_g':2700*n*t*.0113*.09*1000}

def events(session):
    return sorted((session/'events').glob('*.json'))

def check_session(session):
    meta=read(session/'session.json')
    raw=(session/'task.json').read_bytes()
    if sha(raw)!=meta['task_sha256']: raise ValueError('task bytes changed; no action allowed')
    if sha(PROTOCOL.read_bytes())!=PROTOCOL_SHA or meta['protocol_sha256']!=PROTOCOL_SHA: raise ValueError('protocol changed')
    if sha(Path(__file__).read_bytes())!=meta['adapter_sha256']: raise ValueError('adapter changed after session initialization')
    if sha((ROOT/'aerolab/geometry.py').read_bytes())!=meta['cad_geometry_source_sha256']: raise ValueError('CAD geometry/inspection source changed')
    for path,digest in zip(MODEL_PATHS,MODEL_SHAS):
        if sha((ROOT/path).read_bytes())!=digest: raise ValueError('model source changed')
        target=session/'staged'/Path(path).relative_to('research/pressure_fin/original_freeze')
        if sha(target.read_bytes())!=digest: raise ValueError('staged model changed')
    initial=read(session/'results/001_init.json')
    if initial!=meta: raise ValueError('session metadata differs from initial evidence')
    previous=None
    for expected_sequence,p in enumerate(events(session),1):
        ev=read(p)
        if ev['sequence']!=expected_sequence: raise ValueError('trace sequence mismatch')
        if ev['previous_event_sha256']!=previous: raise ValueError('trace chain mismatch')
        if ev.get('result_file') and sha((session/ev['result_file']).read_bytes())!=ev['result_sha256']: raise ValueError('result bytes changed')
        previous=sha(p.read_bytes())
    return meta,validate_task(json.loads(raw))

def log(session,op,request,decision,result,started,error=None,execution=None):
    prior=events(session);idx=len(prior)+1;name=f'{idx:03d}_{op}'
    result_rel=f'results/{name}.json'
    digest=write(session/result_rel,result)
    event={'sequence':idx,'utc':now(),'actor':'native_assistant','operation':op,'request':request,'decision_summary':decision,
           'result_file':result_rel,'result_sha256':digest,'elapsed_seconds':time.monotonic()-started,'status':'error' if error else 'ok',
           'error':error,'execution':execution or {},'previous_event_sha256':sha(prior[-1].read_bytes()) if prior else None}
    write(session/'events'/f'{idx:03d}.json',event)
    return result

def init_session(session,task_path,decision):
    if session.exists(): raise ValueError('session must be new; evidence cannot be overwritten')
    raw=task_path.read_bytes();task=validate_task(json.loads(raw))
    if len(raw)>=100000: raise ValueError('task too large')
    if sha(PROTOCOL.read_bytes())!=PROTOCOL_SHA: raise ValueError('protocol hash mismatch')
    from research.pressure_fin.audit_package import audit
    accepted,snapshot,identity=audit(ROOT,expected_manifest_sha256=PACKAGE_SHA,return_verified_records=True)
    if accepted['status']!='passed': raise ValueError('source package audit failed')
    session.mkdir(parents=True);(session/'task.json').write_bytes(raw)
    for path,digest in zip(MODEL_PATHS,MODEL_SHAS):
        data=snapshot[path]
        if sha(data)!=digest: raise ValueError('pinned source mismatch')
        target=session/'staged'/Path(path).relative_to('research/pressure_fin/original_freeze')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    meta={'schema':'native_engineering_trial_session_v1','task_id':task['task_id'],'task_sha256':sha(raw),'protocol_sha256':PROTOCOL_SHA,
          'adapter_sha256':sha(Path(__file__).read_bytes()),'source_package_sha256':identity,'model_source_sha256':list(MODEL_SHAS),
          'started_utc':now(),'native_runtime_model_identity':'unverified','external_model_api_calls':0,'human_interventions_during_execution':0,
          'human_setup':'User requested native-assistant execution; development requirement authored before trial. Heldout task setter is an independent assistant, not a human.',
          'cad_geometry_source_sha256':sha((ROOT/'aerolab/geometry.py').read_bytes()),
          'python_version':sys.version,'execution_scope':'Native assistant orchestration; deterministic single-action CLI tools; not a standalone autonomous product'}
    write(session/'session.json',meta)
    return log(session,'init',{'task_id':task['task_id'],'task_sha256':sha(raw)},decision,meta,time.monotonic())

def load_model(session):
    p=session/'staged/study/pressure_fin.py'
    spec=importlib.util.spec_from_file_location('agent_trial_pressure_fin',p)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def inspect_tool(session,task):
    # Analytic rectangular duct series is only a hydraulic scope screen; no thermal shortcut.
    def mean(g,h):
        a,b=sorted((g,h))
        series=sum(math.tanh(n*math.pi*b/(2*a))/n**5 for n in range(1,2000,2))
        return a*a/12*(1-192*a/(math.pi**5*b)*series)
    rows=[]
    for d in IDS:
        g=geometry(d);per=[]
        for c in task['cases']:
            res=[]
            for gap in (g['interior_gap_m'],(.0452-.0415)/2):
                u=c['pressure_Pa']*mean(gap,.0113)/(1.204*1.516e-5*.09)
                res.append(u*(2*gap*.0113/(gap+.0113))/1.516e-5)
            per.append({'case_id':c['case_id'],'analytic_max_Re_Dh':max(res),'within_Re_scope':max(res)<2300})
        rows.append({'design_id':d,**g,'mass_requirement_pass':g['fin_only_mass_g']<=task['max_fin_mass_g'],'hydraulic_screen':per})
    return {'task':task,'candidates':rows,'source_model_sha256':list(MODEL_SHAS),'thermal_results_computed':False,
            'warning':'Analytic hydraulics and mass only. Selection requires live PDE, numerical and mesh checks plus CAD. Existing family results were visible during development; this is not an unseen-family test.'}

def evaluate(session,task,d,cid,mesh,execution=None):
    n,t=design(d);case=next((c for c in task['cases'] if c['case_id']==cid),None)
    if case is None: raise ValueError('unknown task case')
    nx,ny,nz=MESHES[mesh];m=load_model(session)
    if execution is not None: execution['solver_started']=True
    result=m.PressureFin(n,t,nx,ny).solve(case['pressure_Pa'],case['blocked_channels'],nz,details=True)
    if execution is not None: execution['solver_completed']=True
    gates=m.thermal_gates(result);temp=task['inlet_temperature_C']+case['heat_load_W']/result['G_W_K']
    conditions={'numerical_gates':all(gates.values()),'Re_scope':result['max_Re_Dh']<2300,
                'fin_mass':result['fin_only_mass_kg']*1000<=task['max_fin_mass_g'],'base_temperature':temp<=task['max_base_temperature_C']}
    return {'execution':'live_frozen_PDE_solve','design_id':d,'case_id':cid,'mesh_id':mesh,'result':result,'numerical_gates':gates,
            'requirements':case,'required_uniform_base_temperature_C':temp,'temperature_margin_C':task['max_base_temperature_C']-temp,
            'fin_mass_margin_g':task['max_fin_mass_g']-result['fin_only_mass_kg']*1000,'condition_gates':conditions,
            'conditional_pass':all(conditions.values()),'physical_validation_pass':None,'aircraft_transfer_authorized':False}

def cad(session,d):
    from aerolab.geometry import Geometry,_load_kernel,build_solid,generate_step,generate_stl,inspect_brep,inspect_stl,geometry_preview_svg
    n,t=design(d);p=Geometry(length_mm=90,width_mm=41.5,fin_height_mm=11.3,base_thickness_mm=3,fin_thickness_mm=t*1000,fin_count=n)
    cq=_load_kernel();solid=build_solid(p);brep=inspect_brep(solid,p)
    step=generate_step(p,force_regenerate=True);stl=generate_stl(p,force_regenerate=True)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'roundtrip.step';path.write_bytes(step);roundtrip=inspect_brep(cq.importers.importStep(str(path)).val(),p)
    mesh=inspect_stl(stl,p);fin_volume=brep['volume_mm3']-41.5*90*3;fin_mass=fin_volume*1e-9*2700*1000
    mapping={'thermal_fin_only_mass_g':geometry(d)['fin_only_mass_g'],'kernel_fin_only_mass_g':fin_mass,
             'fin_mass_absolute_error_g':abs(fin_mass-geometry(d)['fin_only_mass_g']),
             'base_thickness_mm':3,'base_scope':'Illustrative CAD support only; excluded from thermal fin-mass criterion; base spreading not solved',
             'duct_scope':'45.2 mm wide adiabatic flow boundary is a mathematical boundary, not an exported duct solid'}
    passed=brep['passed'] and roundtrip['passed'] and mesh['passed'] and mapping['fin_mass_absolute_error_g']<1e-8
    folder=session/'cad'/f'{len(events(session))+1:03d}_{d}';folder.mkdir(parents=True)
    artifacts={}
    for kind,raw in (('step',step),('stl',stl)):
        comp=gzip.compress(raw,mtime=0);chunks=[]
        for i,start in enumerate(range(0,len(comp),250000)):
            filename=f'{d}.{kind}.gz.part{i:03d}';blob=comp[start:start+250000];(folder/filename).write_bytes(blob)
            chunks.append({'file':str((folder/filename).relative_to(session)),'bytes':len(blob),'sha256':sha(blob)})
        artifacts[kind]={'raw_sha256':sha(raw),'gzip_sha256':sha(comp),'raw_bytes':len(raw),'chunks':chunks,'restore':'Concatenate chunks in order, then gzip decompress'}
    svg=geometry_preview_svg(p).encode();(folder/f'{d}.svg').write_bytes(svg)
    return {'design_id':d,'parameters':p.to_dict(),'brep':brep,'step_roundtrip':roundtrip,'stl':mesh,'thermal_geometry_mapping':mapping,
            'artifacts':artifacts,'preview_file':str((folder/f'{d}.svg').relative_to(session)),'preview_sha256':sha(svg),'passed':bool(passed),
            'software_versions':{k:importlib.metadata.version(k) for k in ('cadquery','cadquery-ocp')},
            'geometry_source_sha256':sha((ROOT/'aerolab/geometry.py').read_bytes()),
            'source':'Existing generic rectangular-fin CAD kernel; newly generated component dimensions, not original NASA CAD or whole-aircraft output'}

def finalize(session,task,d):
    design(d);rows=[];cads=[];all_evals=[]
    for event_path in events(session):
        event=read(event_path)
        if event['status']!='ok': continue
        r=read(session/event['result_file'])
        if event['operation']=='evaluate': all_evals.append(r)
        if event['operation']=='cad' and r['design_id']==d: cads.append(r)
    selected=[r for r in all_evals if r['design_id']==d]
    for case in task['cases']:
        found={r['mesh_id']:r for r in selected if r['case_id']==case['case_id']}
        complete=set(found)==set(MESHES)
        row={'case_id':case['case_id'],'all_meshes_present':complete,'all_mesh_condition_gates_pass':complete and all(r['conditional_pass'] for r in found.values())}
        if complete:
            g=found['primary']['result']['G_W_K'];sp=abs(found['spatial']['result']['G_W_K']/g-1);ax=abs(found['axial']['result']['G_W_K']/g-1)
            row.update({'spatial_G_relative':sp,'axial_G_relative':ax,'convergence_pass':sp<.005 and ax<.002,
                        'primary_required_base_temperature_C':found['primary']['required_uniform_base_temperature_C'],'worst_mesh_temperature_C':max(r['required_uniform_base_temperature_C'] for r in found.values())})
        else: row['convergence_pass']=False
        rows.append(row)
    cadok=bool(cads and cads[-1]['passed'])
    if cads:
        for artifact in cads[-1]['artifacts'].values():
            blob=b''
            for chunk in artifact['chunks']:
                b=(session/chunk['file']).read_bytes();cadok=cadok and sha(b)==chunk['sha256'] and len(b)<=250000;blob+=b
            cadok=cadok and sha(blob)==artifact['gzip_sha256'] and sha(gzip.decompress(blob))==artifact['raw_sha256']
    rejected=[{'design_id':r['design_id'],'case_id':r['case_id'],'mesh_id':r['mesh_id'],'failed_gates':[k for k,v in r['condition_gates'].items() if not v]} for r in all_evals if not r['conditional_pass']]
    primary_feasible=[]
    for candidate in sorted({r['design_id'] for r in all_evals}):
        case_results={r['case_id']:r for r in all_evals if r['design_id']==candidate and r['mesh_id']=='primary'}
        if set(case_results)=={c['case_id'] for c in task['cases']} and all(r['conditional_pass'] for r in case_results.values()): primary_feasible.append(candidate)
    lighter=[candidate for candidate in primary_feasible if geometry(candidate)['fin_only_mass_g']<geometry(d)['fin_only_mass_g']-1e-9]
    objective_pass=task['objective']=='find_feasible' or not lighter
    inspect_rejections=[]
    for epath in events(session):
        e=read(epath)
        if e['operation']=='inspect' and e['status']=='ok':
            for r in read(session/e['result_file'])['candidates']:
                if not r['mass_requirement_pass'] or not all(x['within_Re_scope'] for x in r['hydraulic_screen']): inspect_rejections.append(r['design_id'])
    rejection_retention_pass=bool(rejected or inspect_rejections) or len(primary_feasible)==len(IDS)
    meta=read(session/'session.json');wall_seconds=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(meta['started_utc'])).total_seconds()
    wall_budget_pass=wall_seconds<=3600
    evs=[read(p) for p in events(session)];passed=cadok and objective_pass and rejection_retention_pass and wall_budget_pass and all(r['all_mesh_condition_gates_pass'] and r['convergence_pass'] for r in rows)
    return {'task_id':task['task_id'],'selected_design_id':d,'outcome':'conditionally_feasible' if passed else 'not_demonstrated_feasible','conditional_acceptance_pass':passed,
            'case_verification':rows,'cad_pass':cadok,'objective_pass':objective_pass,'lighter_primary_feasible_candidates':lighter,'primary_feasible_candidate_ids':primary_feasible,'rejected_evaluations':rejected,'evaluated_candidate_ids':sorted({r['design_id'] for r in all_evals}),
            'solver_calls':sum(e.get('execution',{}).get('solver_started',False) for e in evs),'completed_solver_calls':sum(e.get('execution',{}).get('solver_completed',False) for e in evs),'evaluate_requests':sum(e['operation']=='evaluate' for e in evs),'analytic_rejected_candidate_ids':sorted(set(inspect_rejections)),'rejection_retention_pass':rejection_retention_pass,'wall_seconds':wall_seconds,'wall_budget_pass':wall_budget_pass,'cad_calls':sum(e['operation']=='cad' for e in evs),'tool_calls_including_this':len(evs)+1,
            'errors':sum(e['status']=='error' for e in evs),'human_interventions_during_execution':read(session/'session.json')['human_interventions_during_execution'],
            'physical_validation_pass':None,'global_optimum_established':False,'all_candidate_infeasibility_established':False,
            'interpretation':'Conditional component screening only; immutable requirements, model-validity limits and rejected cases retained. No aircraft, manufacturing or broad generalization claim.'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session',required=True,type=Path);p.add_argument('--decision',required=True,help='Concise public action rationale, not private reasoning')
    sub=p.add_subparsers(dest='operation',required=True)
    si=sub.add_parser('init');si.add_argument('--task',type=Path,required=True)
    sub.add_parser('inspect')
    se=sub.add_parser('evaluate');se.add_argument('--design',required=True,choices=IDS);se.add_argument('--case',dest='case_id',required=True);se.add_argument('--mesh',choices=MESHES,default='primary')
    sc=sub.add_parser('cad');sc.add_argument('--design',required=True,choices=IDS)
    sf=sub.add_parser('finalize');sf.add_argument('--design',required=True,choices=IDS)
    a=p.parse_args(argv);session=a.session.resolve()
    if not a.decision.strip() or len(a.decision)>800: p.error('decision must be 1..800 characters')
    if a.operation=='init': result=init_session(session,a.task,a.decision)
    else:
        meta,task=check_session(session);prior=[read(path) for path in events(session)];started=time.monotonic()
        request={k:v for k,v in vars(a).items() if k not in ('session','decision','operation')}
        execution={'solver_started':False,'solver_completed':False}
        try:
            if any(e['operation']=='finalize' for e in prior): raise ValueError('session already finalized')
            if len(prior)>=40: raise ValueError('tool budget exhausted')
            elapsed=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(meta['started_utc'])).total_seconds()
            if elapsed>3600 and a.operation!='finalize': raise ValueError('60-minute task wall-clock budget exhausted')
            if a.operation=='inspect': result=inspect_tool(session,task)
            elif a.operation=='evaluate':
                if sum(e['operation']=='evaluate' for e in prior)>=24: raise ValueError('solver budget exhausted')
                result=evaluate(session,task,a.design,a.case_id,a.mesh,execution)
            elif a.operation=='cad':
                if sum(e['operation']=='cad' for e in prior)>=3: raise ValueError('CAD budget exhausted')
                result=cad(session,a.design)
            else: result=finalize(session,task,a.design)
            if (datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(meta['started_utc'])).total_seconds()>3600:
                result['wall_clock_budget_exceeded']=True
                if 'conditional_pass' in result: result['conditional_pass']=False
                if 'conditional_acceptance_pass' in result: result['conditional_acceptance_pass']=False;result['outcome']='not_demonstrated_feasible'
            result=log(session,a.operation,request,a.decision,result,started,execution=execution)
        except Exception as exc:
            result={'error_type':type(exc).__name__,'error':str(exc)}
            log(session,a.operation,request,a.decision,result,started,str(exc),execution=execution);print(dumps(result).decode());return 1
    print(dumps(result).decode());return 0

if __name__=='__main__': raise SystemExit(main())
