#!/usr/bin/env python3
"""Stdlib package/negative tests; mocked orchestration is not thermal evidence."""
import sys
sys.dont_write_bytecode=True
import argparse,importlib.util,json,os,pathlib,shutil,subprocess,tempfile
from unittest.mock import patch
HERE=pathlib.Path(__file__).absolute().parent

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
A=module('package_test_audit',HERE/'audit_package.py');R=module('package_test_replay',HERE/'replay_roots.py')

def rejected(call):
 try:call()
 except (ValueError,RuntimeError,OSError,subprocess.SubprocessError):return True
 return False

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=pathlib.Path,default=A.ROOT);parser.add_argument('--expected-manifest-sha256',required=True);parser.add_argument('--report',type=pathlib.Path,required=True);a=parser.parse_args()
 root=A.absolute_root(a.root);summary,records,pin=A.audit(root,a.expected_manifest_sha256,True);checks={}
 checks['pinned_audit']=summary['all_passed'];checks['immutable_snapshot_bytes']=all(isinstance(b,bytes) for b in records.values())
 proc=subprocess.run([sys.executable,'-I','-S','-B',str(root/A.PREFIX/'audit_package.py'),'--root',str(root),'--expected-manifest-sha256',pin],capture_output=True,text=True,check=True,timeout=20)
 checks['python_S_audit_without_science']=json.loads(proc.stdout)['science_dependencies_imported'] is False
 checks['wrong_pin_rejected']=rejected(lambda:A.audit(root,'0'*64))
 checks['duplicate_JSON_rejected']=rejected(lambda:A.strict_json(b'{"x":1,"x":2}'))
 checks['nonfinite_JSON_rejected']=all(rejected(lambda b=b:A.strict_json(b)) for b in [b'{"x":NaN}',b'{"x":1e999}'])
 checks['unsafe_paths_rejected']=all(rejected(lambda k=k:A.path_key(k)) for k in ['../x','/x','a/../x','a//x','a\\x'])
 output=root/'output';output.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='pressure-package-tests-',dir=output) as temp:
  base=pathlib.Path(temp);copy=base/'deep'/'relocated';copy.mkdir(parents=True)
  for name,b in records.items():
   dest=copy/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
  checks['relocated_without_git']=not (copy/'.git').exists() and A.audit(copy,pin)['all_passed']
  before_files={str(f.relative_to(copy)):f.read_bytes() for f in copy.rglob('*') if f.is_file()}
  A.audit(copy,pin)
  checks['audit_performs_no_writes']=before_files=={str(f.relative_to(copy)):f.read_bytes() for f in copy.rglob('*') if f.is_file()}
  target=copy/A.STUDY/'RESULTS.md';saved=target.read_bytes();target.write_bytes(saved+b'\nmutation\n')
  checks['payload_tampering_rejected']=rejected(lambda:A.audit(copy,pin));checks['verified_snapshot_survives_later_mutation']=records[A.STUDY+'RESULTS.md']==saved;target.write_bytes(saved)
  manifest=copy/A.MANIFEST;old=manifest.read_bytes();manifest.write_bytes(old+b' ')
  checks['manifest_tampering_rejected']=rejected(lambda:A.audit(copy,pin));manifest.write_bytes(old)
  target.unlink();target.symlink_to(root/A.STUDY/'RESULTS.md')
  checks['payload_symlink_rejected']=rejected(lambda:A.audit(copy,pin));target.unlink();target.write_bytes(saved)
  fifo=copy/'fifo';os.mkfifo(fifo)
  code="import importlib.util,pathlib; p=pathlib.Path(__import__('sys').argv[1]); s=importlib.util.spec_from_file_location('a',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.bounded_read(pathlib.Path(__import__('sys').argv[2]),'fifo')"
  proc=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(root/A.PREFIX/'audit_package.py'),str(copy)],capture_output=True,text=True,timeout=3)
  checks['FIFO_rejected_without_blocking']=proc.returncode!=0;fifo.unlink()
  huge=copy/'huge.json';huge.write_bytes(b'x'*100000)
  checks['oversized_file_rejected']=rejected(lambda:A.bounded_read(copy,'huge.json',100000));huge.unlink()
  checks['protected_output_rejected_before_creation']=rejected(lambda:R.output_directory(copy,copy/'research/new')) and not (copy/'output').exists()
  checks['outside_output_rejected']=rejected(lambda:R.output_directory(copy,base/'outside'))
  checks['nested_output_rejected']=rejected(lambda:R.output_directory(copy,copy/'output/nested/new'))
  (copy/'output').symlink_to(copy/'research',target_is_directory=True)
  checks['symlink_output_root_rejected']=rejected(lambda:R.output_directory(copy));(copy/'output').unlink();(copy/'output').mkdir()
  (copy/'output/existing').mkdir();(copy/'output/file').write_text('keep')
  checks['existing_directory_rejected']=rejected(lambda:R.output_directory(copy,copy/'output/existing'))
  checks['existing_file_rejected']=rejected(lambda:R.output_directory(copy,copy/'output/file'))
  (copy/'output/link').symlink_to(copy/'research',target_is_directory=True)
  checks['symlink_leaf_rejected']=rejected(lambda:R.output_directory(copy,copy/'output/link'))
  checks['symlinked_parent_rejected']=rejected(lambda:R.output_directory(copy,copy/'output/link/new'))
  (copy/'output/broken').symlink_to(base/'missing')
  checks['broken_symlink_leaf_rejected']=rejected(lambda:R.output_directory(copy,copy/'output/broken'))
  alias=base/'alias';alias.symlink_to(copy,target_is_directory=True)
  checks['symlinked_root_rejected']=rejected(lambda:R.output_directory(alias))
  fresh,fd=R.output_directory(copy);os.close(fd);checks['fresh_direct_ignored_output']=fresh.parent==copy/'output' and fresh.is_dir()
  with patch.object(R.sys,'platform','darwin'):checks['nonlinux_numerical_replay_rejected']=rejected(lambda:R.run(copy,expected_manifest_sha256=pin))
  snapshots=[]
  def mock_numerics(command,**kwargs):
   snapshot=pathlib.Path(kwargs['cwd']);snapshots.append(A.audit(snapshot,pin,True)[1]==records)
   target.write_bytes(saved+b'\nconcurrent source mutation\n')
   return subprocess.CompletedProcess(command,0,stdout=json.dumps({'thermal_evaluations':6,'root_searches':0,'all_passed':True}),stderr='')
  with patch.object(R.subprocess,'run',side_effect=mock_numerics):checks['source_mutation_during_replay_rejected']=rejected(lambda:R.run(copy,expected_manifest_sha256=pin))
  checks['replay_consumes_verified_snapshot']=bool(snapshots) and all(snapshots);target.write_bytes(saved)
 checks['source_package_unchanged']=A.audit(root,pin,True)[1]==records
 result={'status':'passed' if all(checks.values()) else 'failed','all_passed':all(checks.values()),'checks':checks,'manifest_sha256':pin,'actual_thermal_solves':0,'mocked_orchestration_not_numerical_verification':True}
 b=(json.dumps(result,indent=2)+'\n').encode();assert len(b)<100000
 with a.report.open('xb') as f:f.write(b)
 print(json.dumps(result,indent=2));raise SystemExit(0 if result['all_passed'] else 1)
if __name__=='__main__':main()
