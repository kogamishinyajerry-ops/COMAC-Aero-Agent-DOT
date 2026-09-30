#!/usr/bin/env python3
"""Generate the real named X-57 Mod II reconstruction STEP and audited manifest.

python scripts/generate_nacelle.py --out cad/nacelle
python scripts/generate_nacelle.py --out output/custom-nacelle --params '{"hv_fin_count":28}'
python scripts/generate_nacelle.py --verify-only --out cad/nacelle
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aerolab.nacelle_geometry import (SCHEMA, _load_kernel, assembly_geometry, build_nacelle,
    inspect_nacelle_brep, mesh_audit, nacelle_fingerprint,nacelle_metrics,parse_nacelle,provenance,
    _read_step_artifact, GEOMETRY_SOURCE_SHA256, STEP_CHUNK_MAX_BYTES)


def digest(data):return hashlib.sha256(data).hexdigest()


def verify(out):
    manifest=json.loads((out/'manifest.json').read_text());p=parse_nacelle(manifest['parameters'])
    assert manifest['fingerprint']==nacelle_fingerprint(p)
    assert manifest['geometry_module_sha256']==GEOMETRY_SOURCE_SHA256
    check=manifest['validation']
    assert check['passed'] and check['intersection_audit_complete'] and check['unexpected_intersection_count']==0
    assert manifest['roundtrip']['passed'] and manifest['mesh_validation']['passed']
    artifact=manifest['artifacts']['step'];blob=_read_step_artifact(out,artifact)
    cq=_load_kernel()
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'verify.step';path.write_bytes(blob);shape=cq.importers.importStep(str(path)).val()
        assert shape.isValid() and all(s.Closed() for s in shape.Shells())
        assert len(shape.Solids())==manifest['validation']['solid_count']
        assert abs(shape.Volume()-manifest['validation']['volume_mm3'])/shape.Volume()<1e-8
    assert manifest['validation']['passed'] and manifest['mesh_validation']['passed']
    print(f"Verified {len(shape.Solids())} STEP solids, fingerprint {manifest['fingerprint'][:12]}",flush=True)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('cad/nacelle'))
    parser.add_argument('--params',help='JSON partial dimensional parameters')
    parser.add_argument('--verify-only',action='store_true')
    parser.add_argument('--skip-intersections',action='store_true',help='Development only: validation is marked incomplete')
    args=parser.parse_args()
    if args.verify_only:verify(args.out);return
    p=parse_nacelle(json.loads(args.params) if args.params else None);args.out.mkdir(parents=True,exist_ok=True)
    start=time.time();cq=_load_kernel();assembly,shapes=build_nacelle(p)
    print(f'Built {len(shapes)} named components in {time.time()-start:.1f}s',flush=True)
    check=inspect_nacelle_brep(shapes,p,check_intersections=not args.skip_intersections,progress=lambda msg:print(msg,flush=True))
    check['intersection_audit_complete']=not args.skip_intersections
    if args.skip_intersections:check['passed']=False
    print(f"BRep audit: passed={check['passed']}, unexpected intersections={check['unexpected_intersection_count']}",flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'x57-modii-nacelle.step';assembly.save(str(path),exportType='STEP',mode='default');blob=path.read_bytes()
        imported=cq.importers.importStep(str(path)).val()
        roundtrip={'valid':imported.isValid(),'closed_shells':all(s.Closed() for s in imported.Shells()),'solid_count':len(imported.Solids()),'volume_mm3':imported.Volume()}
        roundtrip['relative_volume_error']=abs(imported.Volume()-check['volume_mm3'])/max(check['volume_mm3'],1)
        roundtrip['passed']=roundtrip['valid'] and roundtrip['closed_shells'] and roundtrip['solid_count']==check['solid_count'] and roundtrip['relative_volume_error']<1e-8
    packed=gzip.compress(blob,compresslevel=9,mtime=0);chunks=[]
    for index,offset in enumerate(range(0,len(packed),STEP_CHUNK_MAX_BYTES)):
        part=packed[offset:offset+STEP_CHUNK_MAX_BYTES];filename=f'x57-modii-baseline.step.gz.part-{index:04d}'
        temp=args.out/(filename+'.tmp');temp.write_bytes(part);temp.replace(args.out/filename)
        chunks.append({'index':index,'file':filename,'bytes':len(part),'sha256':digest(part)})
    artifact={'storage':'ordered_chunks_v1','compression':'gzip','download_filename':'x57-modii-nacelle.step','chunk_max_bytes':STEP_CHUNK_MAX_BYTES,'chunks':chunks,'sha256':digest(blob),'compressed_sha256':digest(packed),'bytes':len(blob),'compressed_bytes':len(packed)}
    if _read_step_artifact(args.out,artifact)!=blob:
        raise RuntimeError('Written STEP chunks failed exact reassembly')
    manifest={'schema':SCHEMA,'parameters':p.to_dict(),'fingerprint':nacelle_fingerprint(p),'provenance':provenance(),'artifacts':{'step':artifact},'validation':check,'roundtrip':roundtrip,'mesh_validation':mesh_audit(p),'metrics':nacelle_metrics(p),'named_components':[{'id':c['id'],'label':c['label'],'group':c['group'],'role':c['role'],'thermal_node':c['thermal_node']} for c in assembly_geometry(p)['components']],'software':{'cadquery':cq.__version__},'geometry_module_sha256':GEOMETRY_SOURCE_SHA256,'generator_sha256':digest(Path(__file__).read_bytes())}
    manifest_temp=args.out/'manifest.json.tmp'
    manifest_temp.write_text(json.dumps(manifest,indent=2)+'\n');manifest_temp.replace(args.out/'manifest.json')
    print(f"Wrote {len(packed):,}-byte compressed named STEP in {len(chunks)} bounded chunks in {time.time()-start:.1f}s; roundtrip={roundtrip['passed']}",flush=True)
    if not args.skip_intersections and not (check['passed'] and roundtrip['passed']):raise SystemExit('Geometry audit failed; inspect manifest before using generated artifact')

if __name__=='__main__':main()
