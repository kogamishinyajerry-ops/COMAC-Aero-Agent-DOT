#!/usr/bin/env python3
"""Standard-library relocation, tamper, snapshot and non-overwrite checks."""
from __future__ import annotations
import hashlib,json,pathlib,shutil,subprocess,sys,uuid
sys.dont_write_bytecode=True
from audit_package import audit,MP,RP,EP
from export_display import export
ROOT=pathlib.Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def require(x,m):
    if not x:raise AssertionError(m)
def rejects(fn):
    try:fn()
    except (ValueError,KeyError,FileNotFoundError):return True
    return False
def main():
    checks={};pin=sha(ROOT/MP);summary,snapshot,identity=audit(ROOT,pin,True);checks['verified_snapshot_api']=summary['status']=='passed' and identity==pin and isinstance(next(iter(snapshot.values())),bytes)
    win_key=pathlib.PureWindowsPath(r'C:\portable\examples\pressure_fin_tradeoff\candidates\n16_t600.json').relative_to(pathlib.PureWindowsPath(r'C:\portable')).as_posix()
    checks['posix_snapshot_key_contract_for_windows_paths']=win_key==EP+'candidates/n16_t600.json' and win_key in snapshot
    work=ROOT/'output'/('packaging-qa-'+uuid.uuid4().hex[:8]);work.mkdir(parents=True)
    def clone(name):
        root=work/name/'deeper'/'offline_copy';root.mkdir(parents=True);shutil.copytree(ROOT/RP,root/RP);shutil.copytree(ROOT/EP,root/EP);return root
    copy=clone('relocation');checks['deep_relocation_audit']=audit(copy,pin)['status']=='passed'
    cmd=[sys.executable,'-S',str(copy/RP/'reproduce.py'),'--design','n16_t600','--case','combined_fault','--heat-load','40'];p=subprocess.run(cmd,capture_output=True,text=True);require(p.returncode==0,p.stderr);result=json.loads(p.stdout);view=json.loads(pathlib.Path(result['selected_view']).read_text())
    checks['stdlib_only_default_reproduction']=result['status']=='passed' and result['scientific_mode']=='none';checks['fixed_60W_failure_survives_40W_selection']=view['selected']['selected_scenario_condition_pass'] and not view['selected']['fixed_60W_combined_criterion']['Reynolds_qualified_conditional_pass'];checks['baseline_and_selected_flow_bars_present']=len(view['baseline']['branches'])==17 and len(view['selected']['branches'])==17
    checks['default_did_not_modify_pins']=all(sha(copy/name)==hashlib.sha256(raw).hexdigest() for name,raw in snapshot.items())
    path=copy/EP/'candidates/n16_t600.json';before=path.read_bytes();p=subprocess.run([sys.executable,'-S',str(copy/RP/'reproduce.py'),'--output','examples/pressure_fin_tradeoff/candidates/n16_t600.json'],capture_output=True,text=True);checks['pinned_path_overwrite_rejected']=p.returncode!=0 and path.read_bytes()==before
    p=subprocess.run([sys.executable,'-S',str(copy/RP/'reproduce.py'),'--output',result['output_directory']],capture_output=True,text=True);checks['existing_output_overwrite_rejected']=p.returncode!=0
    _,snap2,_=audit(copy,pin,True);obj=json.loads(before);obj['fin_only_aluminum_mass_g']+=1;path.write_text(json.dumps(obj));checks['artifact_tamper_rejected']=rejects(lambda:audit(copy,pin));checks['snapshot_remains_exact_after_file_change']=snap2[path.relative_to(copy).as_posix()]==before
    frozen=copy/RP/'original_freeze/study/design_results.json';frozen_before=frozen.read_bytes();frozen.write_text('{}')
    export(copy/RP/'original_freeze/study',work/'snapshot_export',verified_records=snap2,snapshot_root=copy)
    checks['snapshot_export_ignores_post_audit_source_mutation']=all(p.read_bytes()==snap2[EP+p.relative_to(work/'snapshot_export').as_posix()] for p in (work/'snapshot_export').rglob('*.json'))
    frozen.write_bytes(frozen_before)
    path.write_bytes(before);manifest=copy/MP;mb=manifest.read_bytes();manifest.write_bytes(mb+b' ');checks['replaced_manifest_rejected']=rejects(lambda:audit(copy,pin));manifest.write_bytes(mb)
    path.write_bytes(b' '*100001);checks['oversize_preflight_rejected']=rejects(lambda:audit(copy,pin));path.write_bytes(before)
    obj=json.loads(before);obj['fixed_60W_combined_criterion']['Reynolds_qualified_conditional_pass']=True;path.write_text(json.dumps(obj,indent=2)+'\n');m=json.loads(mb);entry=next(x for x in m['files'] if x['path']==path.relative_to(copy).as_posix());entry['bytes']=path.stat().st_size;entry['sha256']=sha(path);m['total_listed_bytes']=sum(e['bytes'] for e in m['files']);manifest.write_text(json.dumps(m,indent=2)+'\n');checks['tampered_semantics_rejected_even_with_local_rehash']=rejects(lambda:audit(copy,sha(manifest),True));path.write_bytes(before);manifest.write_bytes(mb)
    require(all(checks.values()),str(checks));out={'status':'passed','checks':checks,'standard_library_only':True,'numpy_or_scipy_imported_by_default':False,'scientific_model_sha256':sha(ROOT/RP/'original_freeze/study/pressure_fin.py'),'test_script_sha256':sha(__file__),'scope':'Packaging integrity, immutable snapshots, display arithmetic and fresh-output safety; no PDE rerun or aircraft validation'};print(json.dumps(out,indent=2))
if __name__=='__main__':main()
