#!/usr/bin/env python3
"""Stdlib-only retained evidence and invariant audit."""
import argparse,hashlib,json
import storage
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--full-source',action='store_true');a=ap.parse_args()
 m=json.loads((HERE/'evidence/manifest.json').read_text())
 for f in m['files']:
  p=(REPO/f['path']).resolve();assert p.is_relative_to(HERE);data=storage.read_bytes(p);assert len(data)==f['bytes'],str(p);assert hashlib.sha256(data).hexdigest()==f['sha256'],str(p)
 for record in storage.records():storage.unpack(record)
 r=json.loads((HERE/'evidence/report.json').read_text());lock=r['run']['run_lock']
 assert sha(HERE/'plan.json')==lock['plan_sha256'];assert sha(HERE/'study.py')==lock['study_sha256']
 assert r['original_validation']['status']=='FAILED_RETAINED';assert r['original_validation']['pressure_relative_change']>r['original_validation']['threshold']
 assert (r['run']['new_solver_wall_seconds'] if r['run']['new_solver_wall_seconds'] is not None else r['run']['new_solver_wall_seconds_accounted_upper_bound'])<=2700;assert r['run']['historical_bytes_unchanged']
 assert r['all_completed_case_execution_gates_passed'];assert len(r['rows'])==(10 if r['run']['all_new_cases_completed'] else 9)
 if not r['run']['all_new_cases_completed']:
  assert len(r['run']['failed_planned_cases'])==1
  failed=r['run']['failed_planned_cases'][0]
  assert failed['case']=='discrete_developed_inlet';assert r['supplementary_inlet']['pressure_change_from_B_Pa_m'] is None;assert not r['supplementary_inlet']['accepted_causal_conclusion'];assert failed['iterations']==1500;assert max(x['initial'] for x in failed['final_residuals'].values())>1e-7
 assert abs(r['directional_attribution']['decomposition_closure_Pa_m'])<1e-10
 count=0
 if a.full_source:
  sm=json.loads((HERE/'evidence/source_artifacts.json').read_text());root=REPO/sm['source_root_relative_to_repository']
  for f in sm['files']:
   p=root/f['path'];assert p.stat().st_size==f['bytes'],str(p);assert sha(p)==f['sha256'],str(p);count+=1
 print(json.dumps({'compact_files_verified':len(m['files']),'new_full_source_artifacts_verified':count,'original_gate':'FAILED_RETAINED','directional_dominance':r['directional_attribution']['predeclared_transverse_dominance_supported'],'fully_developed_operator_90pct_explanation':r['operator_attribution']['predeclared_90_percent_explanation_supported']},indent=2))
if __name__=='__main__':main()
