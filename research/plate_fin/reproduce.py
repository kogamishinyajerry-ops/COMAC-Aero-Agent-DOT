#!/usr/bin/env python3
"""Reproduce into a new ignored output directory; never promote saved evidence."""
import argparse,hashlib,json,os,pathlib,subprocess,sys,uuid
sys.dont_write_bytecode=True
from audit_package import audit,ROOT,RP,EP,MP
HERE=pathlib.Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--output-dir',type=pathlib.Path);p.add_argument('--audit-only',action='store_true');p.add_argument('--workers',type=int,default=3);a=p.parse_args()
 out=(a.output_dir if a.output_dir else ROOT/'output/plate-fin-replays'/('run_'+uuid.uuid4().hex[:12])).resolve()
 if out.is_relative_to((ROOT/RP).resolve()) or out.is_relative_to((ROOT/EP).resolve()):raise ValueError('Replay output may not overwrite either pinned publication directory')
 if out.exists():raise ValueError('Replay requires a fresh output directory; existing directories are never reused')
 audit_result=audit(ROOT);manifest=json.loads((ROOT/MP).read_text());pinned=[ROOT/r['proposed_repository_path'] for r in manifest['files']]+[ROOT/MP];before={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in pinned}
 out.mkdir(parents=True,exist_ok=False);(out/'package_audit.json').write_text(json.dumps(audit_result,indent=2)+'\n')
 if not a.audit_only:
  env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
  subprocess.run([sys.executable,str(HERE/'replay_numerics.py'),'--workers',str(a.workers),'--output',str(out/'packaging_replay.json')],env=env,check=True)
 after={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in pinned};assert before==after,'Pinned publication files changed during replay'
 metadata={'status':'passed','mode':'audit_only' if a.audit_only else 'numeric_replay','fresh_output_directory':True,'pinned_publication_files_unchanged':True,'accepted_manifest_sha256':before[MP],'publication_promotion_performed':False,'physical_validation_pass':None,'aircraft_transfer_authorized':False}
 (out/'run_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n');print(out)
if __name__=='__main__':main()
