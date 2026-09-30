#!/usr/bin/env python3
"""Run only a separately authorized/frozen verification continuation.
Does not modify phase-one code, plan, runs, results or terminal evidence.
Artifact references inside combined results are relative to the original study root.
"""
from __future__ import annotations
import sys,pathlib,importlib.util,json,hashlib,time,copy,datetime
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent;CONT=HERE/'continuation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
plan_path=CONT/'plan.json'
if not plan_path.exists():raise SystemExit('No separately frozen continuation plan; nothing run')
plan=load(plan_path);PLAN_HASH=sha(plan_path)
assert PLAN_HASH==(CONT/'plan.sha256').read_text().split()[0]
assert plan['status']=='authorized_frozen_before_continuation_solves'
assert sha(pathlib.Path(__file__))==plan['continuation_runner_sha256']
DEADLINE=datetime.datetime.fromisoformat(plan['execution_window_end_utc'])
for name,h in plan['accepted_input_sha256'].items():
 assert sha(HERE.parents[2]/name)==h, 'accepted upstream artifact changed: '+name
for name,h in plan['phase_one_input_sha256'].items():
 assert sha(HERE/name)==h, 'phase-one artifact changed: '+name
spec=importlib.util.spec_from_file_location('phase_one_pressure_requirement',HERE/'pressure_requirement.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
# Redirect only new artifact writes. The inherited model, source paths, original
# equations, frozen thresholds and original root routine remain unchanged.
p.HERE=CONT
PRIMARY_LIMIT=plan['resource_budget']['max_additional_primary_thermal_solves']
p.MAX_SOLVES=2*PRIMARY_LIMIT
START=time.monotonic()
COUNTER=len(list((CONT/'runs').rglob('*.json')))
class Resume(p.Study):
 def __init__(self,design):
  super().__init__(design)
  for folder,prefix in [(HERE/'runs'/design,'runs/'),(CONT/'runs'/design,'continuation/runs/')]:
   for f in folder.glob('*.json'):
    r=load(f);m=r['mesh'];key=(r['end_loss_K'],m['nx'],m['ny'],m['nz'],float(r['nominal_pressure_budget_Pa']),r['condition'])
    r['record_file']=prefix+design+'/'+f.name;self.cache[key]=r
  self.count=len(list((CONT/'runs'/design).glob('*.json')))
 def evaluation(self,K,mesh,P,condition='combined'):
  global COUNTER
  key=(K,*mesh,float(P),condition)
  if key in self.cache:return self.cache[key]
  if datetime.datetime.now(datetime.timezone.utc)>=DEADLINE:raise RuntimeError('continuation execution deadline reached')
  if COUNTER>=PRIMARY_LIMIT:raise RuntimeError('separate continuation primary solve cap reached')
  if time.monotonic()-START>plan['resource_budget']['soft_wall_time_minutes']*60:raise RuntimeError('continuation wall-time cap reached')
  r=super().evaluation(K,mesh,P,condition)
  COUNTER+=1;local_path=r['record_file'];r['record_file']='continuation/'+local_path
  r.update(continuation_plan_sha256=PLAN_HASH,continuation_runner_sha256=sha(pathlib.Path(__file__)),phase='separate_bounded_verification_continuation',phase_one_equations_and_root_routine_unchanged=True)
  p.save(local_path,r)
  return r

for design in ['n16_t860','n16_t600']:
 original=load(HERE/'results'/f'{design}.json');result=copy.deepcopy(original)
 s=Resume(design)
 result.update(phase_one_result_source=f'results/{design}.json',phase_one_status=original['status'],phase_one_thermal_solve_count=original['new_thermal_solve_count'],
               artifact_reference_base='original pressure-requirement-study directory',continuation_plan_sha256=PLAN_HASH,status='continuation_running')
 for case in result['cases']:
  if case['status']=='numerically_verified_conditional_root':continue
  key=f"{design}:K{case['K']}:axial"
  assert key in plan['outstanding_root_cases'], 'undeclared continuation case'
  assert case['roots'].get('main',{}).get('status')=='root_bracketed'
  assert case['roots'].get('spatial',{}).get('status')=='root_bracketed'
  case['phase_one_status']=case['status'];case['phase_one_error']=case.get('error')
  K=case['K'];main=case['roots']['main'];P=main['root_Pa'];mesh=(48,144,1600)
  try:
   reference=s.evaluation(K,(48,144,800),P);probe=s.evaluation(K,mesh,P)
   refined=s.root(K,mesh,seed=P);case['roots']['axial']=refined
   case['axial_sensitivity']={'G_relative_at_main_pressure':abs(probe['G_W_K']/reference['G_W_K']-1),'record_at_main_pressure':probe['record_file'],
     'root_P_relative':abs(refined['root_Pa']/P-1) if refined['status']=='root_bracketed' else None,
     'G_gate_pass':abs(probe['G_W_K']/reference['G_W_K']-1)<.002,
     'root_gate_pass':refined['status']=='root_bracketed' and abs(refined['root_Pa']/P-1)<.005}
   case['status']='numerically_verified_conditional_root' if all(rr['status']=='root_bracketed' and all(rr['gates'].values()) for rr in case['roots'].values()) and all(case[n+'_sensitivity']['G_gate_pass'] and case[n+'_sensitivity']['root_gate_pass'] for n in ['spatial','axial']) else 'verification_failed_or_incomplete'
   case.pop('error',None)
  except Exception as e:
   case['status']='continuation_failed_or_resource_limited';case['error']=str(e)
  p.save(pathlib.Path('results')/(design+'.json'),result)
 result.update(status='continuation_complete_pending_independent_review',additional_primary_thermal_solve_count=s.count)
 p.save(pathlib.Path('results')/(design+'.json'),result)
p.save('execution.json',{'status':'terminal','additional_primary_thermal_solve_count':COUNTER,'limit':PRIMARY_LIMIT,'elapsed_s':time.monotonic()-START,'plan_sha256':PLAN_HASH,'runner_sha256':sha(pathlib.Path(__file__)),'primary_phase_preserved':all(sha(HERE/name)==h for name,h in plan['phase_one_input_sha256'].items()),'accepted_upstream_preserved':all(sha(HERE.parents[2]/name)==h for name,h in plan['accepted_input_sha256'].items())})
print(json.dumps({'continuation_primary_count':COUNTER,'limit':PRIMARY_LIMIT}),flush=True)
