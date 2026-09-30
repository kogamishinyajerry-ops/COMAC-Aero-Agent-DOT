#!/usr/bin/env python3
"""Stdlib packaging tests. Mocked subprocess tests check orchestration, not numerics."""
import argparse, hashlib, json, pathlib, shutil, subprocess, sys, tempfile
from unittest.mock import patch
sys.dont_write_bytecode=True
from audit_package import audit, bounded_read, strict_json, ROOT, PREFIX, STUDY, MANIFEST, CORE
import reproduce

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=ROOT);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();root=a.root.resolve();pin=hashlib.sha256((root/MANIFEST).read_bytes()).hexdigest();checks={}
 summary,records,got=audit(root,pin,True);checks['pinned_audit']=summary['all_passed'] and got==pin
 checks['immutable_snapshot_bytes']=all(isinstance(x,bytes) for x in records.values())
 proc=subprocess.run([sys.executable,'-S',str(root/PREFIX/'audit_package.py'),'--root',str(root),'--expected-manifest-sha256',pin],capture_output=True,text=True,check=True);checks['stdlib_python_S_audit']=json.loads(proc.stdout)['all_passed']
 def rejected(call,exc=(ValueError,FileExistsError,RuntimeError)):
  try:call()
  except exc:return True
  return False
 checks['wrong_pin_rejected']=rejected(lambda:audit(root,'0'*64))
 checks['duplicate_json_key_rejected']=rejected(lambda:strict_json(b'{"x":1,"x":2}'))
 checks['nonfinite_json_rejected']=rejected(lambda:strict_json(b'{"x":1e999}'))
 work=root/'output';work.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='appendix_tests_',dir=work) as temp:
  t=pathlib.Path(temp);copy=t/'package';copy.mkdir()
  for name,b in records.items():
   dest=copy/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
  (copy/MANIFEST).write_bytes((root/MANIFEST).read_bytes())
  checks['relocated_audit']=audit(copy,pin)['all_passed']
  before=records[STUDY+'RESULTS.md'];(copy/STUDY/'RESULTS.md').write_text('mutation')
  checks['tamper_rejected']=rejected(lambda:audit(copy,pin));checks['snapshot_survives_disk_mutation']=records[STUDY+'RESULTS.md']==before
  (copy/STUDY/'RESULTS.md').write_bytes(before)
  big=t/'oversized.json'
  with big.open('wb') as f:f.truncate(100000)
  with patch.object(pathlib.Path,'open',side_effect=AssertionError('read attempted after oversized stat')):
   checks['oversize_rejected_before_open']=rejected(lambda:bounded_read(big,100000))
  checks['existing_directory_rejected']=rejected(lambda:reproduce.output_directory(copy,copy/'research'))
  checks['protected_destination_rejected']=rejected(lambda:reproduce.output_directory(copy,copy/'research/new'))
  checks['outside_root_rejected']=rejected(lambda:reproduce.output_directory(copy,t/'elsewhere'))
  (copy/'output').symlink_to(copy/'research',target_is_directory=True)
  checks['symlink_output_root_rejected']=rejected(lambda:reproduce.output_directory(copy))
  (copy/'output').unlink();(copy/'output').mkdir()
  (copy/'output/redirect').symlink_to(copy/'research',target_is_directory=True)
  checks['symlink_destination_parent_rejected']=rejected(lambda:reproduce.output_directory(copy,copy/'output/redirect/new'))
  fresh=reproduce.output_directory(copy);checks['fresh_default_directory']=fresh.is_dir() and fresh.is_relative_to(copy/'output')
  checks['existing_output_rejected']=rejected(lambda:reproduce.output_directory(copy,fresh))
  checks['unknown_suite_rejected']=rejected(lambda:reproduce.run(copy,suite='unknown'))
  with patch.object(reproduce.sys,'platform','darwin'):
   checks['nonlinux_replay_rejected']=rejected(lambda:reproduce.run(copy))
  expected_rows=strict_json(records[STUDY+'refinement.json'])['rows'];snapshot_ok=[]
  def mock_numerics(args,**kwargs):
   workspace=pathlib.Path(kwargs['cwd']);snapshot_ok.append((workspace/CORE).read_bytes()==records[CORE])
   if args[1].endswith('verify_math.py'):
    (copy/CORE).write_bytes(records[CORE]+b'\n# test-only source mutation\n')
   else:
    nx=int(args[args.index('--nx')+1]);nz=int(args[args.index('--nz')+1]);v=float(args[args.index('--speed')+1]);row=next(x for x in expected_rows if x['mesh']['gap_cells']==nx and x['mesh']['axial_slabs']==nz and x['V_interior_m_s']==v)
    pathlib.Path(args[args.index('--output')+1]).write_text(json.dumps(row))
   return subprocess.CompletedProcess(args,0)
  with patch.object(reproduce.subprocess,'run',side_effect=mock_numerics):
   checks['source_mutation_during_replay_rejected']=rejected(lambda:reproduce.run(copy,suite='quick',expected_manifest_sha256=pin))
  checks['staging_uses_verified_snapshot']=bool(snapshot_ok) and all(snapshot_ok)
  (copy/CORE).write_bytes(records[CORE])
 checks['source_package_unchanged_after_tests']=audit(root,pin,True)[1]==records
 result={'status':'passed' if all(checks.values()) else 'failed','all_passed':all(checks.values()),'checks':checks,'checked_manifest_sha256':pin,'test_script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'mocked_orchestration_is_not_numerical_replay':True,'physical_validation_pass':None}
 raw=(json.dumps(result,indent=2)+'\n').encode();assert len(raw)<100000
 with a.output.open('xb') as f:f.write(raw)
 print(json.dumps(result,indent=2));assert all(checks.values())
if __name__=='__main__':main()
