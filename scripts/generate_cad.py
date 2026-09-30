#!/usr/bin/env python3
"""Regenerate real CAD + independent validation evidence (CadQuery optional dependency).

python scripts/generate_cad.py --out cad
python scripts/generate_cad.py --verify-only --out cad
python scripts/generate_cad.py --params '{"fin_count":39}' --out output/custom-cad
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aerolab.geometry import (ASSUMPTIONS, GEOMETRY_PRESETS, GEOMETRY_SCHEMA, SOURCE_URL,
    _load_kernel, build_solid, generate_step, generate_stl, geometry_fingerprint,
    geometry_metrics, geometry_preview_svg, inspect_brep, inspect_stl, parse_geometry)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(out):
    cq = _load_kernel()
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    for name, item in manifest['presets'].items():
        params = parse_geometry(item['parameters'])
        assert item['fingerprint'] == geometry_fingerprint(params)
        blobs = {}
        for kind, artifact in item['artifacts'].items():
            compressed = (out / artifact['file']).read_bytes()
            assert digest(compressed) == artifact['compressed_sha256'], (name, kind, 'compressed checksum')
            blobs[kind] = gzip.decompress(compressed)
            assert digest(blobs[kind]) == artifact['sha256'], (name, kind, 'checksum')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.step'
            path.write_bytes(blobs['step'])
            solid = cq.importers.importStep(str(path)).val()
            check = inspect_brep(solid, params)
        mesh = inspect_stl(blobs['stl'], params)
        assert check['passed'] and mesh['passed'], (name, check, mesh)
        print(f"{name}: STEP roundtrip and closed STL verified; V={check['volume_mm3']:.6f} mm3, mass={check['mass_kg']:.9f} kg")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('cad'))
    parser.add_argument('--params', help='JSON partial geometry; otherwise regenerate all three built-in presets')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--source-step', type=Path, help='Optional prior reference proof STEP to independently compare with the reference')
    args = parser.parse_args()
    out = args.out
    if args.verify_only:
        verify(out)
        return
    cq = _load_kernel()
    out.mkdir(parents=True, exist_ok=True)
    geometries = {'custom': parse_geometry(json.loads(args.params))} if args.params else GEOMETRY_PRESETS
    manifest = {
        'schema': GEOMETRY_SCHEMA,
        'title': 'Source-derived idealized heat sink CAD with independent kernel checks',
        'source': {'url': SOURCE_URL, 'report': 'NASA/TM-20230011420 (August 2023)',
                   'location': 'Table 2 and Figure 9, printed p. 13',
                   'scope': 'Older X-57 heat sink benchmark, not final Mod II as-built hardware',
                   'license_note': 'NTRS marks the report Work of the US Government, public use permitted. Geometry here is newly generated from dimensions.'},
        'source_reference_dimensions': asdict(GEOMETRY_PRESETS['reference']),
        'assumptions': list(ASSUMPTIONS),
        'software_versions': {key: importlib.metadata.version(key) for key in ('cadquery', 'cadquery-ocp')},
        'generator_sha256': digest(Path(__file__).read_bytes()),
        'geometry_module_sha256': digest((Path(__file__).resolve().parents[1] / 'aerolab/geometry.py').read_bytes()),
        'presets': {},
        'limits': {'physics_experimentally_validated': False, 'CFD_solved': False,
                   'manufacturing_validated': False, 'original_NASA_CAD': False},
    }
    if args.source_step:
        old = cq.importers.importStep(str(args.source_step)).val()
        check = inspect_brep(old, GEOMETRY_PRESETS['reference'])
        assert check['passed'], check
        manifest['prior_proof_comparison'] = {'file_name': args.source_step.name,
            'sha256': digest(args.source_step.read_bytes()), 'validation': check}
    for name, params in geometries.items():
        solid = build_solid(params)
        brep = inspect_brep(solid, params)
        step = generate_step(params, force_regenerate=True)
        stl = generate_stl(params, force_regenerate=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'roundtrip.step'
            path.write_bytes(step)
            roundtrip = inspect_brep(cq.importers.importStep(str(path)).val(), params)
        mesh = inspect_stl(stl, params)
        assert brep['passed'] and roundtrip['passed'] and mesh['passed']
        artifacts = {}
        for kind, data in (('step', step), ('stl', stl)):
            compressed = gzip.compress(data, compresslevel=9, mtime=0)
            filename = f'{name}.{kind}.gz'
            (out / filename).write_bytes(compressed)
            artifacts[kind] = {'file': filename, 'sha256': digest(data), 'compressed_sha256': digest(compressed),
                               'uncompressed_bytes': len(data), 'compressed_bytes': len(compressed), 'coordinate_unit': 'mm'}
        svg = geometry_preview_svg(params)
        (out / f'{name}.svg').write_text(svg, encoding='utf-8')
        manifest['presets'][name] = {
            'classification': 'published reference dimensions with explicit idealizations' if name == 'reference' else 'synthetic design alternative, not source-reported hardware',
            'parameters': asdict(params), 'fingerprint': geometry_fingerprint(params),
            'analytic': geometry_metrics(params),
            'validation': {'brep': brep, 'step_roundtrip': roundtrip, 'stl': mesh},
            'artifacts': artifacts, 'preview': f'{name}.svg',
        }
        print(f"{name}: V={brep['volume_mm3']:.6f} mm3, mass={brep['mass_kg']:.9f} kg, {brep['faces']} BRep faces, {mesh['triangles']} closed STL triangles")
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    verify(out)


if __name__ == '__main__':
    main()
