#!/usr/bin/env python3
"""Preserve the planned inlet control's iteration-limit failure without a retry."""
import json,re
from pathlib import Path
import numpy as np
import study as d
s=d.s
root=d.REPO/'output/openfoam-directional-v1';case=root/'discrete_developed_inlet'
lock=json.loads((root/'run_lock.json').read_text())
assert s.sha(d.HERE/'study.py')==lock['study_sha256'];assert s.sha(d.HERE/'plan.json')==lock['plan_sha256']
log=(case/'log.simpleFoam').read_text();assert 'SIMPLE solution converged' not in log
assert float(s.latest(case).name)==1500
res=s.residuals(case/'log.simpleFoam');assert max(v['initial'] for v in res.values())>1e-7
assert not (case/'flow_final').exists()
clock_seconds=int(re.findall(r'ClockTime = (\d+) s',log)[-1]);execution_seconds=float(re.findall(r'ExecutionTime = ([\d.]+) s',log)[-1])
# Inspect final native pressure only as explicitly unconverged, non-acceptance data.
mesh=s.read_mesh(case);n=len(mesh['centers']);p,_=s.read_field(case/'1500/p',n);u,_=s.read_field(case/'1500/U',n)
x=mesh['centers'][:,0];mask=(x>.25*s.L)&(x<.75*s.L);g=-s.RHO*np.polyfit(x[mask],p[mask],1)[0]
failed={'case':'discrete_developed_inlet','status':'FAILED_FROZEN_RESIDUAL_GATE_AT_ITERATION_LIMIT','iterations':1500,'required_max_final_initial_residual':1e-7,'final_residuals':res,'OpenFOAM_ClockTime_seconds_integer':clock_seconds,'OpenFOAM_ExecutionTime_seconds':execution_seconds,'exact_subprocess_wall_seconds':'not persisted because the frozen driver aborted before writing flow_run.json','budget_charge_upper_bound_seconds':d.PLAN['budget']['maximum_single_solver_wall_seconds'],'unconverged_fields_excluded_from_primary_evidence':True,'provisional_not_accepted_diagnostic':{'native_time_directory':'1500','middle_half_gradient_Pa_m':float(g),'maximum_transverse_velocity_m_s':float(np.max(np.linalg.norm(u[:,1:],axis=1))),'interpretation':'Pressure value is a failed-gate diagnostic only; it does not establish accepted causal attribution or validation.'}}
s.write_json(root/'failed_supplement.json',failed)
rows=[json.loads(p.read_text()) for p in sorted((root/'metrics').glob('*.json')) if not p.name.endswith('_profiles.json')]
assert len(rows)==9;assert all(all(r['execution_gates'].values()) for r in rows)
completed=[r for r in rows if not r['reused_historical']];assert len(completed)==5
used=sum(r['flow_runtime']['wall_seconds'] for r in completed);charge=used+failed['budget_charge_upper_bound_seconds'];assert charge<=2700
old=json.loads((root/'historical_hashes_before.json').read_text());assert all(s.sha(d.REPO/p)==h for p,h in old.items());d.audit_old()
size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file());assert size<=2e9
s.write_json(root/'all_metrics.json',rows)
s.write_json(root/'run_summary.json',{'all_new_cases_completed':False,'all_primary_directional_cases_completed':True,'new_solver_wall_seconds':None,'completed_case_subprocess_wall_seconds':used,'failed_case_OpenFOAM_ClockTime_seconds':clock_seconds,'new_solver_wall_seconds_accounted_upper_bound':charge,'budget_seconds':2700,'budget_accounting':'Five converged subprocess durations measured exactly; failed supplement charged its full preallocated1200s because exact subprocess duration was not persisted. Its solver log reports57s. This deliberately overcounts rather than inventing an exact aggregate.','historical_bytes_unchanged':True,'new_working_bytes':size,'run_lock':lock,'failed_planned_cases':[failed],'completed_new_cases':[r['name'] for r in completed],'unconverged_fields_excluded_from_evidence':True})
print(json.dumps({'completed_directional_cases':5,'failed_inlet_control':failed,'completed_solver_seconds':used,'conservative_total_solver_budget_charge':charge},indent=2))
