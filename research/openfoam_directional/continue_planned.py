#!/usr/bin/env python3
"""Continue only the already-preregistered independent inlet case after T2 timeout.
Does not rerun, extend, or use the failed large case; preserves its full accounting.
"""
import argparse,datetime,json,shutil,time
from pathlib import Path
import study as d
s=d.s

def main(root):
 lock=json.loads((root/'run_lock.json').read_text())
 assert s.sha(d.HERE/'study.py')==lock['study_sha256'];assert s.sha(d.HERE/'plan.json')==lock['plan_sha256']
 failed=json.loads((root/'failed_attempt.json').read_text())
 assert 'TimeoutExpired' in failed['exception'],'Continuation applies only to the frozen solver timeout'
 assert failed['case']=='transverse_extra_fine','Only the last planned primary case may be bypassed as failed'
 assert not (root/'run_summary.json').exists(),'Do not continue an already finalized run'
 entry=d.PLAN['new_supplementary_cases'][0];assert entry['name']=='discrete_developed_inlet'
 case=root/entry['name'];assert not case.exists(),'Never overwrite or retry an existing supplement'
 used=failed['total_solver_wall_seconds_including_failed']
 remaining=d.PLAN['budget']['maximum_new_solver_wall_seconds']-used
 assert remaining>0,'No new solver budget remains'
 s.write_json(root/'continuation_lock.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':s.sha(Path(__file__)),'reason':'Frozen per-case timeout; complete only the independent inlet case already registered before first solver','failed_case_not_retried':failed['case'],'solver_seconds_used_including_failed':used,'remaining_total_solver_seconds':remaining,'plan_sha256':lock['plan_sha256']})
 mesh=s.setup(case,entry['grid']);d.supplement_inlet(case,mesh,entry['grid']);del mesh
 start=time.monotonic()
 try:elapsed=s.run([s.FOAM,'simpleFoam','-case',case],case,'log.simpleFoam',timeout=min(remaining,d.PLAN['budget']['maximum_single_solver_wall_seconds']))
 except Exception as exc:
  s.write_json(root/'continuation_failure.json',{'case':entry['name'],'exception':repr(exc),'total_solver_wall_seconds_including_failed':used+time.monotonic()-start});raise
 used+=elapsed;final=s.latest(case)
 assert 'SIMPLE solution converged' in (case/'log.simpleFoam').read_text()
 shutil.copytree(final,case/'flow_final');s.write_json(case/'flow_run.json',{'wall_seconds':elapsed,'iterations':float(final.name),'final_time':final.name,'solver':'simpleFoam'})
 row=d.analyse(case,entry['name'],root/'metrics');print(json.dumps(row,indent=2),flush=True)
 rows=[json.loads(p.read_text()) for p in sorted((root/'metrics').glob('*.json')) if not p.name.endswith('_profiles.json')]
 old=json.loads((root/'historical_hashes_before.json').read_text());assert all(s.sha(d.REPO/p)==h for p,h in old.items())
 d.audit_old();size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
 assert size<=d.PLAN['budget']['maximum_new_working_storage_GB']*1e9
 s.write_json(root/'all_metrics.json',rows)
 s.write_json(root/'run_summary.json',{'all_new_cases_completed':False,'new_solver_wall_seconds':used,'historical_bytes_unchanged':True,'new_working_bytes':size,'run_lock':lock,'failed_planned_cases':[failed],'completed_new_cases':[r['name'] for r in rows if not r['reused_historical']],'unconverged_fields_excluded_from_evidence':True})
 print('BOUNDED PARTIAL STUDY FINALIZED: T2 timeout preserved; planned supplement complete',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.output.resolve())
