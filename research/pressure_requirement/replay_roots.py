#!/usr/bin/env python3
"""Optional six-case numerical replay from a verified immutable byte snapshot."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,importlib.util,json,os,pathlib,re,stat,subprocess,uuid
HERE=pathlib.Path(__file__).absolute().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('pressure_package_audit',HERE/'audit_package.py');checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

def output_name(root,requested=None):
 root=checker.absolute_root(root);output=root/'output'
 if requested is None:return 'pressure-requirement-replay-'+uuid.uuid4().hex
 raw=os.fspath(requested)
 if '..' in pathlib.PurePath(raw).parts:raise ValueError('parent traversal in output rejected')
 target=pathlib.Path(raw)
 if not target.is_absolute():target=root/target
 target=pathlib.Path(os.path.abspath(target))
 if target.parent!=output or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',target.name):raise ValueError('output must be a new direct child of verified-root/output')
 return target.name

def output_directory(root,requested=None):
 if sys.platform!='linux':raise ValueError('numerical output staging requires Linux no-follow dirfd semantics')
 root=checker.absolute_root(root);name=output_name(root,requested)
 rootfd=checker.open_root_fd(root)
 try:
  try:os.mkdir('output',0o700,dir_fd=rootfd)
  except FileExistsError:pass
  outfd=os.open('output',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=rootfd)
  try:
   os.mkdir(name,0o700,dir_fd=outfd)  # O_EXCL equivalent for directories; existing/symlinks always fail.
   fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=outfd)
  finally:os.close(outfd)
 finally:os.close(rootfd)
 return root/'output'/name,fd

def materialize(fd,records):
 os.mkdir('verified_source',0o700,dir_fd=fd)
 snapshotfd=os.open('verified_source',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
 try:
  for name,b in sorted(records.items()):
   parts=checker.path_key(name);parent=os.dup(snapshotfd)
   try:
    for part in parts[:-1]:
     try:os.mkdir(part,0o700,dir_fd=parent)
     except FileExistsError:pass
     nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);os.close(parent);parent=nxt
    f=os.open(parts[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=parent)
    with os.fdopen(f,'wb') as stream:stream.write(b)
   finally:os.close(parent)
 finally:os.close(snapshotfd)

def save(fd,name,value):
 b=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
 if len(b)>=100000:raise ValueError('report exceeds strict JSON bound')
 f=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
 with os.fdopen(f,'wb') as stream:stream.write(b)

def run(root=ROOT,requested=None,expected_manifest_sha256=None):
 if sys.platform!='linux':raise ValueError('numerical replay is supported on Linux only; the pinned audit is stdlib-only')
 root=checker.absolute_root(root)
 # Reject protected output selections before any destination creation or optional imports.
 output_name(root,requested)
 summary,records,pin=checker.audit(root,expected_manifest_sha256,True)
 dest,fd=output_directory(root,requested)
 try:
  materialize(fd,records)
  os.mkdir('results',0o700,dir_fd=fd)
  resultsfd=os.open('results',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
  try:
   snapshot=dest/'verified_source'
   verified_snapshot=checker.audit(snapshot,pin,True)[1]
   if verified_snapshot!=records:raise ValueError('materialized snapshot differs from verified bytes')
   env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
   command=[sys.executable,'-I','-B',str(snapshot/checker.PREFIX/'_replay_worker.py'),'--expected-manifest-sha256',pin,'--output-fd',str(resultsfd)]
   process=subprocess.run(command,cwd=snapshot,env=env,pass_fds=(resultsfd,),capture_output=True,text=True,timeout=900)
   if process.returncode:raise RuntimeError('six-case numerical replay failed: '+process.stderr[-3000:])
   report=checker.strict_json(process.stdout)
   if report.get('thermal_evaluations')!=6 or report.get('root_searches')!=0 or report.get('all_passed') is not True:raise ValueError('unexpected replay result')
   snapshot_after=checker.audit(snapshot,pin,True)[1]
   source_after=checker.audit(root,pin,True)[1]
   if snapshot_after!=records or source_after!=records:raise ValueError('source/snapshot changed during replay')
   result={'status':'passed_six_reviewed_main_roots','all_passed':True,'output_directory':str(dest),'package_manifest_sha256':pin,'thermal_evaluations':6,'root_searches':0,'source_package_unchanged':True,'snapshot_unchanged':True,'verified_snapshot_files':len(records),'default_scope':'two geometries timesK=0,1,2 at reviewed main-root pressures; no191-solve campaign rerun','numerical_report':'results/numerical_replay.json','physical_validation_pass':None,'aircraft_transfer_authorized':False}
   save(fd,'replay_report.json',result);return result
  finally:os.close(resultsfd)
 except Exception as e:
  try:save(fd,'replay_failure.json',{'status':'failed','error':str(e),'package_manifest_sha256':pin,'accepted_package_not_modified_by_wrapper':True})
  except Exception:pass
  raise
 finally:os.close(fd)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=pathlib.Path,default=ROOT);parser.add_argument('--output',type=pathlib.Path);parser.add_argument('--expected-manifest-sha256',required=True);a=parser.parse_args()
 print(json.dumps(run(a.root,a.output,a.expected_manifest_sha256),indent=2))
if __name__=='__main__':main()
