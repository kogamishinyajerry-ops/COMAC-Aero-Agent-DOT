#!/usr/bin/env python3
"""Bounded stdlib-only, read-only audit of an externally pinned appendix."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,math,os,pathlib,re,stat
PREFIX='research/pressure_requirement/'
STUDY=PREFIX+'study/'
MANIFEST=PREFIX+'package_manifest.json'
ROOT=pathlib.Path(__file__).absolute().parents[2]
MAX_JSON=100000;MAX_FILE=250000;MAX_FILES=512;MAX_TOTAL=16*1024*1024

def digest(b):return hashlib.sha256(b).hexdigest()
def strict_json(b):
 def pairs(items):
  out={}
  for k,v in items:
   if k in out:raise ValueError('duplicate JSON key: '+k)
   out[k]=v
  return out
 def no_constant(s):raise ValueError('nonfinite JSON: '+s)
 try:data=json.loads(b,object_pairs_hook=pairs,parse_constant=no_constant)
 except (RecursionError,UnicodeDecodeError,json.JSONDecodeError) as e:raise ValueError('invalid bounded JSON') from e
 def visit(x,depth=0):
  if depth>64:raise ValueError('JSON nesting limit')
  if isinstance(x,float) and not math.isfinite(x):raise ValueError('nonfinite JSON number')
  if isinstance(x,(dict,list)):
   if len(x)>10000:raise ValueError('JSON container limit')
   for v in x.values() if isinstance(x,dict) else x:visit(v,depth+1)
 visit(data);return data

def path_key(name):
 if not isinstance(name,str) or len(name)>240 or not re.fullmatch(r'[A-Za-z0-9_.\-/]+',name):raise ValueError('invalid manifest path')
 parts=name.split('/')
 if any(x in ('','.', '..') for x in parts) or name.startswith('/'):raise ValueError('unsafe manifest path')
 return parts

def absolute_root(root):
 root=pathlib.Path(os.path.abspath(os.fspath(root)))
 cur=pathlib.Path(root.anchor)
 for part in root.parts[1:]:
  cur=cur/part
  s=cur.lstat()
  if stat.S_ISLNK(s.st_mode):raise ValueError('symlink root/ancestor rejected: '+str(cur))
  if not stat.S_ISDIR(s.st_mode):raise ValueError('non-directory root/ancestor')
 return root

def open_root_fd(root):
 root=absolute_root(root);fd=os.open(root.anchor,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  for part in root.parts[1:]:
   nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
  return fd
 except Exception:
  os.close(fd);raise

def bounded_read(root,name,limit=MAX_FILE):
 parts=path_key(name);root=absolute_root(root)
 # Linux/Unix dirfd descent refuses links at every component, including during open.
 if hasattr(os,'O_NOFOLLOW') and os.open in os.supports_dir_fd:
  fd=open_root_fd(root)
  try:
   for component in parts[:-1]:
    nxt=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
   f=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
   try:
    info=os.fstat(f)
    if not stat.S_ISREG(info.st_mode) or info.st_size>=limit:raise ValueError('nonregular or oversized file: '+name)
    chunks=[];remaining=limit
    while remaining:
     b=os.read(f,min(65536,remaining))
     if not b:break
     chunks.append(b);remaining-=len(b)
    data=b''.join(chunks)
    if len(data)!=info.st_size or len(data)>=limit:raise ValueError('file changed or oversized: '+name)
    return data
   finally:os.close(f)
  except OSError as e:raise ValueError('unreadable/symlinked package path: '+name) from e
  finally:os.close(fd)
 path=root
 for component in parts:
  path=path/component
  if path.is_symlink():raise ValueError('symlinked package path')
 info=path.stat()
 if not stat.S_ISREG(info.st_mode) or info.st_size>=limit:raise ValueError('nonregular or oversized file')
 with path.open('rb') as f:data=f.read(limit)
 if len(data)!=info.st_size or len(data)>=limit:raise ValueError('file changed or oversized')
 return data

def audit(root=ROOT,expected_manifest_sha256=None,return_verified_records=False):
 if not isinstance(expected_manifest_sha256,str) or not re.fullmatch('[0-9a-f]{64}',expected_manifest_sha256):raise ValueError('a separately trusted64-character lowercase SHA256 pin is required')
 root=absolute_root(root);raw=bounded_read(root,MANIFEST,MAX_JSON)
 if digest(raw)!=expected_manifest_sha256:raise ValueError('manifest pin mismatch')
 manifest=strict_json(raw)
 if manifest.get('schema')!='pressure_requirement_allowlist_v1':raise ValueError('manifest schema')
 chunks=manifest.get('chunks')
 if not isinstance(chunks,list) or not 1<=len(chunks)<=8:raise ValueError('manifest chunk bound')
 records={MANIFEST:raw};entries={};total=len(raw)
 for chunk in chunks:
  name=chunk['path'];path_key(name)
  if not name.startswith(PREFIX+'package_manifest/') or name in records:raise ValueError('manifest chunk path/duplicate')
  b=bounded_read(root,name,MAX_JSON)
  if len(b)!=chunk['bytes'] or digest(b)!=chunk['sha256']:raise ValueError('manifest chunk mismatch')
  records[name]=b;total+=len(b);part=strict_json(b)['files']
  if not isinstance(part,list) or len(part)>80:raise ValueError('chunk count limit')
  for row in part:
   key=row['path'];path_key(key)
   if key in entries or key in records:raise ValueError('duplicate payload path')
   if row['role'] not in ('new_appendix','existing_repository_dependency_compare_only'):raise ValueError('unknown consolidation role')
   if not isinstance(row['bytes'],int) or isinstance(row['bytes'],bool) or not 0<=row['bytes']<MAX_FILE:raise ValueError('payload size bound')
   if not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('invalid payload hash')
   if row['role']=='new_appendix' and not key.startswith(PREFIX):raise ValueError('appendix write allowlist escapes namespace')
   if key.endswith(('.log','.pyc','.pdf','.png','.npy','.npz')) or '__pycache__' in key:raise ValueError('excluded transient/binary payload')
   entries[key]=row
 if len(entries)!=manifest['file_count'] or len(entries)>MAX_FILES:raise ValueError('payload count bound')
 for key,row in entries.items():
  b=bounded_read(root,key,MAX_JSON if key.endswith('.json') else MAX_FILE)
  if len(b)!=row['bytes'] or digest(b)!=row['sha256']:raise ValueError('payload hash/size mismatch: '+key)
  total+=len(b)
  if total>MAX_TOTAL:raise ValueError('package total size limit')
  if key.endswith('.json'):strict_json(b)
  records[key]=b
 def j(name):return strict_json(records[STUDY+name])
 disposition=strict_json(records[PREFIX+'packaging_disposition.json'])
 original_index=j('manifest_index.json');original=[]
 for chunk in original_index['chunks']:
  b=records[STUDY+chunk['path']]
  if digest(b)!=chunk['sha256']:raise ValueError('original manifest chunk changed')
  original+=strict_json(b)['artifact_records']
 omitted={r['path']:r for r in disposition['omitted_logs']}
 if len(original)!=251 or len(omitted)!=3:raise ValueError('original inventory/omission count')
 distributed=0
 for row in original:
  key=STUDY+row['path']
  if row['path'] in omitted:
   if row!=omitted[row['path']] or not row['path'].endswith('.log') or key in records:raise ValueError('log omission mismatch')
  else:
   if key not in records or len(records[key])!=row['bytes'] or digest(records[key])!=row['sha256']:raise ValueError('original scientific artifact changed: '+row['path'])
   distributed+=1
 if distributed!=248:raise ValueError('distributed scientific count')
 phase=j('phase1_manifest.json')
 if len(phase['files'])!=192 or set(phase['files']).intersection(omitted):raise ValueError('phase-one overlap/count')
 for name,row in phase['files'].items():
  if digest(records[STUDY+name])!=row['sha256'] or len(records[STUDY+name])!=row['bytes']:raise ValueError('phase-one snapshot changed')
 dependencies=j('dependency_scoped_audit.json')['accepted_input_rows']
 if len(dependencies)!=13:raise ValueError('scientific dependency count')
 for row in dependencies:
  if digest(records[row['path']])!=row['original_checkpoint_sha256']:raise ValueError('accepted dependency changed')
 original_gates=j('phase1_readout/audit.json')['gates']
 if original_gates['tracked_tree_unchanged'] is not False or original_gates['checkpoint_unchanged'] is not False:raise ValueError('original failed checkout gates erased')
 gate=j('review/final_review_gate.json')
 if gate['status']!='accepted_for_declared_conditional_model_pressure_root_reporting_with_documented_procedural_exceptions':raise ValueError('review status')
 for name,h in gate['evidence_sha256'].items():
  if digest(records[STUDY+name])!=h:raise ValueError('review evidence changed')
 if gate['physical_validation_pass'] is not None or gate['aircraft_transfer_authorized'] is not False:raise ValueError('invalid validation claim')
 if gate['thermal_solve_ledger']!={'original_phase_primary':180,'original_phase_reviewer':0,'separate_continuation_primary':5,'separate_continuation_reviewer':6,'separate_continuation_total':11,'all_phases_total':191}:raise ValueError('scientific phase ledger')
 root_count=0
 for design in ('n16_t860','n16_t600'):
  result=j('continuation/results/'+design+'.json')
  if [c['K'] for c in result['cases']]!=[0,1,2]:raise ValueError('scenario identities')
  for case in result['cases']:
   if case['status']!='numerically_verified_conditional_root':raise ValueError('incomplete case')
   for mesh,root_result in case['roots'].items():
    if root_result['status']!='root_bracketed' or not all(root_result['gates'].values()):raise ValueError('root gate')
    low,high=root_result['fine_bracket'];lo=j(low['file']);hi=j(high['file'])
    if not lo['capacity_at_uniform_base_85C_W']<=60<=hi['capacity_at_uniform_base_85C_W']:raise ValueError('root signs')
    if not 0<high['P_Pa']-low['P_Pa']<.002:raise ValueError('root bracket width')
    root_count+=1
 primary=[k for k in records if k.startswith(STUDY+'runs/') and k.endswith('.json')]
 continuation=[k for k in records if k.startswith(STUDY+'continuation/runs/') and k.endswith('.json')]
 if len(primary)!=180 or len(continuation)!=5 or root_count!=18:raise ValueError('thermal record/root count')
 for name in primary+continuation:
  r=strict_json(records[name])
  if not r['gates'] or not all(v is True for v in r['gates'].values()):raise ValueError('saved numerical failure')
  for state in r['domain_at_both_conditions'].values():
   if not state['within_domain'] or not state['max_Re_Dh']<2300 or not state['max_peak_Mach']<.1:raise ValueError('domain failure')
 ignore=records.get('.gitignore',b'').decode()
 if 'output/' not in ignore.splitlines():raise ValueError('verified output ignore rule missing')
 summary={'status':'passed_pinned_read_only_audit','all_passed':True,'package_manifest_sha256':expected_manifest_sha256,'allowlisted_file_count':len(entries),'verified_snapshot_file_count':len(records),'verified_bytes':total,'original_inventory_entries':251,'distributed_original_non_log_artifacts':248,'omitted_runtime_logs':3,'preserved_phase_one_files':192,'consumed_scientific_dependencies':13,'completed_mesh_roots':18,'accepted_primary_thermal_evaluations':185,'accepted_independent_reproductions':6,'original_whole_checkout_gates':{'tracked_tree_unchanged':False,'checkpoint_unchanged':False},'physical_validation_pass':None,'aircraft_transfer_authorized':False,'science_dependencies_imported':False,'writes_performed':False}
 return (summary,records,expected_manifest_sha256) if return_verified_records else summary

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=pathlib.Path,default=ROOT);parser.add_argument('--expected-manifest-sha256',required=True);args=parser.parse_args()
 print(json.dumps(audit(args.root,args.expected_manifest_sha256),indent=2,allow_nan=False))
if __name__=='__main__':main()
