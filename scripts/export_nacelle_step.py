"""Reassemble an audited manifest's bounded chunks into a normal STEP file."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aerolab.nacelle_geometry import _read_step_artifact, nacelle_fingerprint, GEOMETRY_SOURCE_SHA256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=Path('cad/nacelle/manifest.json'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    if manifest['fingerprint'] != nacelle_fingerprint(manifest['parameters']) or manifest['geometry_module_sha256'] != GEOMETRY_SOURCE_SHA256:
        raise SystemExit('Manifest geometry identity does not match current construction code')
    if not all(manifest[name]['passed'] for name in ('validation','roundtrip','mesh_validation')) or not manifest['validation']['intersection_audit_complete']:
        raise SystemExit('Manifest lacks complete passed geometry verification')
    data=_read_step_artifact(args.manifest.parent,manifest['artifacts']['step'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(data)
    print(f"Wrote {args.output} ({len(data):,} bytes); SHA256 {manifest['artifacts']['step']['sha256']}")

if __name__=='__main__':
    main()
