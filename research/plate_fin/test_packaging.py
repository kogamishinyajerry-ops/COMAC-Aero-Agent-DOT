#!/usr/bin/env python3
"""Dependency-free relocation, tamper, and fresh-output contract tests."""
import argparse,hashlib,importlib.util,json,pathlib,shutil,subprocess,sys
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('fin_audit_for_tests',HERE/'audit_package.py');audit_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit_module)
RP=audit_module.RP;EP=audit_module.EP;MP=audit_module.MP
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def copy_root(destination):
 destination.mkdir(parents=True,exist_ok=False)
 for prefix in ['research/plate_fin','examples/plate_fin_experiment']:
  shutil.copytree(ROOT/prefix,destination/prefix,ignore=shutil.ignore_patterns('__pycache__','.cache','.mplconfig'))
 return destination
def update_manifest(root):
 path=root/MP;m=json.loads(path.read_text())
 for rec in m['files']:
  p=root/rec['proposed_repository_path'];rec['bytes']=p.stat().st_size;rec['sha256']=sha(p)
 m['total_listed_bytes']=sum(r['bytes'] for r in m['files']);path.write_text(json.dumps(m,indent=2)+'\n')
def refresh_report_identity(root):
 p=root/EP/'replay_index.json';v=json.loads(p.read_text());v['report_sha256']=sha(root/EP/'plate_fin_report.json');p.write_text(json.dumps(v,indent=2)+'\n');update_manifest(root)
def expect_rejected(root):
 try:audit_module.audit(root)
 except (ValueError,OSError,KeyError,AssertionError):return True
 raise AssertionError('Malformed package was accepted')
