#!/usr/bin/env python3
"""Create small hash manifests for scientific evidence; no publication or copying."""
import pathlib,json,hashlib,datetime
HERE=pathlib.Path(__file__).resolve().parent
OUT=HERE/'manifest';OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(path,data):
 s=json.dumps(data,indent=2)+'\n';assert len(s.encode())<100000,path;path.write_text(s)
records=[]
for p in sorted(HERE.rglob('*')):
 if not p.is_file():continue
 rel=p.relative_to(HERE)
 if '__pycache__' in rel.parts or 'manifest'==rel.parts[0] or rel.name=='manifest_index.json' or rel.name.endswith('.tmp'):continue
 records.append({'path':str(rel),'bytes':p.stat().st_size,'sha256':sha(p)})
chunks=[]
for i in range(0,len(records),80):
 path=OUT/f'artifacts_{i//80:03d}.json';dump(path,{'artifact_records':records[i:i+80]})
 chunks.append({'path':str(path.relative_to(HERE)),'count':len(records[i:i+80]),'bytes':path.stat().st_size,'sha256':sha(path)})
plan=json.loads((HERE/'plan.json').read_text())
index={'schema':'conditional_pressure_scientific_evidence_manifest_v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'artifact_count':len(records),'chunks':chunks,'external_immutable_inputs':plan['input_sha256'],'excluded':['__pycache__ and bytecode','temporary incomplete writes','manifest self-hashes (index hashes each chunk)'],'limits':{'JSON_bytes_strict_max':100000,'binary_bytes_strict_max':250000},'publication_performed':False,'scope':'Scientific evidence only; subsequent repository integration/publication is a separate parent task.'}
dump(HERE/'manifest_index.json',index)
for p in HERE.rglob('*.json'):assert p.stat().st_size<100000,p
for p in HERE.rglob('*'):
 if p.is_file() and p.suffix in ['.pyc','.npy','.npz','.png','.pdf']:assert p.stat().st_size<250000,p
print(json.dumps({'artifact_count':len(records),'chunks':len(chunks),'largest_JSON_bytes':max(p.stat().st_size for p in HERE.rglob('*.json')),'published':False}))
