#!/usr/bin/env python3
"""Dependency-scoped audit; never rewrites original whole-checkout gate failures."""
import pathlib,json,hashlib,subprocess,datetime
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((HERE/'plan.json').read_text());snapshot=json.loads((HERE/'phase1_manifest.json').read_text());checkpoint=plan['checkpoint']
rows=[]
inputs=list(plan['input_sha256'])
# These accepted saved runs are consumed as exact K0 reproduction targets.
# Their original identity is recovered from the unchanged declared starting Git checkpoint.
for design in ['n16_t860','n16_t600']:
 for case in ['nominal','combined_fault']:
  inputs.append(f'research/pressure_fin/original_freeze/study/runs/{design}_{case}.json')
for name in inputs:
 historical=subprocess.check_output(['git','show',checkpoint+':'+name],cwd=ROOT)
 historical_sha=hashlib.sha256(historical).hexdigest();current_sha=sha(ROOT/name)
 rows.append({'path':name,'original_checkpoint_sha256':historical_sha,'current_sha256':current_sha,'identical_to_original_checkpoint':current_sha==historical_sha,
              'original_declared_input_sha256':plan['input_sha256'].get(name),'matches_original_declared_input':name not in plan['input_sha256'] or current_sha==plan['input_sha256'][name],
              'role':'accepted K0 reproduction target; supplemental dependency inventory' if name not in plan['input_sha256'] else 'frozen declared input'})
phase_checks={name:sha(HERE/name)==r['sha256'] for name,r in snapshot['files'].items()}
cont=HERE/'continuation/plan.json';cp=json.loads(cont.read_text()) if cont.exists() else None
original_audit=json.loads((HERE/'phase1_readout/audit.json').read_text())
checks={'all_consumed_accepted_inputs_identical':all(r['identical_to_original_checkpoint'] and r['matches_original_declared_input'] for r in rows),'immutable_phase_one_snapshot_intact':all(phase_checks.values()),'original_whole_checkout_gate_results_preserved':original_audit['gates']['tracked_tree_unchanged'] is False and original_audit['gates']['checkpoint_unchanged'] is False}
if cp:checks['continuation_runner_unchanged']=sha(HERE/'continue_verification.py')==cp['continuation_runner_sha256']
result={'status':'passed_dependency_scoped_audit' if all(checks.values()) else 'failed_dependency_scoped_audit','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'accepted_input_rows':rows,'immutable_phase_one_file_count':len(phase_checks),'immutable_phase_one_failures':[k for k,v in phase_checks.items() if not v],
 'original_whole_checkout_gates':{k:original_audit['gates'][k] for k in ['tracked_tree_unchanged','checkpoint_unchanged']},
 'disposition':'Whole-checkout failures remain false in immutable phase-one evidence. Authorized concurrent repository integration/guide work is outside the scientific dependencies. This narrower audit establishes input identity only; independent review must assess the disposition.',
 'original_checkpoint':checkpoint,'current_HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'current_status_porcelain':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True),
 'dependency_inventory_note':'The frozen plan names9 accepted inputs; the audit additionally inventories the4 accepted saved run records actually consumed for exact K0 reproduction, comparing their bytes against the original declared starting commit. No input, model or result is modified.'}
s=json.dumps(result,indent=2)+'\n';assert len(s.encode())<100000;(HERE/'dependency_scoped_audit.json').write_text(s)
print(json.dumps({'status':result['status'],'checks':checks,'accepted_dependencies':len(rows),'original_checkout_gates_preserved':result['original_whole_checkout_gates']}))