def main():
 p=argparse.ArgumentParser();p.add_argument('--work-dir',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();a.work_dir=a.work_dir.resolve();a.output=a.output.resolve();a.work_dir.mkdir(parents=True,exist_ok=False);results={};before={str(x.relative_to(ROOT)):sha(x) for parent in [ROOT/RP,ROOT/EP] for x in parent.rglob('*') if x.is_file() and '__pycache__' not in x.parts}
 relocated=copy_root(a.work_dir/'deep'/'relocated_checkout');empty=a.work_dir/'empty_working_directory';empty.mkdir();pin=sha(relocated/MP)
 sub=subprocess.run([sys.executable,'-S',str(relocated/RP/'audit_package.py'),'--expected-manifest-sha256',pin],cwd=empty,check=True,capture_output=True,text=True);results['relocated_audit_from_empty_cwd_without_site_packages']=json.loads(sub.stdout)['all_passed']
 # The application consumes exactly this accepted byte snapshot, never rereads.
 snapshot_root=copy_root(a.work_dir/'verified_record_snapshot');summary,records,identity=audit_module.audit(snapshot_root,return_verified_records=True)
 saved=records[EP+'plate_fin_report.json'];assert isinstance(saved,bytes) and identity==sha(snapshot_root/MP)
 target=snapshot_root/EP/'plate_fin_report.json';target.write_bytes(target.read_bytes()+b' corrupt after verification')
 results['verified_record_snapshot_survives_disk_change']=summary['all_passed'] and records[EP+'plate_fin_report.json']==saved and json.loads(saved)['study_id']=='plate_fin_2024' and expect_rejected(snapshot_root)
 # A changed manifest cannot be accepted against the trusted external identity.
 try:audit_module.audit(relocated,'0'*64)
 except ValueError:results['wrong_pinned_manifest_identity_rejected']=True
 else:raise AssertionError('Wrong pin accepted')
 for case in ['changed_payload','missing_source','traversal','nonfinite_json','physical_validation_claim','boundary_label','source_marker','central_half_channel']:
  root=copy_root(a.work_dir/case)
  if case=='changed_payload':
   f=root/EP/'experimental_comparison.json';f.write_bytes(f.read_bytes()+b' ')
  elif case=='missing_source':(root/RP/'inputs/figure8_markers.json').unlink()
  elif case=='traversal':
   f=root/MP;m=json.loads(f.read_text());m['files'][0]['proposed_repository_path']='../escape.json';f.write_text(json.dumps(m))
  elif case=='central_half_channel':
   f=root/EP/'display_fields.json';m=json.loads(f.read_text());m['channel_domains'][2]['modeled_width_fraction']=1.;m['channel_domains'][2]['modeled_width_m']=m['channel_domains'][2]['physical_full_channel_width_m'];f.write_text(json.dumps(m,separators=(',',':')));update_manifest(root)
  elif case=='source_marker':
   f=root/RP/'inputs/figure8_markers.json';m=json.loads(f.read_text());m['rows'][0]['Rth_K_W']+=.01;f.write_text(json.dumps(m));update_manifest(root)
  else:
   f=root/EP/'plate_fin_report.json';m=json.loads(f.read_text())
   if case=='nonfinite_json':m['rows'][0]['observed']['Rth_K_W']=float('nan')
   elif case=='physical_validation_claim':m['physical_validation_pass']=True
   elif case=='boundary_label':m['rows'][3]['scope']['scope']='robustly_in_declared_laminar_scope'
   f.write_text(json.dumps(m));refresh_report_identity(root)
  results[case+'_rejected']=expect_rejected(root)
 # Prove stat preflight rejects oversize corruption before opening its bytes.
 for case,target in [('oversized_manifest',MP),('oversized_json_artifact',EP+'experimental_comparison.json')]:
  root=copy_root(a.work_dir/case);large=(root/target).resolve()
  with large.open('r+b') as stream:stream.truncate(100000)
  opened=[False];original_open=pathlib.Path.open
  def tracked_open(path,*args,**kwargs):
   if path.resolve()==large:opened[0]=True
   return original_open(path,*args,**kwargs)
  pathlib.Path.open=tracked_open
  try:expect_rejected(root)
  finally:pathlib.Path.open=original_open
  assert not opened[0], 'Oversized artifact was opened before rejection'
  results[case+'_rejected_before_open']=True
 # No prior README, array, PDF or output artifact exists in this fresh directory.
 out=relocated/'output/plate-fin-replays/fresh_contract_test';require_empty=not out.exists()
 cmd=[sys.executable,'-S',str(relocated/RP/'reproduce.py'),'--audit-only','--output-dir',str(out)]
 subprocess.run(cmd,cwd=empty,check=True,capture_output=True,text=True)
 meta=json.loads((out/'run_metadata.json').read_text());results['fresh_output_no_preexisting_artifacts']=require_empty and meta['fresh_output_directory'];results['pinned_files_unchanged_after_default_entry']=meta['pinned_publication_files_unchanged'];again=subprocess.run(cmd,cwd=empty,capture_output=True,text=True);results['existing_output_directory_rejected']=again.returncode!=0
 protected_cmd=[sys.executable,'-S',str(relocated/RP/'reproduce.py'),'--audit-only','--output-dir',str(relocated/EP/'bad_new_output')]
 protected=subprocess.run(protected_cmd,cwd=empty,capture_output=True,text=True);results['pinned_directory_output_rejected']=protected.returncode!=0
 after={str(x.relative_to(ROOT)):sha(x) for parent in [ROOT/RP,ROOT/EP] for x in parent.rglob('*') if x.is_file() and '__pycache__' not in x.parts};results['test_source_publication_unchanged']=before==after
 result={'status':'passed','all_passed':all(results.values()),'checks':results,'test_count':len(results),'dependencies':'Python standard library only, including a python -S audit','test_script_sha256':sha(pathlib.Path(__file__)),'chronology':'Post-comparison packaging robustness checks; no solver, parameter, grid or validation-scope change','physical_validation_pass':None,'aircraft_transfer_authorized':False};assert all(results.values());a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
